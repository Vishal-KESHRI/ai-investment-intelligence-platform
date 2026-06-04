# ARP Global Capital — Local AI Investment Intelligence Platform

A **locally runnable** AI-powered investment-operations platform that demonstrates
secure AI workflows: AI agents with tool calling, **server-side role-based access
control (RBAC)**, **full audit logging**, dashboards, and a one-command Docker
deployment. Runs entirely on a normal laptop — **no GPU, no paid APIs, no cloud**.

```bash
docker compose up
# Dashboard → http://localhost:8501
# API docs  → http://localhost:8000/docs
```

---

## 1. What it does

| Capability | Implementation |
|---|---|
| Load investment/operational data | Faker-generated mock data (deterministic seed) |
| Store data locally | SQLite via SQLAlchemy (6 tables) |
| Visualize | Streamlit + Plotly dashboard (4 pages) |
| AI agents answering from real data | Portfolio Analyst + Risk & Compliance agents |
| Role-based access control | Server-side permission gate (mandatory) |
| Audit logs for AI interactions | Every query — allowed *and* denied — is logged |
| Run locally with Docker | `docker compose up` (backend + dashboard + Ollama) |

The design thesis (per the brief): **orchestration and tool-calling matter more
than model quality.** RBAC, tool routing, and DB access are all deterministic
code. The LLM only synthesises a natural-language answer from tool output it is
explicitly handed — it never decides permissions and never sees data the user's
role isn't allowed to access.

---

## 2. Architecture

```
                          ┌─────────────────────────────────────────────┐
                          │            Streamlit Dashboard               │
                          │   Portfolio · Trades · AI Assistant · Audit  │
                          │   (stores JWT in session; renders only what  │
                          │    the backend returns — no client-side RBAC)│
                          └───────────────────────┬─────────────────────┘
                                                  │ HTTP + Bearer JWT
                                                  ▼
        ┌──────────────────────────────────────────────────────────────────────┐
        │                         FastAPI Backend                                │
        │                                                                        │
        │  /auth/login   /dashboard/*   /agent/query   /audit/logs   /health     │
        │       │             │              │              │                    │
        │       ▼             ▼              ▼              ▼                    │
        │   JWT handler   require_permission()      Agent Router (orchestrator)  │
        │                 (RBAC gate, 403)     1. classify → agent + tool        │
        │                                      2. RBAC gate  ◀── hard, in code    │
        │                                      3. run tool → DB                  │
        │                                      4. RAG grounding (risk explain)   │
        │                                      5. LLM synthesis                  │
        │                                      6. audit log (allowed OR denied)  │
        │       │                                     │            │            │
        │       ▼                                     ▼            ▼            │
        │  ┌─────────────┐   ┌──────────────┐  ┌────────────┐ ┌─────────────┐  │
        │  │ Tools layer │   │ LLM Provider │  │ Vector RAG │ │ Audit logger│  │
        │  │ portfolio / │   │  (interface) │  │ (TF-IDF,   │ │             │  │
        │  │ risk tools  │   │ Ollama│Mock  │  │  numpy)    │ │             │  │
        │  └──────┬──────┘   └──────┬───────┘  └────────────┘ └──────┬──────┘  │
        └─────────┼─────────────────┼─────────────────────────────────┼────────┘
                  ▼                 ▼ (local, no data egress)          ▼
        ┌──────────────────┐  ┌──────────────┐              ┌──────────────────┐
        │  SQLite database │  │   Ollama     │              │   audit_logs      │
        │ users, holdings, │  │ qwen2.5:7b / │              │ (same SQLite DB)  │
        │ trades, prices,  │  │ llama3.2:3b  │              │                   │
        │ risk_rules, ...  │  └──────────────┘              └──────────────────┘
        └──────────────────┘
```

**Request flow for an AI question** (matches the brief exactly):
`User → AI Agent → Tool/API → Database → Response`

### Project layout

```
backend/
  main.py                 FastAPI app + startup seeding + /health
  config.py               env-driven settings (12-factor)
  database/  db.py, seed.py
  models/    user, holding, trade, market_price, risk_rule, audit_log
  schemas/   auth, agent, dashboard (Pydantic, input validation)
  auth/      jwt_handler.py, permissions.py (RBAC matrix), dependencies.py
  tools/     portfolio_tools.py, risk_tools.py   (the only DB read path for agents)
  agents/    portfolio_agent.py, risk_agent.py, router.py (orchestrator)
  llm/       base.py (interface), ollama_provider.py, mock_provider.py, factory.py
  rag/       vector_store.py (dependency-free TF-IDF retrieval)
  audit/     logger.py
  api/       auth.py, dashboard.py, agent.py, audit.py
dashboard/   app.py (Streamlit), Dockerfile, requirements.txt
tests/       test_rbac.py, test_audit.py, test_agents.py, conftest.py
Dockerfile, docker-compose.yml, .env.example, requirements.txt
.github/workflows/ci.yml
```

---

## 3. Setup & run

### Option A — Docker (recommended)

```bash
cp .env.example .env          # adjust JWT_SECRET etc. (never commit .env)
docker compose up --build
```

- Dashboard: <http://localhost:8501>
- Backend API + Swagger docs: <http://localhost:8000/docs>
- Ollama: <http://localhost:11434>

**Enable the local LLM (optional but recommended for the demo).** Ollama starts
empty; pull a model once (cached in a volume afterwards):

```bash
docker compose exec ollama ollama pull qwen2.5:7b   # ~4.7GB, good tool-calling
# Lighter option for weaker laptops:
docker compose exec ollama ollama pull llama3.2:3b
```

If no model is pulled (or Ollama is slow/unavailable), the backend **transparently
falls back to the deterministic mock provider** — the demo never hard-fails. To
skip Ollama entirely, set `LLM_PROVIDER=mock` in `.env`.

The SQLite database is auto-created and seeded on first startup, persisted in the
`arp-db` Docker volume.

### Option B — Local Python (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export LLM_PROVIDER=mock JWT_SECRET=dev-secret      # mock = no Ollama needed
uvicorn backend.main:app --reload                   # backend on :8000

# In a second terminal:
pip install -r dashboard/requirements.txt
export BACKEND_URL=http://localhost:8000
streamlit run dashboard/app.py                      # dashboard on :8501
```

### Run the tests

```bash
pytest -q          # 24 tests: RBAC, audit, agent routing (all use mock LLM)
ruff check backend tests
```

---

## 4. Login users (demo)

Login is **email-only** for the demo, but it still issues a signed JWT carrying
the user's role; all protected routes require that token.

| Email | Role | Access |
|---|---|---|
| `analyst@local` | analyst | Portfolio + market data |
| `risk@local` | risk | Portfolio + trades + risk alerts + audit |
| `manager@local` | manager | Summary-only (+ audit oversight) |
| `intern@local` | intern | Basic portfolio summary only |

---

## 5. RBAC matrix (enforced server-side)

RBAC is the single source of truth in `backend/auth/permissions.py` and is
enforced by the backend on **every** route and **every** agent tool call. The
dashboard performs **no** access decisions — it only renders what the backend
returns, or a "permission denied" banner on HTTP 403.

| Resource → / Role ↓ | portfolio_summary | holdings | trades | market_data | exposure | risk_alerts | audit_logs |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **analyst** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **risk** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **manager** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **intern** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

> **Manager = full access** (project-owner override). Note: the original
> assessment brief specifies a *summary-only* manager; this build grants the
> manager every resource per request. To restore the brief's behaviour, set
> `"manager"` back to `{"portfolio_summary", "exposure", "audit_logs"}` in
> `backend/auth/permissions.py`.

Denied requests return the canonical payload:

```json
{ "status": "denied", "reason": "insufficient permissions" }
```

---

## 6. AI agents & tool calling

Two agents, selected by deterministic keyword routing (`backend/agents/router.py`):

- **Portfolio Analyst** — top holdings, asset allocation, biggest movers, performance.
- **Risk & Compliance** — overexposure, high-risk trades, review queue, explain-a-flag.

**Tools** (the only way agents read data — `Agent → Tool → DB → Response`):

| Tool | Resource gated | Returns |
|---|---|---|
| `get_portfolio_summary()` | portfolio_summary | value, P&L, allocation, top holdings |
| `get_recent_trades()` | trades | trade blotter |
| `get_asset_exposure()` | exposure | exposure by asset & sector |
| `get_risk_alerts()` | risk_alerts | flagged trades + active rules |
| `check_user_permission()` | — | the hard RBAC gate (runs before any tool) |

Plus `get_top_movers`, `get_overexposure`, `get_trades_for_review`,
`explain_trade_flag` for the full question set.

**Hybrid orchestration (why it's robust).** Small local models are unreliable at
strict tool selection, so routing, RBAC, and DB access are deterministic code.
The LLM is used only to turn the structured tool output into prose, under this
constrained prompt:

```
You are an investment operations assistant.
Use ONLY the provided tool output. Do not invent financial data.
If the tool output does not contain enough information, say so clearly.
```

**Provider abstraction (`backend/llm/`).** The platform depends on an
`LLMProvider` interface, never a concrete model:

- `OllamaProvider` — local model, **default** (no data egress).
- `MockProvider` — deterministic, model-free synthesis; used in CI/tests and as
  the runtime fallback if Ollama fails.

Swapping in a VPC-hosted model for production is one new class + one env var
(`LLM_PROVIDER`) — no changes to agents or tools.

**RAG (bonus).** "Explain why a trade was flagged" augments the answer with the
most relevant compliance-policy snippet, retrieved from a tiny dependency-free
TF-IDF vector store (`backend/rag/vector_store.py`). Swappable for pgvector/Chroma
in production behind the same `query()` interface.

---

## 7. Audit logging

Every call to `POST /agent/query` writes one `audit_logs` row — **whether allowed
or denied** — capturing: `user`, `role`, `question`, `agent`, `tool_called`,
`decision (allowed|denied)`, `reason`, `timestamp`.

- API: `GET /audit/logs` (RBAC-guarded — only `risk` and `manager` may read it).
- Dashboard: the **Audit Logs** page colour-codes allowed (green) vs denied (red)
  and shows allowed/denied counts.

This makes RBAC enforcement observable and provides the AI-usage trail required
for compliance.

---

## 8. Security considerations

- **No secrets committed.** All secrets come from env vars; `.env` is git-ignored;
  `.env.example` documents every variable. `JWT_SECRET` should be generated with
  `openssl rand -hex 32` in production.
- **Server-side RBAC only.** The single permission gate runs before any data read
  on both dashboard routes and agent tool calls. The UI cannot bypass it.
- **Token auth.** Protected routes require a valid Bearer JWT; expiry is enforced.
- **Input validation.** Pydantic validates and bounds all inputs (email shape,
  question length ≤ 500 chars, trade-limit clamping).
- **Least-data-to-model.** The LLM receives only the specific tool output needed
  for the answer — never raw tables or data outside the user's role.
- **Auditability.** Allowed and denied AI interactions are both logged.
- **Container hardening.** Images run as a non-root user.

### External LLM risk & mitigation

> External LLM providers may receive sensitive portfolio, trade, or compliance
> data if prompts are sent outside the organization, where they could be retained,
> logged, or used for training.

**Mitigations implemented / recommended:**

- **Prefer a local LLM (Ollama)** — the default. Data never leaves the laptop.
- **Apply RBAC *before* tool calls** — unauthorized roles never reach the data.
- **Send only the minimal tool output** required for the answer; never raw tables.
- **Never expose data to unauthorized roles**, in UI or prompt.
- **Log every interaction** for traceability.
- **Validate all inputs**; use env vars for secrets.
- **In production:** use a private/VPC-hosted model or a zero-retention provider
  under a DPA/BAA, plus secrets management (Vault/KMS) and encryption in transit
  and at rest. The `LLMProvider` abstraction makes this a config-level change.

---

## 9. Production scaling plan

| Area | Local (this assessment) | Production |
|---|---|---|
| Database | SQLite | PostgreSQL (+ pgvector for RAG), read replicas |
| Auth | Email-only demo JWT | OAuth / SSO / OIDC, short-lived tokens, refresh |
| LLM | Local Ollama | Dedicated inference service (VPC / private endpoint) |
| Ingress | Direct ports | API gateway + WAF + rate limiting |
| Observability | `/health` + audit table | Prometheus + Grafana, ELK/OpenSearch for logs |
| Deployment | docker compose | Kubernetes (HPA), CI/CD pipeline |
| Security | env vars | Vault/KMS secrets, encryption at rest & in transit |
| Risk workflow | flag + audit | Human review/approval workflow for high-risk trades |

---

## 10. Demo script (interview)

1. `docker compose up` → open <http://localhost:8501>.
2. **Login `analyst@local`** → AI Assistant → *"What are our top holdings?"* → **allowed**, answered from portfolio data.
3. Still analyst → *"Which trades are high risk?"* → **denied** (insufficient permissions).
4. **Login `risk@local`** → *"Which trades are high risk?"* → **allowed**, answered from trade + risk data.
5. **Login `manager@local`** → *"Summarize portfolio performance"* → **summary-only** answer.
6. **Login `intern@local`** → *"Show recent trades"* → **denied**.
7. Open **Audit Logs** (as risk/manager) → show allowed + denied requests with users, roles, tools, timestamps.

---

## 11. Tech stack

FastAPI · SQLAlchemy · SQLite · Pydantic · PyJWT · Faker · Streamlit · Plotly ·
Ollama · numpy (RAG) · pytest · ruff · Docker Compose · GitHub Actions.
