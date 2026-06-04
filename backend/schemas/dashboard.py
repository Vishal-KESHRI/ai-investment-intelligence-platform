"""Dashboard response schemas. Kept permissive (dict-based) where the shape
is aggregate/derived; explicit where it aids the frontend."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HoldingOut(BaseModel):
    asset_symbol: str
    asset_name: str
    asset_class: str
    sector: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class TradeOut(BaseModel):
    trade_ref: str
    asset_symbol: str
    asset_name: str
    side: str
    quantity: float
    price: float
    notional: float
    trader: str
    status: str
    risk_flag: bool
    risk_reason: str
    risk_severity: str
    executed_at: datetime


class RiskAlertOut(BaseModel):
    trade_ref: str
    asset_symbol: str
    notional: float
    risk_severity: str
    risk_reason: str
    status: str
    executed_at: datetime


class AuditLogOut(BaseModel):
    id: int
    user_email: str
    role: str
    question: str
    agent: str
    tool_called: str
    decision: str
    reason: str
    timestamp: datetime
