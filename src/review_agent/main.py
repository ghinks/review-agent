import typer
from rich.console import Console
from rich.progress import track
from typing import Optional
from google.antigravity import Agent
from .db import get_outliers
from .tools import get_pr_diff, get_pr_comments

app = typer.Typer(help="Agentic Analysis for PR Outliers")
console = Console()

@app.command()
def analyze(
    db_path: str = typer.Option(..., help="Path to the review_classification.db file"),
    repo: str = typer.Option(..., help="GitHub repository name (owner/repo)"),
    output: str = typer.Option("agentic_report.md", help="Output markdown file"),
    limit: Optional[int] = typer.Option(None, help="Limit number of PRs to analyze")
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
    
    agent = Agent(
        model="gemini-3.5-pro",
        system_prompt=(
            "You are an expert code reviewer and engineering manager. "
            "Your task is to analyze Pull Requests that have been statistically flagged as outliers. "
            "Use your tools to read the PR diff and comments. Explain WHY this PR is an outlier "
            "(e.g., was it a difficult refactor? a controversial architectural change?) "
            "and identify any potential risks. Keep the analysis concise and actionable."
        ),
        tools=[get_pr_diff, get_pr_comments]
    )
    
    report_lines = [f"# Agentic Analysis Report for {repo}\n"]
    
    for pr in track(outliers, description="Analyzing PRs..."):
        pr_num = pr['number']
        title = pr['title']
        reasons = pr['outlier_features']
        max_z = pr['max_abs_z_score']
        
        console.print(f"\n[bold blue]Analyzing PR #{pr_num}:[/bold blue] {title}")
        console.print(f"Flagged for: {reasons} (max Z={max_z:.2f})")
        
        prompt = (
            f"Please analyze PR #{pr_num} in repository '{repo}'. "
            f"It was flagged by our statistical analysis for the following reasons: {reasons}. "
            "Investigate the diff and comments to explain this anomaly."
        )
        
        try:
            response = agent.run(prompt)
            # Assuming the response has a .text attribute, or can be cast to string
            result = getattr(response, 'text', str(response))
        except Exception as e:
            result = f"Error during analysis: {e}"
            console.print(f"[red]Error analyzing PR #{pr_num}: {e}[/red]")
            
        report_lines.append(f"## PR #{pr_num}: {title}")
        report_lines.append(f"**Flagged for:** {reasons} (max Z={max_z:.2f})\n")
        report_lines.append(result)
        report_lines.append("\n---\n")
        
    with open(output, "w") as f:
        f.write("\n".join(report_lines))
        
    console.print(f"\n[bold green]Analysis complete! Report saved to {output}[/bold green]")

if __name__ == "__main__":
    app()
