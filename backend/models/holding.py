"""Portfolio holdings — current positions in the book."""
from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.db import Base


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_symbol: Mapped[str] = mapped_column(String, index=True, nullable=False)
    asset_name: Mapped[str] = mapped_column(String, nullable=False)
    # equity | crypto | bond | commodity | cash
    asset_class: Mapped[str] = mapped_column(String, index=True, nullable=False)
    sector: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)

    @property
    def market_value(self) -> float:
        return round(self.quantity * self.current_price, 2)

    @property
    def cost_basis(self) -> float:
        return round(self.quantity * self.avg_cost, 2)

    @property
    def unrealized_pnl(self) -> float:
        return round(self.market_value - self.cost_basis, 2)

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return round((self.unrealized_pnl / self.cost_basis) * 100, 2)
