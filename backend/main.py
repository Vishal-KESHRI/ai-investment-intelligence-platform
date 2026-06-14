"""FastAPI application entrypoint.

On startup: create tables and seed mock data (idempotent) so the platform is
demo-ready immediately after `docker compose up`.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import agent as agent_api
from backend.api import audit as audit_api
from backend.api import auth as auth_api
from backend.api import dashboard as dashboard_api
from backend.config import settings
from backend.database.db import SessionLocal, init_db
from backend.database.seed import seed
from backend.llm.factory import get_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed(db)  # idempotent
    finally:
        db.close()
    yield


app = FastAPI(
    title="Demo Capital — Local AI Investment Intelligence Platform",
    version="1.0.0",
    description=(
        "Locally runnable AI investment-operations platform: secure AI agents "
        "with tool calling, server-side RBAC, and full audit logging."
    ),
    lifespan=lifespan,
)

# Streamlit talks to the backend; allow local origins (demo).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_api.router)
app.include_router(dashboard_api.router)
app.include_router(agent_api.router)
app.include_router(audit_api.router)


@app.get("/health", tags=["system"])
def health() -> dict:
    """Liveness + LLM provider status (never blocks startup)."""
    provider = get_provider()
    return {
        "status": "ok",
        "llm_provider": provider.name,
        "llm_available": provider.is_available(),
        "model": settings.ollama_model if provider.name == "ollama" else None,
    }


@app.get("/", tags=["system"])
def root() -> dict:
    return {
        "service": "Demo Capital — Local AI Investment Intelligence Platform",
        "docs": "/docs",
        "health": "/health",
    }
