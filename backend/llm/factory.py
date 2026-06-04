"""Provider selection + resilient synthesis.

`synthesize()` is what agents call. It picks the configured provider, and if
that provider fails at request time (e.g. Ollama down / model not pulled), it
transparently falls back to the MockProvider and reports which one answered.
"""
from __future__ import annotations

from backend.config import settings
from backend.llm.base import LLMProvider
from backend.llm.mock_provider import MockProvider
from backend.llm.ollama_provider import OllamaProvider

_mock = MockProvider()


def get_provider(name: str | None = None) -> LLMProvider:
    """Return the configured provider instance (does not probe availability)."""
    choice = (name or settings.llm_provider or "mock").lower()
    if choice == "ollama":
        return OllamaProvider()
    return _mock


def synthesize(question: str, tool_result: str) -> tuple[str, str]:
    """Generate an answer, falling back to mock on any provider error.

    Returns (answer, provider_name_that_actually_answered).
    """
    provider = get_provider()
    if provider.name == "mock":
        return provider.generate(question, tool_result), "mock"

    try:
        return provider.generate(question, tool_result), provider.name
    except Exception:  # noqa: BLE001 — any provider failure must degrade gracefully
        # Fallback keeps the demo alive; we annotate the provider so the UI/audit
        # can show that mock answered.
        return _mock.generate(question, tool_result), f"mock (fallback from {provider.name})"
