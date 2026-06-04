"""Seed the database with realistic mock data using Faker.

Idempotent: running it when data already exists is a no-op unless `force=True`.
The seed is deterministic (fixed random seed) so demos are reproducible.

Risk flagging is *derived* from the risk_rules table rather than hard-coded,
so the "explain why a trade was flagged" agent answer is grounded in real rules.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from faker import Faker
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.db import SessionLocal, init_db
from backend.models import (
    AuditLog,  # noqa: F401  (ensure table registered)
    MarketPrice,
    PortfolioHolding,
    RiskRule,
    Trade,
    User,
)

# A small, realistic universe of assets across classes.
UNIVERSE = [
    ("AAPL", "Apple Inc.", "equity", "Technology"),
    ("MSFT", "Microsoft Corp.", "equity", "Technology"),
    ("NVDA", "NVIDIA Corp.", "equity", "Technology"),
    ("JPM", "JPMorgan Chase", "equity", "Financials"),
    ("XOM", "Exxon Mobil", "equity", "Energy"),
    ("JNJ", "Johnson & Johnson", "equity", "Healthcare"),
    ("BTC", "Bitcoin", "crypto", "Digital Assets"),
    ("ETH", "Ethereum", "crypto", "Digital Assets"),
    ("US10Y", "US 10Y Treasury", "bond", "Government"),
    ("GLD", "Gold ETF", "commodity", "Commodities"),
    ("USD", "US Dollar Cash", "cash", "Cash"),
]

SEED_USERS = [
    ("analyst@local", "Ana Lyst", "analyst"),
    ("risk@local", "Rick Manager", "risk"),
    ("manager@local", "Meg Anager", "manager"),
    ("intern@local", "Ian Tern", "intern"),
]

RISK_RULES = [
    (
        "CONC-25",
        "Single-Asset Concentration",
        "Flag if a single asset exceeds the threshold percent of total portfolio value.",
        "concentration",
        25.0,
        "high",
    ),
    (
        "NOT-LRG",
        "Large Notional Trade",
        "Flag any single trade whose notional exceeds the threshold (USD).",
        "large_notional",
        500_000.0,
        "high",
    ),
    (
        "MOV-10",
        "Sharp Price Move",
        "Flag trades in assets that moved more than the threshold percent intraday.",
        "price_move",
        10.0,
        "medium",
    ),
    (
        "RESTRICT-CR",
        "Restricted Asset Class",
        "Flag oversized crypto trades pending compliance sign-off.",
        "restricted_asset",
        250_000.0,
        "medium",
    ),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _already_seeded(db: Session) -> bool:
    return db.query(User).count() > 0


def seed(db: Session, *, force: bool = False) -> None:
    """Populate all tables. No-op if already seeded (unless force)."""
    if _already_seeded(db) and not force:
        return

    if force:
        for model in (AuditLog, Trade, MarketPrice, PortfolioHolding, RiskRule, User):
            db.query(model).delete()
        db.commit()

    rng = random.Random(settings.seed_random_seed)
    fake = Faker()
    Faker.seed(settings.seed_random_seed)
    now = _utcnow()

    # --- Users ---
    for email, name, role in SEED_USERS:
        db.add(User(email=email, name=name, role=role))

    # --- Risk rules ---
    rule_by_type: dict[str, RiskRule] = {}
    for code, name, desc, rtype, threshold, severity in RISK_RULES:
        rule = RiskRule(
            code=code,
            name=name,
            description=desc,
            rule_type=rtype,
            threshold=threshold,
            severity=severity,
            enabled=True,
        )
        db.add(rule)
        rule_by_type[rtype] = rule

    # --- Market prices (today's snapshot) ---
    price_map: dict[str, float] = {}
    move_map: dict[str, float] = {}
    for symbol, name, _cls, _sector in UNIVERSE:
        if symbol == "USD":
            price, prev = 1.0, 1.0
        elif symbol == "BTC":
            prev = rng.uniform(55_000, 70_000)
            price = prev * (1 + rng.uniform(-0.15, 0.15))
        elif symbol == "ETH":
            prev = rng.uniform(2_500, 3_800)
            price = prev * (1 + rng.uniform(-0.15, 0.15))
        elif symbol == "US10Y":
            prev = rng.uniform(95, 105)
            price = prev * (1 + rng.uniform(-0.01, 0.01))
        else:
            prev = rng.uniform(80, 450)
            price = prev * (1 + rng.uniform(-0.12, 0.12))
        change_pct = round(((price - prev) / prev) * 100, 2) if prev else 0.0
        price_map[symbol] = round(price, 2)
        move_map[symbol] = change_pct
        db.add(
            MarketPrice(
                asset_symbol=symbol,
                asset_name=name,
                price=round(price, 2),
                prev_close=round(prev, 2),
                change_pct=change_pct,
                volume=rng.randint(100_000, 50_000_000),
                as_of=now,
            )
        )

    # --- Holdings ---
    # Build positions, deliberately overweight one asset (NVDA) to trip CONC-25.
    target_weights = {
        "NVDA": 0.30,  # intentional concentration breach
        "AAPL": 0.14,
        "MSFT": 0.12,
        "BTC": 0.10,
        "JPM": 0.08,
        "ETH": 0.06,
        "XOM": 0.05,
        "JNJ": 0.05,
        "GLD": 0.04,
        "US10Y": 0.04,
        "USD": 0.02,
    }
    total_aum = 10_000_000.0
    holdings: list[PortfolioHolding] = []
    for symbol, name, asset_class, sector in UNIVERSE:
        weight = target_weights.get(symbol, 0.03)
        target_value = total_aum * weight
        price = price_map[symbol]
        qty = round(target_value / price, 4) if price else 0.0
        avg_cost = round(price * rng.uniform(0.80, 1.15), 2)
        h = PortfolioHolding(
            asset_symbol=symbol,
            asset_name=name,
            asset_class=asset_class,
            sector=sector,
            quantity=qty,
            avg_cost=avg_cost,
            current_price=price,
        )
        holdings.append(h)
        db.add(h)

    portfolio_value = sum(h.market_value for h in holdings)

    # --- Trades (with rule-derived flagging) ---
    conc_rule = rule_by_type["concentration"]
    notional_rule = rule_by_type["large_notional"]
    move_rule = rule_by_type["price_move"]
    restrict_rule = rule_by_type["restricted_asset"]

    traders = [fake.first_name() for _ in range(5)]
    n_trades = 45
    for i in range(n_trades):
        symbol, name, asset_class, _sector = rng.choice(UNIVERSE)
        if symbol == "USD":
            symbol, name, asset_class, _sector = UNIVERSE[0]
        side = rng.choice(["buy", "sell"])
        price = price_map[symbol] * (1 + rng.uniform(-0.02, 0.02))
        # Size trades by target NOTIONAL (realistic across all asset classes),
        # then derive quantity from price. This keeps high-priced assets like
        # BTC sensible (a few BTC, not thousands). A subset are deliberately
        # large to trip the large-notional / restricted-crypto rules.
        if i % 11 == 0:
            target_notional = rng.uniform(600_000, 1_200_000)  # trips NOT-LRG (>$500k)
        else:
            target_notional = rng.uniform(20_000, 400_000)
        qty = target_notional / price if price else 0.0
        notional = round(qty * price, 2)
        executed_at = now - timedelta(
            days=rng.randint(0, 14), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
        )

        # Evaluate risk rules in priority order.
        reasons: list[str] = []
        severity = "low"
        if notional > notional_rule.threshold:
            reasons.append(
                f"{notional_rule.code}: notional ${notional:,.0f} exceeds "
                f"${notional_rule.threshold:,.0f}"
            )
            severity = "high"
        if asset_class == "crypto" and notional > restrict_rule.threshold:
            reasons.append(
                f"{restrict_rule.code}: crypto trade ${notional:,.0f} exceeds "
                f"${restrict_rule.threshold:,.0f} (compliance sign-off required)"
            )
            severity = "high" if severity == "high" else "medium"
        if abs(move_map.get(symbol, 0.0)) > move_rule.threshold:
            reasons.append(
                f"{move_rule.code}: {symbol} moved {move_map[symbol]:+.1f}% intraday "
                f"(> {move_rule.threshold:.0f}%)"
            )
            severity = "high" if severity == "high" else "medium"

        risk_flag = bool(reasons)
        status_val = "review" if risk_flag else rng.choice(["settled", "settled", "pending"])

        db.add(
            Trade(
                trade_ref=f"TRD-{1000 + i}",
                asset_symbol=symbol,
                asset_name=name,
                side=side,
                quantity=round(qty, 4),
                price=round(price, 2),
                notional=notional,
                trader=rng.choice(traders),
                status=status_val,
                risk_flag=risk_flag,
                risk_reason=" | ".join(reasons),
                risk_severity=severity,
                executed_at=executed_at,
            )
        )

    # Concentration is a portfolio-level breach; record it as an informational
    # note on the most overweight holding's largest trade context via a synthetic
    # high-risk trade so the risk agent can surface CONC-25 too.
    nvda_value = next((h.market_value for h in holdings if h.asset_symbol == "NVDA"), 0)
    nvda_weight = (nvda_value / portfolio_value * 100) if portfolio_value else 0
    if nvda_weight > conc_rule.threshold:
        db.add(
            Trade(
                trade_ref="TRD-CONC",
                asset_symbol="NVDA",
                asset_name="NVIDIA Corp.",
                side="buy",
                quantity=round(nvda_value / price_map["NVDA"], 4),
                price=price_map["NVDA"],
                notional=round(nvda_value, 2),
                trader="Desk PM",
                status="review",
                risk_flag=True,
                risk_reason=(
                    f"{conc_rule.code}: NVDA is {nvda_weight:.1f}% of portfolio "
                    f"(> {conc_rule.threshold:.0f}% concentration limit)"
                ),
                risk_severity="high",
                executed_at=now - timedelta(hours=2),
            )
        )

    db.commit()


def run() -> None:
    """Entrypoint: create tables then seed (used by `python -m backend.database.seed`)."""
    init_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    run()
    print("Seed complete.")
