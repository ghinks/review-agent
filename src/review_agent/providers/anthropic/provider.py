"""Claude backend via the Anthropic SDK.

Implements the agentic loop by hand: call the Messages API, execute any
``tool_use`` blocks against our GitHub tools, feed the results back, and repeat
until Claude stops calling tools. Auth comes from ``ANTHROPIC_API_KEY`` in the
environment (the SDK's default credential resolution).
"""

from typing import Any, Callable, cast

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolParam

from review_agent.prompts import SYSTEM_INSTRUCTIONS, build_prompt
from review_agent.tools import get_pr_comments, get_pr_diff

MODEL = "claude-opus-4-8"
MAX_TOKENS = 8000

# Map tool name -> implementation. Both take (repo_name, pr_number).
TOOL_IMPLS: dict[str, Callable[..., str]] = {
    "get_pr_diff": get_pr_diff,
    "get_pr_comments": get_pr_comments,
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_pr_diff",
        "description": "Fetches the raw unified diff of a GitHub Pull Request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_name": {
                    "type": "string",
                    "description": "Repository as 'owner/repo'.",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "The pull request number.",
                },
            },
            "required": ["repo_name", "pr_number"],
        },
    },
    {
        "name": "get_pr_comments",
        "description": "Fetches the title, body, and review/issue comments for a GitHub Pull Request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_name": {
                    "type": "string",
                    "description": "Repository as 'owner/repo'.",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "The pull request number.",
                },
            },
            "required": ["repo_name", "pr_number"],
        },
    },
]


class AnthropicProvider:
    """Analyzes a PR using a Claude agent with a manual tool-use loop."""

    async def analyze(self, repo: str, pr_num: int, reasons: str) -> str:
        client = AsyncAnthropic()
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": build_prompt(repo, pr_num, reasons)}
        ]

        while True:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_INSTRUCTIONS,
                tools=cast(list[ToolParam], TOOLS),
                messages=cast(list[MessageParam], messages),
            )

            if response.stop_reason != "tool_use":
                return "".join(
                    block.text for block in response.content if block.type == "text"
                )

            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                impl = TOOL_IMPLS[block.name]
                args: dict[str, Any] = dict(block.input)  # type: ignore[arg-type]
                result = impl(**args)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})
