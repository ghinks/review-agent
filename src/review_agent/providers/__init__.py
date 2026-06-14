"""Provider registry.

``get_provider`` lazily imports the selected backend so that choosing one SDK
never imports the others — callers only need the SDK and API key for the
backend they actually use.
"""

from review_agent.providers.base import AgentProvider, Sdk

__all__ = ["AgentProvider", "Sdk", "get_provider"]


def get_provider(sdk: Sdk) -> AgentProvider:
    """Returns the provider implementation for the given SDK."""
    if sdk is Sdk.antigravity:
        from review_agent.providers.antigravity.provider import AntigravityProvider

        return AntigravityProvider()
    if sdk is Sdk.openai:
        from review_agent.providers.openai.provider import OpenAIProvider

        return OpenAIProvider()
    if sdk is Sdk.anthropic:
        from review_agent.providers.anthropic.provider import AnthropicProvider

        return AnthropicProvider()
    raise ValueError(f"Unknown SDK: {sdk}")
