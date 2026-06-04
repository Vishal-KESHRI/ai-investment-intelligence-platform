"""Risk & Compliance Agent.

Answers: overexposure, high-risk trades, trades needing review, explain-a-flag.
Uses RAG (vector_store) to ground 'explain' answers in policy text.
"""
from __future__ import annotations

from backend.tools import risk_tools

AGENT_NAME = "risk_compliance"


def routes() -> list[dict]:
    return [
        {
            "agent": AGENT_NAME,
            "tool": "get_overexposure",
            "resource": "risk_alerts",
            "keywords": {"overexposed", "overexposure", "concentration", "too much",
                         "limit", "exceed", "breach"},
            "runner": lambda db: risk_tools.get_overexposure(db),
        },
        {
            "agent": AGENT_NAME,
            "tool": "get_trades_for_review",
            "resource": "risk_alerts",
            "keywords": {"review", "pending", "queue", "approve", "sign-off",
                         "signoff", "need"},
            "runner": lambda db: risk_tools.get_trades_for_review(db),
        },
        {
            "agent": AGENT_NAME,
            "tool": "explain_trade_flag",
            "resource": "risk_alerts",
            "keywords": {"explain", "why", "reason", "flagged", "flag"},
            "runner": lambda db: risk_tools.explain_trade_flag(db),
            "rag": True,  # augment with retrieved policy context
        },
        {
            "agent": AGENT_NAME,
            "tool": "get_risk_alerts",
            "resource": "risk_alerts",
            "keywords": {"risk", "high", "risky", "alert", "dangerous", "compliance",
                         "violation", "trades"},
            "runner": lambda db: risk_tools.get_risk_alerts(db),
        },
    ]
