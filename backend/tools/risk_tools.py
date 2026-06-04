"""Risk & compliance data tools."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.models import PortfolioHolding, RiskRule, Trade


def get_risk_alerts(db: Session) -> dict:
    """All flagged trades plus the active risk rules they were tested against."""
    flagged = (
        db.query(Trade)
        .filter(Trade.risk_flag.is_(True))
        .order_by(desc(Trade.risk_severity), desc(Trade.notional))
        .all()
    )
    alerts = [
        {
            "trade_ref": t.trade_ref,
            "asset_symbol": t.asset_symbol,
            "asset_name": t.asset_name,
            "side": t.side,
            "notional": t.notional,
            "risk_severity": t.risk_severity,
            "risk_reason": t.risk_reason,
            "status": t.status,
            "executed_at": t.executed_at.isoformat(),
        }
        for t in flagged
    ]
    rules = [
        {
            "code": r.code,
            "name": r.name,
            "rule_type": r.rule_type,
            "threshold": r.threshold,
            "severity": r.severity,
        }
        for r in db.query(RiskRule).filter(RiskRule.enabled.is_(True)).all()
    ]
    severity_counts: dict[str, int] = defaultdict(int)
    for a in alerts:
        severity_counts[a["risk_severity"]] += 1

    return {
        "alert_count": len(alerts),
        "severity_breakdown": dict(severity_counts),
        "alerts": alerts,
        "active_rules": rules,
    }


def get_overexposure(db: Session, threshold_pct: float | None = None) -> dict:
    """Assets exceeding the concentration limit (defaults to the CONC rule)."""
    conc_rule = (
        db.query(RiskRule).filter(RiskRule.rule_type == "concentration").first()
    )
    limit = threshold_pct if threshold_pct is not None else (
        conc_rule.threshold if conc_rule else 25.0
    )

    holdings = db.query(PortfolioHolding).all()
    total_mv = sum(h.market_value for h in holdings) or 1.0
    breaches = [
        {
            "asset_symbol": h.asset_symbol,
            "asset_name": h.asset_name,
            "exposure_pct": round(h.market_value / total_mv * 100, 2),
            "market_value": h.market_value,
            "limit_pct": limit,
        }
        for h in holdings
        if (h.market_value / total_mv * 100) > limit
    ]
    breaches.sort(key=lambda b: b["exposure_pct"], reverse=True)
    return {
        "concentration_limit_pct": limit,
        "rule_code": conc_rule.code if conc_rule else None,
        "breach_count": len(breaches),
        "breaches": breaches,
    }


def get_trades_for_review(db: Session) -> dict:
    """Trades whose status is 'review' or 'pending' — the compliance queue."""
    rows = (
        db.query(Trade)
        .filter(Trade.status.in_(["review", "pending"]))
        .order_by(desc(Trade.notional))
        .all()
    )
    out = [
        {
            "trade_ref": t.trade_ref,
            "asset_symbol": t.asset_symbol,
            "notional": t.notional,
            "status": t.status,
            "risk_flag": t.risk_flag,
            "risk_severity": t.risk_severity,
            "risk_reason": t.risk_reason,
        }
        for t in rows
    ]
    return {"count": len(out), "trades": out}


def explain_trade_flag(db: Session, trade_ref: str | None = None) -> dict:
    """Explain why a specific trade (or the highest-severity flagged trade) was flagged."""
    q = db.query(Trade).filter(Trade.risk_flag.is_(True))
    if trade_ref:
        trade = q.filter(Trade.trade_ref == trade_ref.upper()).first()
    else:
        trade = q.order_by(desc(Trade.notional)).first()

    if not trade:
        return {"found": False, "message": "No flagged trade matched the request."}

    # Map the reason back to the originating rule(s) for grounded explanation.
    rules = {r.code: r for r in db.query(RiskRule).all()}
    cited = [
        {"code": r.code, "name": r.name, "description": r.description, "threshold": r.threshold}
        for code, r in rules.items()
        if code in (trade.risk_reason or "")
    ]
    return {
        "found": True,
        "trade_ref": trade.trade_ref,
        "asset_symbol": trade.asset_symbol,
        "notional": trade.notional,
        "risk_severity": trade.risk_severity,
        "risk_reason": trade.risk_reason,
        "cited_rules": cited,
    }
