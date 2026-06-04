"""Ollama-backed synthesis (default for the live demo).

Runs a local open-source model (qwen2.5:7b by default, llama3.2:3b for weaker
laptops). Because it is local, sensitive portfolio/trade data never leaves the
machine — this is the core mitigation for the external-LLM leakage risk.

Robustness: if Ollama is unreachable, the model isn't pulled, or the request
times out, `generate()` raises and the router transparently falls back to the
MockProvider. The demo therefore cannot hard-fail on a flaky model.
"""
from __future__ import annotations

import httpx

from backend.config import settings
from backend.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout_seconds

    def is_available(self) -> bool:
        """Cheap reachability probe used for status reporting (not the gate)."""
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def generate(self, question: str, tool_result: str) -> str:
        """Call Ollama's /api/generate with a tightly-scoped prompt.

        Raises httpx.HTTPError (or RuntimeError) on any failure so the caller
        can fall back. The model only ever sees the tool output we hand it.
        """
        prompt = self.build_prompt(question, tool_result)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        resp = httpx.post(
            f"{self.base_url}/api/generate", json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        answer = (data.get("response") or "").strip()
        if not answer:
            raise RuntimeError("Ollama returned an empty response")
        return answer
