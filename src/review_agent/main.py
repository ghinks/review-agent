import asyncio
import multiprocessing as mp
from queue import Empty
from typing import Any, Optional

import typer
from rich.console import Console
from rich.progress import track

from review_agent.db import get_outliers
from review_agent.providers import Sdk, get_provider

app = typer.Typer(help="Agentic Analysis for PR Outliers")
console = Console()


def agent_worker(sdk: Sdk, repo: str, pr_num: int, reasons: str, queue: mp.Queue) -> None:
    # Construct the provider inside the child process: SDK clients/agents are
    # not necessarily picklable, and a provider's import-time setup should run
    # only in the process that uses it.
    try:
        provider = get_provider(sdk)
        result = asyncio.run(provider.analyze(repo, pr_num, reasons))
    except Exception as e:
        queue.put({"ok": False, "result": f"Error during analysis: {e}"})
    else:
        queue.put({"ok": True, "result": result})


def analyze_pr_with_timeout(sdk: Sdk, repo: str, pr_num: int, reasons: str, timeout: int) -> str:
    queue: mp.Queue[dict[str, Any]] = mp.Queue()
    process = mp.Process(target=agent_worker, args=(sdk, repo, pr_num, reasons, queue))
    process.start()
    process.join(timeout)

    if process.is_alive():
        process.terminate()
        process.join()
        return f"Error during analysis: timed out after {timeout} seconds"

    try:
        payload = queue.get_nowait()
    except Empty:
        return f"Error during analysis: agent process exited with code {process.exitcode} without a response"

    return str(payload["result"])


@app.command()
def analyze(
    db_path: str = typer.Option(..., help="Path to the review_classification.db file"),
    repo: str = typer.Option(..., help="GitHub repository name (owner/repo)"),
    sdk: Sdk = typer.Option(Sdk.antigravity, help="Reasoning SDK: antigravity | openai | anthropic"),
    output: str = typer.Option("agentic_report.md", help="Output markdown file"),
    limit: Optional[int] = typer.Option(None, help="Limit number of PRs to analyze"),
    timeout: int = typer.Option(180, help="Timeout in seconds for each agent startup and analysis"),
):
    """Analyze outlier PRs using an LLM agent."""
    console.print(f"Fetching outliers for [bold]{repo}[/bold] from {db_path}...")
    try:
        outliers = get_outliers(db_path, repo)
    except Exception as e:
        console.print(f"[bold red]Error reading database:[/bold red] {e}")
        raise typer.Exit(1)

    if not outliers:
        console.print("[yellow]No outliers found.[/yellow]")
        raise typer.Exit()

    if limit:
        outliers = outliers[:limit]

    console.print(f"Found {len(outliers)} outlier PRs to analyze using [bold]{sdk.value}[/bold].")
    for pr in outliers:
        console.print(f"PR #{pr['number']}: {pr['title']} ({pr['url']}")

    report_lines = [f"# Agentic Analysis Report for {repo}\n"]

    for pr in track(outliers, description="Analyzing PRs..."):
        pr_num = pr['number']
        title = pr['title']
        reasons = pr['outlier_features']
        max_z = pr['max_abs_z_score']

        console.print(f"\n[bold blue]Analyzing PR #{pr_num}:[/bold blue] {title}")
        console.print(f"Flagged for: {reasons} (max Z={max_z:.2f})")
        console.print(f"Starting isolated agent process (timeout: {timeout}s)...")

        result = analyze_pr_with_timeout(sdk, repo, pr_num, reasons, timeout)
        if result.startswith("Error during analysis:"):
            console.print(f"[red]{result}[/red]")

        report_lines.append(f"## PR #{pr_num}: {title}")
        report_lines.append(f"**Flagged for:** {reasons} (max Z={max_z:.2f})\n")
        report_lines.append(result)
        report_lines.append("\n---\n")

    with open(output, "w") as f:
        f.write("\n".join(report_lines))

    console.print(f"\n[bold green]Analysis complete! Report saved to {output}[/bold green]")

if __name__ == "__main__":
    app()
