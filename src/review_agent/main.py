import asyncio
import multiprocessing as mp
from datetime import datetime
from queue import Empty
from typing import Any, List, Optional

import typer
from rich.console import Console
from rich.progress import track

from review_agent.db import get_outliers
from review_agent.pr_sources import load_pr_numbers_from_file, merge_records
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
    repo: str = typer.Option(..., help="GitHub repository name (owner/repo)"),
    db_path: Optional[str] = typer.Option(
        None, help="Path to the review_classification.db file (outlier PRs)"
    ),
    pr: Optional[List[int]] = typer.Option(
        None, "--pr", help="A specific PR number to analyze. Repeat to add more."
    ),
    pr_file: Optional[str] = typer.Option(
        None, help="Path to a file listing PR numbers to analyze (one per line)"
    ),
    sdk: Sdk = typer.Option(Sdk.antigravity, help="Reasoning SDK: antigravity | openai | anthropic"),
    from_date: Optional[datetime] = typer.Option(
        None,
        formats=["%Y-%m-%d"],
        help="Only analyze DB outlier PRs created on or after midnight of this date (YYYY-MM-DD)",
    ),
    output: str = typer.Option("agentic_report.md", help="Output markdown file"),
    limit: Optional[int] = typer.Option(None, help="Limit number of PRs to analyze"),
    timeout: int = typer.Option(180, help="Timeout in seconds for each agent startup and analysis"),
):
    """Analyze PRs using an LLM agent.

    PRs come from any combination of: the outlier database (--db-path), specific
    numbers (--pr), and/or a file of numbers (--pr-file). At least one source is
    required.
    """
    if not db_path and not pr and not pr_file:
        console.print(
            "[bold red]Error:[/bold red] provide at least one PR source "
            "(--db-path, --pr, or --pr-file)."
        )
        raise typer.Exit(1)

    outliers: list[dict[str, Any]] = []
    if db_path:
        console.print(f"Fetching outliers for [bold]{repo}[/bold] from {db_path}...")
        try:
            outliers = get_outliers(db_path, repo, from_date)
        except Exception as e:
            console.print(f"[bold red]Error reading database:[/bold red] {e}")
            raise typer.Exit(1)

    manual_numbers: List[int] = list(pr or [])
    if pr_file:
        try:
            manual_numbers.extend(load_pr_numbers_from_file(pr_file))
        except (OSError, ValueError) as e:
            console.print(f"[bold red]Error reading PR file:[/bold red] {e}")
            raise typer.Exit(1)

    outliers = merge_records(outliers, manual_numbers, repo)

    if not outliers:
        console.print("[yellow]No PRs to analyze.[/yellow]")
        raise typer.Exit()

    if limit:
        outliers = outliers[:limit]

    console.print(f"Found {len(outliers)} PRs to analyze using [bold]{sdk.value}[/bold].")
    for record in outliers:
        console.print(f"PR #{record['number']}: {record['title']} ({record['url']})")

    report_lines = [f"# Agentic Analysis Report for {repo}\n"]

    for record in track(outliers, description="Analyzing PRs..."):
        pr_num = record['number']
        title = record['title']
        reasons = record['outlier_features']
        max_z = record['max_abs_z_score']
        z_suffix = f" (max Z={max_z:.2f})" if isinstance(max_z, (int, float)) else ""

        console.print(f"\n[bold blue]Analyzing PR #{pr_num}:[/bold blue] {title}")
        console.print(f"Flagged for: {reasons}{z_suffix}")
        console.print(f"Starting isolated agent process (timeout: {timeout}s)...")

        result = analyze_pr_with_timeout(sdk, repo, pr_num, reasons, timeout)
        if result.startswith("Error during analysis:"):
            console.print(f"[red]{result}[/red]")

        report_lines.append(f"## PR #{pr_num}: {title}")
        report_lines.append(f"**Flagged for:** {reasons}{z_suffix}\n")
        report_lines.append(result)
        report_lines.append("\n---\n")

    with open(output, "w") as f:
        f.write("\n".join(report_lines))

    console.print(f"\n[bold green]Analysis complete! Report saved to {output}[/bold green]")

if __name__ == "__main__":
    app()
