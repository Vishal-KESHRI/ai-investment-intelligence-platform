"""Portfolio data tools. Each returns plain dicts (JSON-serializable) so the
LLM synthesis layer and the API can consume identical structures.

These functions are the ONLY way agents read portfolio data — the flow is
always: Agent -> Tool -> Database -> structured result.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.models import MarketPrice, PortfolioHolding, Trade


def get_portfolio_summary(db: Session) -> dict:
    """Aggregate book metrics: total value, cost, P&L, allocation, top holdings."""
    holdings = db.query(PortfolioHolding).all()
    if not holdings:
        return {"total_market_value": 0, "holdings_count": 0, "top_holdings": []}

    total_mv = sum(h.market_value for h in holdings)
    total_cost = sum(h.cost_basis for h in holdings)
    total_pnl = round(total_mv - total_cost, 2)
    pnl_pct = round((total_pnl / total_cost) * 100, 2) if total_cost else 0.0

    by_class: dict[str, float] = defaultdict(float)
    for h in holdings:
        by_class[h.asset_class] += h.market_value
    allocation = [
        {
            "asset_class": cls,
            "market_value": round(val, 2),
            "weight_pct": round(val / total_mv * 100, 2) if total_mv else 0.0,
        }
        for cls, val in sorted(by_class.items(), key=lambda kv: -kv[1])
    ]

    ranked = sorted(holdings, key=lambda h: h.market_value, reverse=True)
    top_holdings = [
        {
            "asset_symbol": h.asset_symbol,
            "asset_name": h.asset_name,
            "asset_class": h.asset_class,
            "market_value": h.market_value,
            "weight_pct": round(h.market_value / total_mv * 100, 2) if total_mv else 0.0,
            "unrealized_pnl": h.unrealized_pnl,
            "unrealized_pnl_pct": h.unrealized_pnl_pct,
        }
        for h in ranked[:5]
    ]

    return {
        "total_market_value": round(total_mv, 2),
        "total_cost_basis": round(total_cost, 2),
        "total_unrealized_pnl": total_pnl,
        "total_unrealized_pnl_pct": pnl_pct,
        "holdings_count": len(holdings),
        "allocation_by_class": allocation,
        "top_holdings": top_holdings,
    }


def get_asset_exposure(db: Session) -> dict:
    """Exposure by individual asset and by sector, as % of total book value."""
    holdings = db.query(PortfolioHolding).all()
    total_mv = sum(h.market_value for h in holdings) or 1.0

    by_asset = [
        {
            "asset_symbol": h.asset_symbol,
            "asset_name": h.asset_name,
            "asset_class": h.asset_class,
            "sector": h.sector,
            "market_value": h.market_value,
            "exposure_pct": round(h.market_value / total_mv * 100, 2),
        }
        for h in sorted(holdings, key=lambda h: h.market_value, reverse=True)
    ]

    by_sector_map: dict[str, float] = defaultdict(float)
    for h in holdings:
        by_sector_map[h.sector] += h.market_value
    by_sector = [
        {"sector": s, "market_value": round(v, 2), "exposure_pct": round(v / total_mv * 100, 2)}
        for s, v in sorted(by_sector_map.items(), key=lambda kv: -kv[1])
    ]

    return {
        "total_market_value": round(total_mv, 2),
        "by_asset": by_asset,
        "by_sector": by_sector,
    }


def get_recent_trades(db: Session, limit: int = 15) -> dict:
    """Most recent trades (the blotter)."""
    limit = max(1, min(limit, 100))
    trades = (
        db.query(Trade).order_by(desc(Trade.executed_at)).limit(limit).all()
    )
    rows = [
        {
            "trade_ref": t.trade_ref,
            "asset_symbol": t.asset_symbol,
            "asset_name": t.asset_name,
            "side": t.side,
            "quantity": t.quantity,
            "price": t.price,
            "notional": t.notional,
            "trader": t.trader,
            "status": t.status,
            "risk_flag": t.risk_flag,
            "risk_severity": t.risk_severity,
            "executed_at": t.executed_at.isoformat(),
        }
        for t in trades
    ]
    return {"count": len(rows), "trades": rows}


def get_top_movers(db: Session, limit: int = 5) -> dict:
    """Assets with the largest absolute intraday price move (market data)."""
    prices = db.query(MarketPrice).all()
    ranked = sorted(prices, key=lambda p: abs(p.change_pct), reverse=True)
    movers = [
        {
            "asset_symbol": p.asset_symbol,
            "asset_name": p.asset_name,
            "price": p.price,
            "prev_close": p.prev_close,
            "change_pct": p.change_pct,
        }
        for p in ranked[:limit]
    ]
    return {"movers": movers}
