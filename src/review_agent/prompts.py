"""Shared prompt text used by every SDK provider.

Keeping this SDK-agnostic ensures Gemini, GPT, and Claude all reason over
identical instructions and input for a given PR.
"""

SYSTEM_INSTRUCTIONS = (
    "You are an expert code reviewer and engineering manager. "
    "Your task is to analyze Pull Requests that have been statistically flagged as outliers. "
    "Use your tools to read the PR diff and comments. Explain WHY this PR is an outlier "
    "(e.g., was it a difficult refactor? a controversial architectural change?) "
    "and identify any potential risks. Keep the analysis concise and actionable."
)


def build_prompt(repo: str, pr_num: int, reasons: str) -> str:
    """Builds the per-PR user prompt handed to the agent."""
    return (
        f"Please analyze PR #{pr_num} in repository '{repo}'. "
        f"It was flagged by our statistical analysis for the following reasons: {reasons}. "
        "Investigate the diff and comments to explain this anomaly."
    )
