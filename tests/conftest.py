"""Shared pytest fixtures.

Each test session runs against an isolated, freshly-seeded SQLite database and
forces the deterministic MockProvider so tests never depend on Ollama.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Configure the environment BEFORE importing backend modules (settings is cached).
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from backend.database.db import SessionLocal, init_db  # noqa: E402
from backend.database.seed import seed  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_db():
    init_db()
    db = SessionLocal()
    try:
        seed(db, force=True)
    finally:
        db.close()
    yield
    os.close(_DB_FD)
    if os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)


@pytest.fixture
def client():
    # The app's lifespan re-seeds idempotently; safe with the prepared DB.
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def login(client, email: str) -> dict:
    """Helper: log in and return {'headers':..., 'body':...}."""
    r = client.post("/auth/login", json={"email": email})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"headers": {"Authorization": f"Bearer {body['access_token']}"}, "body": body}
