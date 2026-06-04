"""Dashboard data APIs. Every route is RBAC-guarded server-side via
require_permission(...) — the dashboard cannot bypass these."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.dependencies import require_permission
from backend.database.db import get_db
from backend.tools import portfolio_tools, risk_tools

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    _=Depends(require_permission("portfolio_summary")),
) -> dict:
    return portfolio_tools.get_portfolio_summary(db)


@router.get("/holdings")
def holdings(
    db: Session = Depends(get_db),
    _=Depends(require_permission("holdings")),
) -> dict:
    summary = portfolio_tools.get_portfolio_summary(db)
    exposure = portfolio_tools.get_asset_exposure(db)
    return {"holdings": exposure["by_asset"], "summary": summary}


@router.get("/trades")
def trades(
    db: Session = Depends(get_db),
    _=Depends(require_permission("trades")),
) -> dict:
    return portfolio_tools.get_recent_trades(db, limit=50)


@router.get("/exposure")
def exposure(
    db: Session = Depends(get_db),
    _=Depends(require_permission("exposure")),
) -> dict:
    return portfolio_tools.get_asset_exposure(db)


@router.get("/movers")
def movers(
    db: Session = Depends(get_db),
    _=Depends(require_permission("market_data")),
) -> dict:
    return portfolio_tools.get_top_movers(db, limit=10)


@router.get("/risk-alerts")
def risk_alerts(
    db: Session = Depends(get_db),
    _=Depends(require_permission("risk_alerts")),
) -> dict:
    return risk_tools.get_risk_alerts(db)
