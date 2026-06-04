"""Trade model — executed orders, some flagged for risk review."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.db import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_ref: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    asset_symbol: Mapped[str] = mapped_column(String, index=True, nullable=False)
    asset_name: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)  # buy | sell
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    notional: Mapped[float] = mapped_column(Float, nullable=False)
    trader: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # settled | pending | review
    # Risk flagging — set by the seed logic against risk_rules thresholds.
    risk_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_reason: Mapped[str] = mapped_column(String, default="", nullable=False)
    # low | medium | high
    risk_severity: Mapped[str] = mapped_column(String, default="low", nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
