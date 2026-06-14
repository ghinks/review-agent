"""GPT backend via the OpenAI SDK.

Implements the agentic loop by hand against the Responses API: call the model,
execute any ``function_call`` items it emits against our GitHub tools, append
the results, and repeat until no more function calls are requested. Auth comes
from ``OPENAI_API_KEY`` in the environment.
"""

import json
from typing import Any, Callable, cast

from openai import AsyncOpenAI
from openai.types.responses import ResponseInputParam, ToolParam

from review_agent.prompts import SYSTEM_INSTRUCTIONS, build_prompt
from review_agent.tools import get_pr_comments, get_pr_diff

# gpt-5.5 is the newer model; override here if desired.
MODEL = "gpt-5"

# Map tool name -> implementation. Both take (repo_name, pr_number).
TOOL_IMPLS: dict[str, Callable[..., str]] = {
    "get_pr_diff": get_pr_diff,
    "get_pr_comments": get_pr_comments,
}

# Responses API tool schemas (flat shape — no nested "function" key).
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "get_pr_diff",
        "description": "Fetches the raw unified diff of a GitHub Pull Request.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_name": {"type": "string", "description": "Repository as 'owner/repo'."},
                "pr_number": {"type": "integer", "description": "The pull request number."},
            },
            "required": ["repo_name", "pr_number"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_pr_comments",
        "description": "Fetches the title, body, and review/issue comments for a GitHub Pull Request.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_name": {"type": "string", "description": "Repository as 'owner/repo'."},
                "pr_number": {"type": "integer", "description": "The pull request number."},
            },
            "required": ["repo_name", "pr_number"],
            "additionalProperties": False,
        },
    },
]


class OpenAIProvider:
    """Analyzes a PR using a GPT agent with a manual tool-calling loop."""

    async def analyze(self, repo: str, pr_num: int, reasons: str) -> str:
        client = AsyncOpenAI()
        input_items: list[Any] = [
            {"role": "user", "content": build_prompt(repo, pr_num, reasons)}
        ]

        while True:
            response = await client.responses.create(
                model=MODEL,
                instructions=SYSTEM_INSTRUCTIONS,
                tools=cast(list[ToolParam], TOOLS),
                input=cast(ResponseInputParam, input_items),
            )

            function_calls = [
                item for item in response.output if item.type == "function_call"
            ]
            if not function_calls:
                return response.output_text

            # Carry the model's turn (including the function_call items) forward.
            input_items += response.output

            for call in function_calls:
                impl = TOOL_IMPLS[call.name]
                args: dict[str, Any] = json.loads(call.arguments)
                result = impl(**args)
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": result,
                    }
                )
