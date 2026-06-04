import asyncio
import multiprocessing as mp
import os
from queue import Empty
from typing import Any, Optional

import typer
from rich.console import Console
from rich.progress import track

from google.antigravity import Agent, CapabilitiesConfig, LocalAgentConfig
from review_agent.db import get_outliers
from review_agent.tools import get_pr_diff, get_pr_comments

# Remove ANTIGRAVITY_HARNESS_PATH if it points to the CLI wrapper 'agy'
# so the SDK will auto-discover the correct localharness binary.
if os.environ.get("ANTIGRAVITY_HARNESS_PATH", "").endswith("agy"):
    del os.environ["ANTIGRAVITY_HARNESS_PATH"]

app = typer.Typer(help="Agentic Analysis for PR Outliers")
console = Console()


SYSTEM_INSTRUCTIONS = (
    "You are an expert code reviewer and engineering manager. "
    "Your task is to analyze Pull Requests that have been statistically flagged as outliers. "
    "Use your tools to read the PR diff and comments. Explain WHY this PR is an outlier "
    "(e.g., was it a difficult refactor? a controversial architectural change?) "
    "and identify any potential risks. Keep the analysis concise and actionable."
)


def create_agent() -> Agent:
    return Agent(
        config=LocalAgentConfig(
            model="gemini-2.5-pro",
            system_instructions=SYSTEM_INSTRUCTIONS,
            capabilities=CapabilitiesConfig(enabled_tools=[]),
            tools=[get_pr_diff, get_pr_comments],
        )
    )


async def run_single_agent_analysis(repo: str, pr_num: int, reasons: str) -> str:
    agent = create_agent()
    prompt = (
        f"Please analyze PR #{pr_num} in repository '{repo}'. "
        f"It was flagged by our statistical analysis for the following reasons: {reasons}. "
        "Investigate the diff and comments to explain this anomaly."
    )

    async with agent:
        response = await agent.chat(prompt)
        return await response.text()


def agent_worker(repo: str, pr_num: int, reasons: str, queue: mp.Queue) -> None:
    try:
        result = asyncio.run(run_single_agent_analysis(repo, pr_num, reasons))
    except Exception as e:
        queue.put({"ok": False, "result": f"Error during analysis: {e}"})
    else:
        queue.put({"ok": True, "result": result})


def analyze_pr_with_timeout(repo: str, pr_num: int, reasons: str, timeout: int) -> str:
    queue: mp.Queue[dict[str, Any]] = mp.Queue()
    process = mp.Process(target=agent_worker, args=(repo, pr_num, reasons, queue))
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
        
    console.print(f"Found {len(outliers)} outlier PRs to analyze.")
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
        
        result = analyze_pr_with_timeout(repo, pr_num, reasons, timeout)
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
