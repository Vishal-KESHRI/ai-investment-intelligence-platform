"""Audit logging tests — every interaction (allowed AND denied) is recorded."""
from __future__ import annotations

from backend.audit.logger import list_logs
from tests.conftest import login


def _count(db):
    return len(list_logs(db, limit=1000))


def test_allowed_query_creates_audit_log(client, db):
    before = _count(db)
    auth = login(client, "analyst@local")
    r = client.post("/agent/query", json={"question": "What are our top holdings?"},
                    headers=auth["headers"])
    assert r.json()["status"] == "allowed"
    logs = list_logs(db, limit=1000)
    assert len(logs) == before + 1
    latest = logs[0]
    assert latest.decision == "allowed"
    assert latest.user_email == "analyst@local"
    assert latest.tool_called == "get_portfolio_summary"
    assert latest.timestamp is not None


def test_denied_query_creates_audit_log(client, db):
    before = _count(db)
    auth = login(client, "intern@local")
    r = client.post("/agent/query", json={"question": "Which trades are high risk?"},
                    headers=auth["headers"])
    assert r.json()["status"] == "denied"
    logs = list_logs(db, limit=1000)
    assert len(logs) == before + 1
    latest = logs[0]
    assert latest.decision == "denied"
    assert latest.reason == "insufficient permissions"
    assert latest.tool_called  # the attempted tool is still recorded


def test_audit_includes_tool_and_timestamp(client, db):
    auth = login(client, "risk@local")
    client.post("/agent/query", json={"question": "Are we overexposed to any asset?"},
                headers=auth["headers"])
    latest = list_logs(db, limit=1)[0]
    assert latest.tool_called == "get_overexposure"
    assert latest.timestamp is not None


def test_audit_api_rbac(client):
    # risk may view; intern may not.
    risk = login(client, "risk@local")
    assert client.get("/audit/logs", headers=risk["headers"]).status_code == 200
    intern = login(client, "intern@local")
    assert client.get("/audit/logs", headers=intern["headers"]).status_code == 403


def test_audit_api_returns_logs(client):
    auth = login(client, "risk@local")
    # ensure at least one interaction exists
    client.post("/agent/query", json={"question": "Which trades are high risk?"},
                headers=auth["headers"])
    logs = client.get("/audit/logs", headers=auth["headers"]).json()
    assert isinstance(logs, list) and len(logs) >= 1
    assert {"user_email", "role", "question", "tool_called", "decision", "timestamp"} <= set(logs[0])
