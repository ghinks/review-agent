"""Provider abstraction: a uniform contract over each LLM SDK backend."""

from enum import Enum
from typing import Protocol


class Sdk(str, Enum):
    """The reasoning SDK to use for analyzing a PR."""

    antigravity = "antigravity"
    openai = "openai"
    anthropic = "anthropic"


class AgentProvider(Protocol):
    """An LLM backend that investigates a single outlier PR and explains it.

    Implementations run their own agentic loop, calling the GitHub tools in
    ``review_agent.tools`` to fetch the diff and comments, and return the
    model's final natural-language analysis.
    """

    async def analyze(self, repo: str, pr_num: int, reasons: str) -> str: ...
