"""Role-Based Access Control matrix and the single permission gate.

RBAC is enforced *server-side only*. The dashboard never decides access; it
merely reflects what the backend allows. This module is the single source of
truth — both the dashboard API routes and the AI agent orchestration call
`check_user_permission()` before any data is read.

Resources (granular, map 1:1 to data the platform can expose):
    portfolio_summary  aggregate book metrics (value, P&L, allocation)
    holdings           raw line-item positions
    trades             raw trade blotter
    market_data        market prices / movers
    exposure           asset/sector exposure (aggregate)
    risk_alerts        flagged trades + risk-rule breaches
    audit_logs         the AI interaction audit trail

Matrix (mirrors the assessment brief):
    analyst  -> portfolio + market data            (NO trades, risk, audit)
    risk     -> portfolio + trades + risk alerts    (+ audit oversight)
    manager  -> summary-only                        (NO raw holdings/trades/risk)
    intern   -> basic portfolio summary only
"""
from __future__ import annotations

# All resources the platform knows how to gate.
RESOURCES = frozenset(
    {
        "portfolio_summary",
        "holdings",
        "trades",
        "market_data",
        "exposure",
        "risk_alerts",
        "audit_logs",
    }
)

ROLES = frozenset({"analyst", "risk", "manager", "intern"})

# The matrix. A role may access exactly the resources in its set.
PERMISSIONS: dict[str, frozenset[str]] = {
    "analyst": frozenset(
        {"portfolio_summary", "holdings", "market_data", "exposure"}
    ),
    "risk": frozenset(
        {
            "portfolio_summary",
            "holdings",
            "trades",
            "market_data",
            "exposure",
            "risk_alerts",
            "audit_logs",
        }
    ),
    # Manager has FULL access (project-owner override). NOTE: this diverges from
    # the assessment brief's "summary-only" manager role — kept here per request.
    "manager": frozenset(RESOURCES),
    # Intern: basic portfolio summary, nothing else.
    "intern": frozenset({"portfolio_summary"}),
}

DENIED_REASON = "insufficient permissions"


def check_user_permission(role: str, resource: str) -> bool:
    """Return True iff `role` may access `resource`. Unknown role/resource -> False.

    This is the hard gate. It is deliberately pure and side-effect free so it
    can be unit-tested in isolation and called from anywhere (API deps, agents).
    """
    if role not in PERMISSIONS or resource not in RESOURCES:
        return False
    return resource in PERMISSIONS[role]


def allowed_resources(role: str) -> list[str]:
    """Sorted list of resources a role may access (used by the dashboard UI)."""
    return sorted(PERMISSIONS.get(role, frozenset()))
