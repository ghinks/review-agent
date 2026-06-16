"""Shared prompt text used by every SDK provider.

Keeping this SDK-agnostic ensures Gemini, GPT, and Claude all reason over
identical instructions and input for a given PR.
"""

SYSTEM_INSTRUCTIONS = (
    "You are an expert code reviewer and engineering manager. "
    "Your task is to analyze Pull Requests that have been flagged for review. "
    "Use your tools to read the PR diff and comments. Explain WHY this PR stands out "
    "(e.g., was it a difficult refactor? a controversial architectural change?) "
    "and identify any potential risks. Keep the analysis concise and actionable."
)


def build_prompt(repo: str, pr_num: int, reasons: str) -> str:
    """Builds the per-PR user prompt handed to the agent."""
    return (
        f"Please analyze PR #{pr_num} in repository '{repo}'. "
        f"Context for why it was selected: {reasons}. "
        "Investigate the diff and comments to explain any anomalies and identify risks."
    )
