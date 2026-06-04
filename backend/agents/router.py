"""Agent router — the orchestration brain.

End-to-end flow for POST /agent/query (matches the brief exactly):
    User -> AI Agent -> Tool/API -> Database -> Response

Steps:
  1. Classify the question -> pick the right agent + tool (deterministic).
  2. Hard RBAC gate via check_user_permission() BEFORE any tool runs.
  3. If denied: audit-log the denial and return the canonical denied payload.
  4. If allowed: run the tool against the DB.
  5. (Risk 'explain' routes) augment with RAG policy context.
  6. Synthesize a natural-language answer via the LLM provider (Ollama->mock).
  7. Audit-log the allowed interaction (with the tool name).
  8. Return the answer + structured data.

The LLM is never trusted with permissions or data access — those are code.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.agents import portfolio_agent, risk_agent
from backend.audit.logger import log_interaction
from backend.auth.permissions import DENIED_REASON, check_user_permission
from backend.llm.factory import synthesize
from backend.rag.vector_store import retrieve_policy_context

# Build the combined route table once.
_ROUTES: list[dict] = portfolio_agent.routes() + risk_agent.routes()
# Default route when nothing matches: safe, low-privilege portfolio summary.
_DEFAULT_ROUTE = next(r for r in _ROUTES if r["tool"] == "get_portfolio_summary")


def _classify(question: str) -> dict:
    """Pick the best route by keyword overlap. Deterministic & explainable."""
    q = question.lower()
    tokens = set(q.replace("?", " ").replace(",", " ").split())

    best, best_score = _DEFAULT_ROUTE, 0
    for route in _ROUTES:
        score = 0
        for kw in route["keywords"]:
            # Substring match handles stems like "diversif" / "overexpos".
            if kw in q or kw in tokens:
                score += 1
        if score > best_score:
            best, best_score = route, score
    return best


def route_and_answer(db: Session, *, email: str, role: str, question: str) -> dict:
    """Full orchestration with RBAC gate, audit logging, and LLM synthesis."""
    route = _classify(question)
    agent_name = route["agent"]
    tool_name = route["tool"]
    resource = route["resource"]

    # --- 2/3. Hard RBAC gate (server-side, before any data access) ---
    if not check_user_permission(role, resource):
        log_interaction(
            db,
            user_email=email,
            role=role,
            question=question,
            decision="denied",
            agent=agent_name,
            tool_called=tool_name,
            reason=DENIED_REASON,
        )
        return {
            "status": "denied",
            "answer": (
                f"Access denied: your role ('{role}') is not permitted to use "
                f"the '{resource}' capability."
            ),
            "agent": agent_name,
            "tool_called": tool_name,
            "reason": DENIED_REASON,
            "llm_provider": None,
            "data": None,
        }

    # --- 4. Run the tool against the database ---
    tool_result = route["runner"](db)

    # --- 5. Optional RAG grounding for risk 'explain' answers ---
    policy_context = []
    if route.get("rag"):
        policy_context = retrieve_policy_context(question, top_k=2)
        if policy_context:
            tool_result = {**tool_result, "policy_context": policy_context}

    # --- 6. LLM synthesis (Ollama with deterministic mock fallback) ---
    tool_result_json = json.dumps(tool_result, default=str)
    answer, provider = synthesize(question, tool_result_json)

    # --- 7. Audit-log the allowed interaction ---
    log_interaction(
        db,
        user_email=email,
        role=role,
        question=question,
        decision="allowed",
        agent=agent_name,
        tool_called=tool_name,
        reason="",
    )

    # --- 8. Return ---
    return {
        "status": "allowed",
        "answer": answer,
        "agent": agent_name,
        "tool_called": tool_name,
        "reason": None,
        "llm_provider": provider,
        "data": tool_result,
    }
