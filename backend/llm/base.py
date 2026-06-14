"""LLMProvider interface.

The platform depends on this abstraction, never on a concrete model. This is
deliberate dependency inversion:

  * In the live demo we run OllamaProvider (a real local model — no data leaves
    the laptop, satisfying the "external LLM data leakage" concern).
  * In CI/tests we run MockProvider (deterministic, zero dependencies, cannot
    hard-fail).
  * In production you would add e.g. a VPC-hosted provider — one new class plus
    one env var, no changes to agents/tools.

It also enforces the project's thesis: *orchestration and tool-calling matter
more than model quality*. RBAC, tool routing, and DB access are all deterministic
code; the LLM only synthesises a natural-language answer from tool output it is
given. The LLM never decides permissions and never sees data it isn't handed.
"""
from __future__ import annotations

import abc

# Shared system prompt. The model is constrained to the tool output only.
SYSTEM_PROMPT = (
    "You are an investment operations assistant for Demo Capital.\n"
    "Use ONLY the provided tool output. Do not invent financial data.\n"
    "If the tool output does not contain enough information, say so clearly.\n"
    "Be concise, factual, and professional."
)

PROMPT_TEMPLATE = (
    "{system}\n\n"
    "Question:\n{question}\n\n"
    "Tool Output (the only data you may use):\n{tool_result}\n\n"
    "Answer:"
)


class LLMProvider(abc.ABC):
    """Abstract synthesis backend. Turns (question, tool_result) into prose."""

    name: str = "base"

    @abc.abstractmethod
    def generate(self, question: str, tool_result: str) -> str:
        """Return a natural-language answer grounded in `tool_result`."""

    def is_available(self) -> bool:  # pragma: no cover - overridden where relevant
        """Whether this provider can currently serve requests."""
        return True

    def build_prompt(self, question: str, tool_result: str) -> str:
        return PROMPT_TEMPLATE.format(
            system=SYSTEM_PROMPT, question=question, tool_result=tool_result
        )
