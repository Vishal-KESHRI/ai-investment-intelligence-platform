"""AI agent query endpoint. Auth required; RBAC + audit happen inside the router."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.agents.router import route_and_answer
from backend.auth.dependencies import CurrentUser, get_current_user
from backend.database.db import get_db
from backend.schemas.agent import AgentQuery, AgentResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/query", response_model=AgentResponse)
def query(
    payload: AgentQuery,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AgentResponse:
    """Ask an AI agent a question. Returns an allowed answer or a clean denial.

    Note: we return HTTP 200 even for denials so the dashboard can render the
    'permission denied' message in-flow; the denial is recorded in the audit
    log and reflected in the response `status`.
    """
    result = route_and_answer(
        db, email=user.email, role=user.role, question=payload.question
    )
    return AgentResponse(**result)
