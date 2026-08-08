"""LLM provider factory."""

from __future__ import annotations

from pymollm.config import Config
from pymollm.providers.base import LLMClient, Message, ToolCall, ToolSpec, AssistantTurn


def get_client(cfg: Config) -> LLMClient:
    provider = (cfg.provider or "openai").strip().lower()
    api_key = cfg.api_key
    if not api_key:
        raise RuntimeError(
            "No API key configured. Run: llm_config key YOUR_KEY "
            "(and set provider/model as needed)"
        )
    model = cfg.resolved_model()
    if provider in ("openai", "oai"):
        from pymollm.providers.openai_compat import OpenAICompatClient

        return OpenAICompatClient(api_key=api_key, model=model, base_url=cfg.base_url)
    if provider in ("anthropic", "claude"):
        from pymollm.providers.anthropic import AnthropicClient

        return AnthropicClient(api_key=api_key, model=model)
    if provider in ("gemini", "google"):
        from pymollm.providers.gemini import GeminiClient

        return GeminiClient(api_key=api_key, model=model)
    raise ValueError(
        f"Unknown provider '{provider}'. Use: openai, anthropic, or gemini"
    )


__all__ = [
    "get_client",
    "LLMClient",
    "Message",
    "ToolCall",
    "ToolSpec",
    "AssistantTurn",
]
