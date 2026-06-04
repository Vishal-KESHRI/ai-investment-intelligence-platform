"""ARP Global Capital — Streamlit dashboard.

A thin client over the FastAPI backend. It stores a JWT in session state and
calls the backend for everything; it NEVER decides access itself — RBAC is
enforced server-side and the UI simply renders whatever the backend allows
(or a clean 'permission denied' banner when it doesn't).
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

USERS = {
    "analyst@local": "Portfolio Analyst — portfolio + market data",
    "risk@local": "Risk & Compliance — portfolio + trades + risk",
    "manager@local": "Manager — summary-only",
    "intern@local": "Intern — basic summary only",
}

ROLE_COLORS = {
    "analyst": "#2563eb",
    "risk": "#dc2626",
    "manager": "#7c3aed",
    "intern": "#6b7280",
}

st.set_page_config(
    page_title="ARP Global Capital — AI Investment Intelligence",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem;}
      .role-badge {display:inline-block;padding:4px 12px;border-radius:14px;
                   color:white;font-weight:600;font-size:0.85rem;}
      .denied {background:#fef2f2;border:1px solid #fecaca;color:#991b1b;
               padding:12px 16px;border-radius:8px;font-weight:500;}
      .allowed {background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;
                padding:12px 16px;border-radius:8px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------- session helpers ---------------------------
def _init_state() -> None:
    st.session_state.setdefault("token", None)
    st.session_state.setdefault("email", None)
    st.session_state.setdefault("role", None)
    st.session_state.setdefault("allowed", [])


def _auth_header() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def api_get(path: str):
    """GET with auth. Returns (ok, payload_or_status)."""
    try:
        r = requests.get(f"{BACKEND_URL}{path}", headers=_auth_header(), timeout=15)
    except requests.RequestException as e:
        return False, f"backend unreachable: {e}"
    if r.status_code == 200:
        return True, r.json()
    if r.status_code == 403:
        return False, "denied"
    return False, f"error {r.status_code}"


def login(email: str) -> str | None:
    try:
        r = requests.post(f"{BACKEND_URL}/auth/login", json={"email": email}, timeout=15)
    except requests.RequestException as e:
        return f"Backend unreachable: {e}"
    if r.status_code != 200:
        return f"Login failed: {r.json().get('detail', r.status_code)}"
    data = r.json()
    st.session_state.token = data["access_token"]
    st.session_state.email = data["email"]
    st.session_state.role = data["role"]
    st.session_state.allowed = data["allowed_resources"]
    return None


def denied_banner(msg: str = "Permission denied — your role cannot access this data.") -> None:
    st.markdown(f'<div class="denied">🔒 {msg}</div>', unsafe_allow_html=True)


# --------------------------- sidebar / login ---------------------------
_init_state()

with st.sidebar:
    st.title("📊 ARP Global Capital")
    st.caption("Local AI Investment Intelligence")

    if st.session_state.token:
        role = st.session_state.role
        color = ROLE_COLORS.get(role, "#374151")
        st.markdown(
            f'<span class="role-badge" style="background:{color}">{role.upper()}</span>',
            unsafe_allow_html=True,
        )
        st.write(f"**{st.session_state.email}**")
        st.caption("Allowed: " + ", ".join(st.session_state.allowed))
        if st.button("Log out", use_container_width=True):
            for k in ("token", "email", "role", "allowed"):
                st.session_state[k] = None if k != "allowed" else []
            st.rerun()
    else:
        st.subheader("Login (demo)")
        email = st.selectbox("Select user", list(USERS.keys()),
                             format_func=lambda e: f"{e} — {USERS[e]}")
        if st.button("Login", type="primary", use_container_width=True):
            err = login(email)
            if err:
                st.error(err)
            else:
                st.rerun()

    st.divider()
    ok, health = api_get("/health") if st.session_state.token else (False, None)
    if isinstance(health, dict):
        prov = health.get("llm_provider")
        avail = "🟢" if health.get("llm_available") else "🟡 (mock fallback)"
        st.caption(f"LLM: **{prov}** {avail}")


if not st.session_state.token:
    st.title("Welcome to ARP Global Capital")
    st.info("👈 Select a demo user and log in from the sidebar to begin.")
    st.markdown(
        "This platform demonstrates **secure AI investment operations**: "
        "AI agents with tool calling, **server-side RBAC**, and **full audit logging** — "
        "all running locally."
    )
    st.stop()


# --------------------------- pages ---------------------------
page = st.sidebar.radio(
    "Navigate",
    ["Portfolio Overview", "Trades", "AI Assistant", "Audit Logs"],
)


def render_portfolio() -> None:
    st.header("Portfolio Overview")
    ok, summary = api_get("/dashboard/summary")
    if not ok:
        denied_banner() if summary == "denied" else st.error(summary)
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market Value", f"${summary['total_market_value']:,.0f}")
    c2.metric("Unrealized P&L", f"${summary['total_unrealized_pnl']:,.0f}",
              f"{summary['total_unrealized_pnl_pct']:+.2f}%")
    c3.metric("Holdings", summary["holdings_count"])
    c4.metric("Cost Basis", f"${summary['total_cost_basis']:,.0f}")

    left, right = st.columns(2)
    with left:
        st.subheader("Allocation by Asset Class")
        alloc = pd.DataFrame(summary["allocation_by_class"])
        if not alloc.empty:
            fig = px.pie(alloc, names="asset_class", values="market_value", hole=0.45)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=340)
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Asset Exposure")
        ok_e, exposure = api_get("/dashboard/exposure")
        if ok_e:
            ex = pd.DataFrame(exposure["by_asset"])
            fig = px.bar(ex, x="asset_symbol", y="exposure_pct", color="asset_class",
                         labels={"exposure_pct": "% of book", "asset_symbol": ""})
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=340)
            st.plotly_chart(fig, use_container_width=True)
        elif exposure == "denied":
            denied_banner("Exposure data not available for your role.")

    st.subheader("Top Holdings")
    tops = pd.DataFrame(summary["top_holdings"])
    if not tops.empty:
        st.dataframe(tops, use_container_width=True, hide_index=True)

    # Holdings table (only roles with 'holdings' will get data)
    st.subheader("All Holdings")
    ok_h, holdings = api_get("/dashboard/holdings")
    if ok_h:
        st.dataframe(pd.DataFrame(holdings["holdings"]), use_container_width=True,
                     hide_index=True)
    elif holdings == "denied":
        denied_banner("Detailed line-item holdings are restricted for your role "
                      "(summary metrics above are permitted).")


def render_trades() -> None:
    st.header("Trades")
    ok, trades = api_get("/dashboard/trades")
    if not ok:
        denied_banner("Trade blotter is restricted for your role.") if trades == "denied" \
            else st.error(trades)
    else:
        df = pd.DataFrame(trades["trades"])
        st.subheader(f"Recent Trades ({trades['count']})")
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Risk Alerts")
    ok_r, alerts = api_get("/dashboard/risk-alerts")
    if ok_r:
        st.markdown(f"**{alerts['alert_count']}** flagged trades — "
                    f"{alerts['severity_breakdown']}")
        st.dataframe(pd.DataFrame(alerts["alerts"]), use_container_width=True,
                     hide_index=True)
    elif alerts == "denied":
        denied_banner("Risk alerts are restricted for your role.")


EXAMPLE_QUESTIONS = [
    "What are our top holdings?",
    "What is our asset allocation?",
    "Which assets moved the most today?",
    "Summarize portfolio performance",
    "Are we overexposed to any asset?",
    "Which trades are high risk?",
    "Which trades need review?",
    "Explain why a trade was flagged",
]


def _call_agent(question: str) -> dict:
    """Call the backend agent and return a normalized assistant-message dict."""
    try:
        r = requests.post(f"{BACKEND_URL}/agent/query", json={"question": question},
                          headers=_auth_header(), timeout=120)
    except requests.RequestException as e:
        return {"role": "assistant", "content": f"Backend unreachable: {e}",
                "denied": True, "caption": None, "data": None}
    if r.status_code != 200:
        return {"role": "assistant", "content": f"Error {r.status_code}: {r.text}",
                "denied": True, "caption": None, "data": None}
    res = r.json()
    denied = res["status"] == "denied"
    if denied:
        caption = (f"Routed to {res['agent']} / {res['tool_called']} — "
                   "this denial is recorded in the audit log.")
    else:
        caption = (f"Agent: {res['agent']} · Tool: {res['tool_called']} · "
                   f"LLM: {res['llm_provider']}")
    return {"role": "assistant", "content": res["answer"], "denied": denied,
            "caption": caption, "data": res.get("data")}


def _render_message(m: dict) -> None:
    with st.chat_message(m["role"], avatar="🧑‍💼" if m["role"] == "user" else "🤖"):
        if m["role"] == "assistant" and m.get("denied"):
            st.markdown(f'<div class="denied">🔒 {m["content"]}</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(m["content"])
        if m.get("caption"):
            st.caption(m["caption"])
        if m.get("data"):
            with st.expander("Tool output (raw data the answer is grounded in)"):
                st.json(m["data"])


def render_ai() -> None:
    st.header("🤖 AI Assistant")
    st.caption("Chat with the Portfolio Analyst & Risk agents. Answers come only "
               "from database tool output, gated by your role.")

    st.session_state.setdefault("chat", [])

    top = st.columns([1, 1, 4])
    if top[0].button("🗑 Clear chat", use_container_width=True):
        st.session_state.chat = []
        st.rerun()

    # Suggested questions (collapsed once a conversation is underway).
    with st.expander("💡 Example questions", expanded=not st.session_state.chat):
        cols = st.columns(2)
        for i, ex in enumerate(EXAMPLE_QUESTIONS):
            if cols[i % 2].button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state.pending_q = ex

    # Render the conversation so far.
    for m in st.session_state.chat:
        _render_message(m)

    # New input: from the chat box or a clicked example.
    typed = st.chat_input("Ask about holdings, allocation, risk, trades…")
    question = typed or st.session_state.pop("pending_q", None)
    if question:
        user_msg = {"role": "user", "content": question}
        st.session_state.chat.append(user_msg)
        _render_message(user_msg)
        with st.chat_message("assistant", avatar="🤖"), st.spinner("Thinking…"):
            assistant_msg = _call_agent(question)
            # Render inline now; the history loop will show it on the next run.
            if assistant_msg.get("denied"):
                st.markdown(f'<div class="denied">🔒 {assistant_msg["content"]}</div>',
                            unsafe_allow_html=True)
            else:
                st.markdown(assistant_msg["content"])
            if assistant_msg.get("caption"):
                st.caption(assistant_msg["caption"])
            if assistant_msg.get("data"):
                with st.expander("Tool output (raw data the answer is grounded in)"):
                    st.json(assistant_msg["data"])
        st.session_state.chat.append(assistant_msg)


def render_audit() -> None:
    st.header("Audit Logs")
    st.caption("Every AI interaction — allowed and denied — is logged here.")
    ok, logs = api_get("/audit/logs")
    if not ok:
        denied_banner("Audit logs are restricted to risk and manager roles.") \
            if logs == "denied" else st.error(logs)
        return
    if not logs:
        st.info("No interactions logged yet. Ask the AI Assistant a few questions.")
        return
    df = pd.DataFrame(logs)[
        ["timestamp", "user_email", "role", "question", "agent", "tool_called",
         "decision", "reason"]
    ]
    a, d = (df["decision"] == "allowed").sum(), (df["decision"] == "denied").sum()
    c1, c2 = st.columns(2)
    c1.metric("Allowed", int(a))
    c2.metric("Denied", int(d))

    def _style(row):
        color = "#f0fdf4" if row["decision"] == "allowed" else "#fef2f2"
        return [f"background-color: {color}"] * len(row)

    st.dataframe(df.style.apply(_style, axis=1), use_container_width=True, hide_index=True)


PAGES = {
    "Portfolio Overview": render_portfolio,
    "Trades": render_trades,
    "AI Assistant": render_ai,
    "Audit Logs": render_audit,
}
PAGES[page]()
