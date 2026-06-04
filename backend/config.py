"""Central configuration, loaded from environment variables.

All secrets and tunables come from the environment (12-factor style).
Sensible local-dev defaults are provided so the project also runs with a
bare `uvicorn backend.main:app` outside Docker.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Database ---
    database_url: str = "sqlite:///./data/arp.db"

    # --- Auth ---
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # --- LLM ---
    # "ollama" (default, local model) or "mock" (deterministic, model-free).
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: int = 30

    # --- Misc ---
    backend_url: str = "http://localhost:8000"
    seed_random_seed: int = 42

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so env is parsed once per process."""
    return Settings()


settings = get_settings()
