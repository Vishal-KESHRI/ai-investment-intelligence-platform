"""Portfolio Analyst Agent.

Answers: top holdings, asset allocation, biggest movers, performance summary.
Defines its routes as (keyword set -> tool). Routing is deterministic; the LLM
only synthesises prose from the chosen tool's output.
"""
from __future__ import annotations

from backend.tools import portfolio_tools

AGENT_NAME = "portfolio_analyst"


def routes() -> list[dict]:
    """Route specs for this agent. `resource` is the RBAC gate key."""
    return [
        {
            "agent": AGENT_NAME,
            "tool": "get_asset_exposure",
            "resource": "exposure",
            "keywords": {"allocation", "exposure", "overweight", "weight", "diversif",
                         "sector", "breakdown", "composition"},
            "runner": lambda db: portfolio_tools.get_asset_exposure(db),
        },
        {
            "agent": AGENT_NAME,
            "tool": "get_recent_trades",
            "resource": "trades",
            "keywords": {"recent", "blotter", "executed", "last", "latest",
                         "list trades", "show trades", "trade history"},
            "runner": lambda db: portfolio_tools.get_recent_trades(db, limit=15),
        },
        {
            "agent": AGENT_NAME,
            "tool": "get_top_movers",
            "resource": "market_data",
            "keywords": {"move", "moved", "mover", "gain", "lost", "today", "change",
                         "biggest", "volatile", "price"},
            "runner": lambda db: portfolio_tools.get_top_movers(db),
        },
        {
            "agent": AGENT_NAME,
            "tool": "get_portfolio_summary",
            "resource": "portfolio_summary",
            "keywords": {"top", "holding", "holdings", "summary", "summarize",
                         "performance", "overview", "portfolio", "pnl", "p&l",
                         "value", "return", "best", "largest"},
            "runner": lambda db: portfolio_tools.get_portfolio_summary(db),
        },
    ]
