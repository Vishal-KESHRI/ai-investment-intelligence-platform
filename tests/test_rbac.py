"""RBAC enforcement tests — the security-critical behaviour from the brief."""
from __future__ import annotations

from backend.auth.permissions import check_user_permission
from tests.conftest import login


# --- Pure unit tests on the permission gate ---
def test_matrix_analyst():
    assert check_user_permission("analyst", "portfolio_summary")
    assert check_user_permission("analyst", "market_data")
    assert not check_user_permission("analyst", "risk_alerts")
    assert not check_user_permission("analyst", "trades")
    assert not check_user_permission("analyst", "audit_logs")


def test_matrix_risk():
    assert check_user_permission("risk", "risk_alerts")
    assert check_user_permission("risk", "trades")
    assert check_user_permission("risk", "audit_logs")


def test_matrix_manager_summary_only():
    assert check_user_permission("manager", "portfolio_summary")
    assert not check_user_permission("manager", "trades")
    assert not check_user_permission("manager", "holdings")


def test_matrix_intern_minimal():
    assert check_user_permission("intern", "portfolio_summary")
    assert not check_user_permission("intern", "trades")
    assert not check_user_permission("intern", "risk_alerts")
    assert not check_user_permission("intern", "audit_logs")


def test_unknown_role_or_resource_denied():
    assert not check_user_permission("hacker", "portfolio_summary")
    assert not check_user_permission("analyst", "nonexistent")


# --- End-to-end RBAC over HTTP ---
def test_protected_route_requires_token(client):
    assert client.get("/dashboard/summary").status_code == 403  # no bearer


def test_analyst_cannot_access_risk_alerts(client):
    auth = login(client, "analyst@local")
    assert client.get("/dashboard/risk-alerts", headers=auth["headers"]).status_code == 403


def test_intern_cannot_access_trades(client):
    auth = login(client, "intern@local")
    assert client.get("/dashboard/trades", headers=auth["headers"]).status_code == 403


def test_risk_user_can_access_risk_alerts(client):
    auth = login(client, "risk@local")
    r = client.get("/dashboard/risk-alerts", headers=auth["headers"])
    assert r.status_code == 200
    assert "alerts" in r.json()


def test_manager_summary_allowed_but_holdings_denied(client):
    auth = login(client, "manager@local")
    assert client.get("/dashboard/summary", headers=auth["headers"]).status_code == 200
    assert client.get("/dashboard/holdings", headers=auth["headers"]).status_code == 403


def test_agent_denial_returns_clean_payload(client):
    auth = login(client, "analyst@local")
    r = client.post("/agent/query", json={"question": "Which trades are high risk?"},
                    headers=auth["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "denied"
    assert body["reason"] == "insufficient permissions"
