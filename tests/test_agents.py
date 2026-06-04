"""AI agent routing + tool-calling tests."""
from __future__ import annotations

from backend.agents.router import _classify
from backend.llm.mock_provider import MockProvider
from backend.rag.vector_store import retrieve_policy_context
from tests.conftest import login


# --- Deterministic routing ---
def test_portfolio_question_routes_to_portfolio_tool():
    assert _classify("What are our top holdings?")["agent"] == "portfolio_analyst"
    assert _classify("What is our asset allocation?")["tool"] == "get_asset_exposure"


def test_risk_question_routes_to_risk_tool():
    r = _classify("Which trades are high risk?")
    assert r["agent"] == "risk_compliance"
    assert r["tool"] == "get_risk_alerts"
    assert _classify("Are we overexposed to any asset?")["tool"] == "get_overexposure"
    assert _classify("Explain why a trade was flagged")["tool"] == "explain_trade_flag"


def test_unknown_question_falls_back_to_summary():
    assert _classify("hello there")["tool"] == "get_portfolio_summary"


# --- End-to-end agent answers grounded in DB data ---
def test_agent_answers_top_holdings_from_db(client):
    auth = login(client, "analyst@local")
    r = client.post("/agent/query", json={"question": "What are our top holdings?"},
                    headers=auth["headers"]).json()
    assert r["status"] == "allowed"
    assert r["tool_called"] == "get_portfolio_summary"
    assert r["data"]["top_holdings"]  # real data present
    assert "$" in r["answer"]


def test_agent_answers_high_risk_trades_from_db(client):
    auth = login(client, "risk@local")
    r = client.post("/agent/query", json={"question": "Which trades are high risk?"},
                    headers=auth["headers"]).json()
    assert r["status"] == "allowed"
    assert r["data"]["alert_count"] >= 1


def test_explain_flag_uses_rag_context(client):
    auth = login(client, "risk@local")
    r = client.post("/agent/query", json={"question": "Explain why a trade was flagged"},
                    headers=auth["headers"]).json()
    assert r["status"] == "allowed"
    assert "policy_context" in r["data"]  # RAG grounding attached


def test_rag_retrieval_is_relevant():
    docs = retrieve_policy_context("crypto trade restricted compliance", top_k=2)
    assert docs
    assert any(d["id"] == "RESTRICT-CR" for d in docs)


# --- Mock provider never fabricates: only renders provided data ---
def test_mock_provider_grounded():
    mp = MockProvider()
    out = mp.generate("test", '{"movers": [{"asset_symbol":"AAPL","change_pct":5.0}]}')
    assert "AAPL" in out and "5.0" in out
    empty = mp.generate("test", "{}")
    assert "enough information" in empty.lower()
