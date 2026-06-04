"""Deterministic, model-free synthesis.

Proves the project's point: a useful answer can be produced purely from
structured tool output via templating — no model required. Used in CI/tests and
as the runtime fallback when Ollama is unavailable, so the demo NEVER hard-fails.
"""
from __future__ import annotations

import json

from backend.llm.base import LLMProvider


class MockProvider(LLMProvider):
    name = "mock"

    def is_available(self) -> bool:
        return True

    def generate(self, question: str, tool_result: str) -> str:
        """Render a readable summary from the structured tool result.

        We parse the JSON tool output and produce a grounded, human-friendly
        paragraph. We never fabricate numbers — everything comes from the data.
        """
        try:
            data = json.loads(tool_result)
        except (json.JSONDecodeError, TypeError):
            return tool_result.strip() or "No data available to answer the question."

        lines = self._summarize(data)
        if not lines:
            return (
                "The tool returned data but it did not contain enough information "
                "to answer the question."
            )
        return "\n".join(lines)

    # --- shape-aware summarizers (grounded in tool output only) ---
    def _summarize(self, d: dict) -> list[str]:
        out: list[str] = []

        if "top_holdings" in d:
            mv = d.get("total_market_value", 0)
            pnl = d.get("total_unrealized_pnl", 0)
            pnl_pct = d.get("total_unrealized_pnl_pct", 0)
            out.append(
                f"Portfolio market value is ${mv:,.0f} across "
                f"{d.get('holdings_count', 0)} holdings, with unrealized P&L of "
                f"${pnl:,.0f} ({pnl_pct:+.2f}%)."
            )
            if d.get("allocation_by_class"):
                alloc = ", ".join(
                    f"{a['asset_class']} {a['weight_pct']:.1f}%"
                    for a in d["allocation_by_class"]
                )
                out.append(f"Allocation by class: {alloc}.")
            if d.get("top_holdings"):
                tops = "; ".join(
                    f"{h['asset_symbol']} (${h['market_value']:,.0f}, "
                    f"{h['weight_pct']:.1f}%)"
                    for h in d["top_holdings"]
                )
                out.append(f"Top holdings: {tops}.")

        if "by_sector" in d and "by_asset" in d:
            top = d["by_asset"][0] if d["by_asset"] else None
            if top:
                out.append(
                    f"Largest single-asset exposure is {top['asset_symbol']} at "
                    f"{top['exposure_pct']:.1f}% of the book."
                )
            sec = ", ".join(
                f"{s['sector']} {s['exposure_pct']:.1f}%" for s in d["by_sector"][:5]
            )
            out.append(f"Sector exposure: {sec}.")

        if "movers" in d:
            if d["movers"]:
                mv = "; ".join(
                    f"{m['asset_symbol']} {m['change_pct']:+.2f}%" for m in d["movers"]
                )
                out.append(f"Biggest movers today: {mv}.")
            else:
                out.append("No market movement data is available.")

        if "alerts" in d:
            out.append(
                f"There are {d.get('alert_count', 0)} flagged trade(s). "
                f"Severity breakdown: {d.get('severity_breakdown', {})}."
            )
            for a in d["alerts"][:5]:
                out.append(
                    f"- {a['trade_ref']} {a['asset_symbol']} "
                    f"(${a['notional']:,.0f}, {a['risk_severity']}): {a['risk_reason']}"
                )

        if "breaches" in d:
            out.append(
                f"{d.get('breach_count', 0)} asset(s) exceed the "
                f"{d.get('concentration_limit_pct')}% concentration limit"
                + (f" (rule {d.get('rule_code')})." if d.get("rule_code") else ".")
            )
            for b in d["breaches"]:
                out.append(
                    f"- {b['asset_symbol']} at {b['exposure_pct']:.1f}% "
                    f"(${b['market_value']:,.0f})"
                )

        if "cited_rules" in d and d.get("found"):
            out.append(
                f"Trade {d['trade_ref']} ({d['asset_symbol']}, "
                f"${d['notional']:,.0f}) was flagged [{d['risk_severity']}]: "
                f"{d['risk_reason']}."
            )
            for r in d["cited_rules"]:
                out.append(f"- Rule {r['code']} — {r['name']}: {r['description']}")
        elif d.get("found") is False:
            out.append(d.get("message", "No matching flagged trade was found."))

        if "trades" in d and "alerts" not in d and "breaches" not in d:
            out.append(f"Found {d.get('count', len(d['trades']))} trade(s).")
            for t in d["trades"][:8]:
                flag = " [FLAGGED]" if t.get("risk_flag") else ""
                out.append(
                    f"- {t['trade_ref']} {t.get('side','').upper()} "
                    f"{t['asset_symbol']} ${t['notional']:,.0f} "
                    f"({t.get('status','')}){flag}"
                )

        return out
