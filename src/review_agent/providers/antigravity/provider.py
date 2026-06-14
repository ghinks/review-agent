"""Gemini backend via the google-antigravity SDK.

The SDK runs its own agentic loop (``agent.chat``), so this provider only has
to build the agent with our GitHub tools and hand it the prompt.
"""

import os

from google.antigravity import Agent, CapabilitiesConfig, LocalAgentConfig

from review_agent.prompts import SYSTEM_INSTRUCTIONS, build_prompt
from review_agent.tools import get_pr_comments, get_pr_diff

# Remove ANTIGRAVITY_HARNESS_PATH if it points to the CLI wrapper 'agy'
# so the SDK will auto-discover the correct localharness binary. Done at
# import time, which only happens when this backend is actually selected.
if os.environ.get("ANTIGRAVITY_HARNESS_PATH", "").endswith("agy"):
    del os.environ["ANTIGRAVITY_HARNESS_PATH"]

MODEL = "gemini-2.5-pro"


class AntigravityProvider:
    """Analyzes a PR using a Gemini agent."""

    def _create_agent(self) -> Agent:
        return Agent(
            config=LocalAgentConfig(
                model=MODEL,
                system_instructions=SYSTEM_INSTRUCTIONS,
                capabilities=CapabilitiesConfig(enabled_tools=[]),
                tools=[get_pr_diff, get_pr_comments],
            )
        )

    async def analyze(self, repo: str, pr_num: int, reasons: str) -> str:
        agent = self._create_agent()
        prompt = build_prompt(repo, pr_num, reasons)
        async with agent:
            response = await agent.chat(prompt)
            return await response.text()
