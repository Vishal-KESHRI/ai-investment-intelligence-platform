"""ARP Global Capital — Streamlit dashboard.

A thin, professional client over the FastAPI backend. It stores a JWT in session
state and calls the backend for everything; it NEVER decides access itself —
RBAC is enforced server-side and the UI simply renders whatever the backend
allows (or an accessible 'permission denied' card when it doesn't).

Design goals: a clean financial-grade visual system, accessible status cues
(icon + text + colour, never colour alone), consistent charts, and tables with
proper currency / percentage formatting.
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# --- Design tokens ---------------------------------------------------------
BRAND = {
    "navy": "#0F172A",
    "primary": "#2563EB",
    "muted": "#64748B",
    "border": "#E2E8F0",
    "surface": "#FFFFFF",
    "bg": "#F1F5F9",
    "pos": "#16A34A",
    "neg": "#DC2626",
    "warn": "#D97706",
}

# Role identity: colour + icon + human label (icon/text => not colour-only).
ROLE_META = {
    "analyst": {"color": "#2563EB", "icon": "📈", "label": "Portfolio Analyst"},
    "risk": {"color": "#DC2626", "icon": "🛡️", "label": "Risk & Compliance"},
    "manager": {"color": "#7C3AED", "icon": "🗂️", "label": "Manager"},
    "intern": {"color": "#475569", "icon": "🎓", "label": "Intern"},
}

USERS = {
    "analyst@local": "Portfolio + market data",
    "risk@local": "Portfolio + trades + risk alerts",
    "manager@local": "Full access",
    "intern@local": "Basic portfolio summary",
}

# Consistent asset-class palette used across every chart.
ASSET_COLORS = {
    "equity": "#2563EB",
    "crypto": "#F59E0B",
    "bond": "#10B981",
    "commodity": "#8B5CF6",
    "cash": "#64748B",
}

st.set_page_config(
    page_title="ARP Global Capital — AI Investment Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",  # expanded on desktop, auto-collapses on mobile
)


def inject_css() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

          html, body, [class*="css"], .stApp { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
          .stApp { background: #F1F5F9; }

          /* Hide Streamlit chrome for a product-grade feel */
          [data-testid="stToolbar"], [data-testid="stDecoration"], footer { visibility: hidden; height: 0; }
          #MainMenu { visibility: hidden; }
          .block-container { padding-top: 2.6rem; padding-bottom: 3rem; max-width: 1320px; }

          /* Accessible focus ring on every interactive element */
          a:focus-visible, button:focus-visible, input:focus-visible,
          select:focus-visible, [tabindex]:focus-visible {
            outline: 3px solid #2563EB; outline-offset: 2px; border-radius: 6px;
          }

          h1, h2, h3 { color: #0F172A; font-weight: 700; letter-spacing: -0.01em; }

          /* Page header band */
          .page-head { display:flex; align-items:center; gap:14px; margin-bottom:.4rem; }
          .page-head .ph-icon { font-size:1.9rem; line-height:1; }
          .page-head .ph-title { font-size:1.55rem; font-weight:800; color:#0F172A; margin:0; }
          .page-head .ph-sub { color:#64748B; font-size:.92rem; margin:.1rem 0 0; }

          /* KPI metric cards */
          [data-testid="stMetric"] {
            background:#fff; border:1px solid #E2E8F0; border-radius:14px;
            padding:16px 18px; box-shadow:0 1px 3px rgba(16,24,40,.06);
          }
          [data-testid="stMetricLabel"] p {
            color:#64748B; font-weight:600; font-size:.74rem;
            text-transform:uppercase; letter-spacing:.05em;
          }
          [data-testid="stMetricValue"] { color:#0F172A; font-weight:800; font-size:1.55rem; }

          /* Bordered containers as cards */
          [data-testid="stVerticalBlockBorderWrapper"] {
            background:#fff; border-radius:14px; border:1px solid #E2E8F0;
            box-shadow:0 1px 3px rgba(16,24,40,.05);
          }

          /* Sidebar — light & high-contrast (WCAG AA dark text on white) */
          [data-testid="stSidebar"] { background:#FFFFFF; border-right:1px solid #E2E8F0; }
          [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 { color:#0F172A; }
          [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:#64748B; }
          /* Nav radio options: comfortable, clearly clickable rows */
          [data-testid="stSidebar"] [role="radiogroup"] label {
            padding:8px 10px; border-radius:9px; font-weight:600; color:#0F172A;
          }
          [data-testid="stSidebar"] [role="radiogroup"] label:hover { background:#F1F5F9; }

          /* Buttons */
          .stButton > button {
            border-radius:10px; font-weight:600; border:1px solid #E2E8F0;
            transition: transform .04s ease, box-shadow .12s ease;
          }
          .stButton > button:hover { box-shadow:0 2px 8px rgba(37,99,235,.18); }
          .stButton > button:active { transform: translateY(1px); }
          .stButton > button[kind="primary"] { background:#2563EB; border-color:#2563EB; }

          /* Dataframe polish */
          [data-testid="stDataFrame"] { border-radius:12px; border:1px solid #E2E8F0; overflow:hidden; }

          /* Chat bubbles */
          [data-testid="stChatMessage"] { background:#fff; border:1px solid #E2E8F0; border-radius:14px; }

          /* Status pills + cards (icon + text, accessible) */
          .pill { display:inline-flex; align-items:center; gap:6px; padding:4px 12px;
                  border-radius:999px; font-weight:700; font-size:.8rem; }
          .role-badge { display:inline-flex; align-items:center; gap:8px; padding:7px 14px;
                        border-radius:999px; color:#fff; font-weight:700; font-size:.9rem; }
          .denied-card { background:#FEF2F2; border:1px solid #FECACA; color:#991B1B;
                         padding:14px 16px; border-radius:12px; font-weight:500; display:flex;
                         align-items:flex-start; gap:10px; }
          .allowed-card { background:#F0FDF4; border:1px solid #BBF7D0; color:#14532D;
                          padding:14px 16px; border-radius:12px; }
          .hero { background:linear-gradient(135deg,#0F172A 0%, #1E3A8A 100%); color:#fff;
                  border-radius:18px; padding:36px 40px; margin-bottom:22px; }
          .hero h1 { color:#fff; font-size:2rem; margin:0 0 6px; }
          .hero p { color:#CBD5E1; margin:0; font-size:1rem; }
          .feat { background:#fff; border:1px solid #E2E8F0; border-radius:12px; padding:16px 18px; height:100%; }
          .feat .ft { font-weight:700; color:#0F172A; margin-bottom:4px; }
          .feat .fb { color:#64748B; font-size:.88rem; }

          /* ---- Landing page ---- */
          .brandbar { display:flex; align-items:center; gap:10px; font-weight:800;
                      font-size:1.15rem; color:#0F172A; margin-bottom:14px; }
          .brandbar .dot { width:30px; height:30px; border-radius:8px;
                           background:linear-gradient(135deg,#2563EB,#1E3A8A);
                           display:inline-flex; align-items:center; justify-content:center; }
          .hero-lg { background:radial-gradient(1200px 400px at 90% -10%, #2563EB33, transparent),
                     linear-gradient(135deg,#0F172A 0%, #15296b 55%, #1E40AF 100%);
                     color:#fff; border-radius:24px; padding:52px 56px;
                     box-shadow:0 20px 45px rgba(15,23,42,.28); }
          .hero-lg .eyebrow { letter-spacing:.14em; text-transform:uppercase;
                     font-size:.76rem; color:#93C5FD; font-weight:700; }
          .hero-lg h1 { color:#fff; font-size:2.5rem; line-height:1.08;
                     margin:12px 0 14px; max-width:640px; font-weight:800;
                     letter-spacing:-0.02em; }
          .hero-lg p { color:#CBD5E1; font-size:1.06rem; max-width:600px; margin:0; }
          .stat-row { display:flex; gap:40px; margin-top:30px; }
          .stat .n { font-size:1.5rem; font-weight:800; color:#fff; }
          .stat .l { color:#93C5FD; font-size:.78rem; text-transform:uppercase;
                     letter-spacing:.06em; }
          .f-item { display:flex; gap:14px; align-items:flex-start; padding:15px 2px;
                    border-bottom:1px solid #E8EDF3; }
          .f-item:last-child { border-bottom:none; }
          .f-ic { font-size:1.45rem; line-height:1.2; }
          .f-t { font-weight:700; color:#0F172A; font-size:.98rem; }
          .f-d { color:#64748B; font-size:.88rem; margin-top:1px; }
          .signin-head { font-size:1.15rem; font-weight:800; color:#0F172A; }
          .signin-sub { color:#64748B; font-size:.88rem; margin-bottom:6px; }
          .landing-foot { text-align:center; color:#94A3B8; font-size:.82rem;
                          margin-top:30px; }

          /* ---- Responsive ---- */
          /* Phones: stack every column group to a single column */
          @media (max-width: 640px) {
            [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: .6rem; }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
            [data-testid="stHorizontalBlock"] > [data-testid="column"] {
              flex: 1 1 100% !important; width: 100% !important; min-width: 100% !important;
            }
            .block-container { padding: 1.3rem .8rem 2rem; }
            .hero-lg { padding: 30px 22px; }
            .hero-lg h1 { font-size: 1.7rem; }
            .hero-lg p { font-size: .95rem; }
            .stat-row { gap: 20px; flex-wrap: wrap; }
            .page-head .ph-title { font-size: 1.25rem; }
            [data-testid="stMetricValue"] { font-size: 1.3rem; }
          }
          /* Tablets: two-up grid (KPIs 2x2, side-by-side panels reflow) */
          @media (min-width: 641px) and (max-width: 992px) {
            [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
            [data-testid="stHorizontalBlock"] > [data-testid="column"] {
              flex: 1 1 calc(50% - 1rem) !important; min-width: calc(50% - 1rem) !important;
            }
            .hero-lg { padding: 40px 36px; }
            .hero-lg h1 { font-size: 2.1rem; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()


# --- Formatting & chart helpers -------------------------------------------
def fmt_money(v: float) -> str:
    """Compact, finance-style currency: $3.00M, $204.5K, $980."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:.2f}B"
    if a >= 1e6:
        return f"${v / 1e6:.2f}M"
    if a >= 1e3:
        return f"${v / 1e3:.1f}K"
    return f"${v:,.0f}"


def style_fig(fig, height: int = 340):
    fig.update_layout(
        height=height,
        margin=dict(t=20, b=8, l=8, r=8),
        font=dict(family="Inter, sans-serif", size=13, color=BRAND["navy"]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, x=0,
                    font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", font_size=12,
                        font_family="Inter, sans-serif"),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EEF2F6", zeroline=False)
    return fig


SEVERITY = {"high": "🔴 High", "medium": "🟠 Medium", "low": "🟢 Low"}


def page_header(icon: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="page-head"><div class="ph-icon">{icon}</div>'
        f'<div><p class="ph-title">{title}</p>'
        f'<p class="ph-sub">{subtitle}</p></div></div>',
        unsafe_allow_html=True,
    )


def denied_card(msg: str) -> None:
    st.markdown(
        f'<div class="denied-card" role="alert" aria-label="Access denied">'
        f'<span aria-hidden="true">🔒</span><div><b>Access denied.</b> {msg}</div></div>',
        unsafe_allow_html=True,
    )


# --- Session / auth --------------------------------------------------------
def _init_state() -> None:
    st.session_state.setdefault("token", None)
    st.session_state.setdefault("email", None)
    st.session_state.setdefault("role", None)
    st.session_state.setdefault("allowed", [])


def _auth_header() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def api_get(path: str):
    """GET with auth. Returns (ok, payload | 'denied' | error-string)."""
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


_init_state()


LOGIN_ORDER = ["analyst@local", "risk@local", "manager@local", "intern@local"]

LANDING_FEATURES = [
    ("🤖", "AI Agents with Tool Calling",
     "Portfolio Analyst & Risk agents answer questions using only real database data."),
    ("🔐", "Role-Based Access Control",
     "Every request is gated server-side. The UI reflects access — it never decides it."),
    ("📝", "Full Audit Trail",
     "Every AI interaction, allowed and denied, is logged with user, role, tool and time."),
    ("🏠", "Runs Fully Local",
     "No data leaves the machine; a local LLM powers synthesis with a safe fallback."),
]


def render_login() -> None:
    # Hide the sidebar entirely on the landing page for a focused experience.
    st.markdown(
        "<style>[data-testid='stSidebar'],[data-testid='collapsedControl']"
        "{display:none !important;}</style>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="brandbar"><span class="dot">📊</span> ARP Global Capital</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="hero-lg">'
        '<div class="eyebrow">Local AI Investment Intelligence</div>'
        '<h1>Secure AI for investment operations</h1>'
        '<p>AI agents with tool calling, server-side role-based access control, and '
        'full audit logging — running entirely on local infrastructure.</p>'
        '<div class="stat-row">'
        '<div class="stat"><div class="n">2</div><div class="l">AI Agents</div></div>'
        '<div class="stat"><div class="n">4</div><div class="l">Roles (RBAC)</div></div>'
        '<div class="stat"><div class="n">100%</div><div class="l">Local & Audited</div></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.write("")

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("##### Why this platform")
            for ic, t, d in LANDING_FEATURES:
                st.markdown(
                    f'<div class="f-item"><div class="f-ic">{ic}</div>'
                    f'<div><div class="f-t">{t}</div><div class="f-d">{d}</div></div></div>',
                    unsafe_allow_html=True,
                )
    with right:
        with st.container(border=True):
            st.markdown('<div class="signin-head">Sign in</div>', unsafe_allow_html=True)
            st.markdown('<div class="signin-sub">Choose a demo role to explore the platform.</div>',
                        unsafe_allow_html=True)
            for email in LOGIN_ORDER:
                meta = ROLE_META[email.split("@")[0]]
                if st.button(f"{meta['icon']}  {meta['label']}  ·  {email}",
                             key=f"login_{email}", use_container_width=True):
                    err = login(email)
                    if err:
                        st.error(err)
                    else:
                        st.rerun()
                st.caption(USERS[email])

    st.markdown(
        '<div class="landing-foot">FastAPI · SQLite · Streamlit · Ollama · '
        'Docker — assessment build for ARP Global Capital</div>',
        unsafe_allow_html=True,
    )


# --- Login landing (no sidebar) -------------------------------------------
if not st.session_state.token:
    render_login()
    st.stop()


# --- Sidebar (authenticated) ----------------------------------------------
with st.sidebar:
    st.markdown("## 📊 ARP Global Capital")
    st.caption("Local AI Investment Intelligence")
    st.divider()

    role = st.session_state.role
    meta = ROLE_META.get(role, {"color": "#334155", "icon": "👤", "label": role})
    st.markdown(
        f'<span class="role-badge" style="background:{meta["color"]}" '
        f'aria-label="Signed in as {meta["label"]}">{meta["icon"]} {meta["label"]}</span>',
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown(f"**{st.session_state.email}**")
    st.caption("Permissions: " + ", ".join(st.session_state.allowed))
    if st.button("Log out", use_container_width=True):
        for k in ("token", "email", "role"):
            st.session_state[k] = None
        st.session_state.allowed = []
        st.session_state.pop("chat", None)
        st.rerun()
    st.divider()

    ok, health = api_get("/health")
    if isinstance(health, dict):
        prov = health.get("llm_provider")
        dot = "🟢" if health.get("llm_available") else "🟡"
        extra = f" · {health.get('model')}" if health.get("model") else " · mock fallback"
        st.caption(f"{dot} LLM engine: **{prov}**{extra}")


# --- Pages -----------------------------------------------------------------
page = st.sidebar.radio(
    "Navigate",
    ["📊 Portfolio Overview", "💹 Trades", "🤖 AI Assistant", "📝 Audit Logs"],
    label_visibility="collapsed",
)


def render_portfolio() -> None:
    page_header("📊", "Portfolio Overview", "Allocation, exposure and holdings at a glance.")
    ok, summary = api_get("/dashboard/summary")
    if not ok:
        denied_card("Portfolio summary is not available for your role.") if summary == "denied" \
            else st.error(summary)
        return

    pnl = summary["total_unrealized_pnl"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market Value", fmt_money(summary["total_market_value"]))
    c2.metric("Unrealized P&L", fmt_money(pnl),
              f"{summary['total_unrealized_pnl_pct']:+.2f}%")
    c3.metric("Holdings", summary["holdings_count"])
    c4.metric("Cost Basis", fmt_money(summary["total_cost_basis"]))

    st.write("")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("##### Allocation by Asset Class")
            alloc = pd.DataFrame(summary["allocation_by_class"])
            if not alloc.empty:
                fig = px.pie(alloc, names="asset_class", values="market_value", hole=0.62,
                             color="asset_class", color_discrete_map=ASSET_COLORS)
                fig.update_traces(textinfo="percent", textfont_size=12,
                                  marker=dict(line=dict(color="#fff", width=2)))
                fig.add_annotation(
                    text=f"<b>{fmt_money(summary['total_market_value'])}</b>"
                         f"<br><span style='font-size:11px;color:#64748B'>Total</span>",
                    showarrow=False, font=dict(size=17, color=BRAND["navy"]))
                st.plotly_chart(style_fig(fig), use_container_width=True,
                                config={"displayModeBar": False})

    with right:
        with st.container(border=True):
            st.markdown("##### Asset Exposure")
            ok_e, exposure = api_get("/dashboard/exposure")
            if ok_e:
                ex = pd.DataFrame(exposure["by_asset"])
                fig = px.bar(ex, x="asset_symbol", y="exposure_pct", color="asset_class",
                             color_discrete_map=ASSET_COLORS, text="exposure_pct")
                fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                                  cliponaxis=False, textfont_size=11)
                fig.update_yaxes(title="% of book", ticksuffix="%",
                                 range=[0, float(ex["exposure_pct"].max()) * 1.18])
                fig.update_xaxes(title="")
                fig = style_fig(fig)
                fig.update_layout(margin=dict(t=24, b=24, l=8, r=8),
                                  legend=dict(y=-0.32))
                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar": False})
            elif exposure == "denied":
                denied_card("Exposure data is not available for your role.")

    with st.container(border=True):
        st.markdown("##### Top Holdings")
        tops = pd.DataFrame(summary["top_holdings"])
        if not tops.empty:
            tops = tops.sort_values("market_value", ascending=False)
            tops_disp = pd.DataFrame({
                "Symbol": tops["asset_symbol"],
                "Name": tops["asset_name"],
                "Class": tops["asset_class"],
                "Market Value": tops["market_value"].map(fmt_money),
                "Weight": tops["weight_pct"],
                "Unrealized P&L": tops["unrealized_pnl"].map(fmt_money),
                "Return": tops["unrealized_pnl_pct"],
            })
            st.dataframe(
                tops_disp, use_container_width=True, hide_index=True,
                column_config={
                    "Weight": st.column_config.ProgressColumn(
                        "Weight", min_value=0, max_value=float(tops["weight_pct"].max()),
                        format="%.1f%%"),
                    "Return": st.column_config.NumberColumn("Return", format="%.2f%%"),
                },
            )

    with st.container(border=True):
        st.markdown("##### All Holdings")
        ok_h, holdings = api_get("/dashboard/holdings")
        if ok_h:
            h = pd.DataFrame(holdings["holdings"])
            h = h.sort_values("market_value", ascending=False)
            disp = pd.DataFrame({
                "Symbol": h["asset_symbol"], "Name": h["asset_name"],
                "Class": h["asset_class"], "Sector": h["sector"],
                "Market Value": h["market_value"].map(fmt_money),
                "Exposure": h["exposure_pct"],
            })
            st.dataframe(
                disp, use_container_width=True, hide_index=True,
                column_config={
                    "Exposure": st.column_config.ProgressColumn(
                        "Exposure", min_value=0,
                        max_value=float(h["exposure_pct"].max()), format="%.1f%%"),
                },
            )
        elif holdings == "denied":
            denied_card("Detailed line-item holdings are restricted for your role "
                        "(the summary metrics above are permitted).")


def render_trades() -> None:
    page_header("💹", "Trades", "Recent execution blotter and risk alerts.")
    ok, trades = api_get("/dashboard/trades")
    if not ok:
        denied_card("The trade blotter is restricted for your role.") if trades == "denied" \
            else st.error(trades)
    else:
        df = pd.DataFrame(trades["trades"])
        flagged = int(df["risk_flag"].sum()) if not df.empty else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Recent Trades", trades["count"])
        c2.metric("Flagged", flagged)
        c3.metric("High Severity",
                  int((df["risk_severity"] == "high").sum()) if not df.empty else 0)
        c4.metric("Total Notional", fmt_money(df["notional"].sum()) if not df.empty else "$0")

        st.write("")
        with st.container(border=True):
            st.markdown("##### Recent Trades")
            disp = pd.DataFrame({
                "Ref": df["trade_ref"], "Symbol": df["asset_symbol"],
                "Side": df["side"].str.capitalize(),
                "Notional": df["notional"].map(fmt_money),
                "Status": df["status"].str.capitalize(),
                "Risk": df.apply(
                    lambda r: SEVERITY.get(r["risk_severity"], "—") if r["risk_flag"]
                    else "—", axis=1),
            })
            st.dataframe(disp, use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.markdown("##### Risk Alerts")
        ok_r, alerts = api_get("/dashboard/risk-alerts")
        if ok_r:
            sev = alerts.get("severity_breakdown", {})
            st.caption(
                f"⚠️ {alerts['alert_count']} flagged trade(s) · "
                f"🔴 {sev.get('high', 0)} high · 🟠 {sev.get('medium', 0)} medium")
            adf = pd.DataFrame(alerts["alerts"])
            if not adf.empty:
                disp = pd.DataFrame({
                    "Ref": adf["trade_ref"], "Symbol": adf["asset_symbol"],
                    "Notional": adf["notional"].map(fmt_money),
                    "Severity": adf["risk_severity"].map(lambda s: SEVERITY.get(s, s)),
                    "Reason": adf["risk_reason"],
                })
                st.dataframe(disp, use_container_width=True, hide_index=True)
        elif alerts == "denied":
            denied_card("Risk alerts are restricted for your role.")


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


def _render_assistant_body(m: dict) -> None:
    if m.get("denied"):
        st.markdown(
            f'<div class="denied-card" role="alert"><span aria-hidden="true">🔒</span>'
            f'<div>{m["content"]}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(m["content"])


def _render_message(m: dict) -> None:
    avatar = "🧑‍💼" if m["role"] == "user" else "🤖"
    with st.chat_message(m["role"], avatar=avatar):
        if m["role"] == "user":
            st.markdown(m["content"])
        else:
            _render_assistant_body(m)


def render_ai() -> None:
    page_header("🤖", "AI Assistant",
                "Chat with the Portfolio Analyst & Risk agents. Answers come only "
                "from database tool output, gated by your role.")
    st.session_state.setdefault("chat", [])

    cols = st.columns([1, 5])
    if cols[0].button("🗑 Clear chat", use_container_width=True):
        st.session_state.chat = []
        st.rerun()

    with st.expander("💡 Example questions", expanded=not st.session_state.chat):
        ec = st.columns(2)
        for i, ex in enumerate(EXAMPLE_QUESTIONS):
            if ec[i % 2].button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state.pending_q = ex

    for m in st.session_state.chat:
        _render_message(m)

    typed = st.chat_input("Ask about holdings, allocation, risk, trades…")
    question = typed or st.session_state.pop("pending_q", None)
    if question:
        user_msg = {"role": "user", "content": question}
        st.session_state.chat.append(user_msg)
        _render_message(user_msg)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Thinking…"):
                assistant_msg = _call_agent(question)
            _render_assistant_body(assistant_msg)
        st.session_state.chat.append(assistant_msg)


def render_audit() -> None:
    page_header("📝", "Audit Logs",
                "Every AI interaction — allowed and denied — is recorded here.")
    ok, logs = api_get("/audit/logs")
    if not ok:
        denied_card("Audit logs are restricted to authorized roles.") \
            if logs == "denied" else st.error(logs)
        return
    if not logs:
        st.info("No interactions logged yet. Ask the AI Assistant a few questions.")
        return

    df = pd.DataFrame(logs)
    allowed = int((df["decision"] == "allowed").sum())
    denied = int((df["decision"] == "denied").sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Interactions", len(df))
    c2.metric("✅ Allowed", allowed)
    c3.metric("🔒 Denied", denied)

    st.write("")
    fc1, fc2 = st.columns([1, 2])
    decision_filter = fc1.selectbox("Filter by decision", ["All", "allowed", "denied"])
    users = sorted(df["user_email"].unique())
    user_filter = fc2.multiselect("Filter by user", users, default=[],
                                  placeholder="All users")

    view = df.copy()
    if decision_filter != "All":
        view = view[view["decision"] == decision_filter]
    # No users selected => show all (do not filter).
    if user_filter:
        view = view[view["user_email"].isin(user_filter)]

    with st.container(border=True):
        disp = pd.DataFrame({
            "Time": pd.to_datetime(view["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S"),
            "User": view["user_email"], "Role": view["role"],
            "Question": view["question"], "Agent": view["agent"],
            "Tool": view["tool_called"],
            "Decision": view["decision"].map(
                {"allowed": "✅ Allowed", "denied": "🔒 Denied"}),
            "Reason": view["reason"],
        })
        st.dataframe(disp, use_container_width=True, hide_index=True)


PAGES = {
    "📊 Portfolio Overview": render_portfolio,
    "💹 Trades": render_trades,
    "🤖 AI Assistant": render_ai,
    "📝 Audit Logs": render_audit,
}
PAGES[page]()
