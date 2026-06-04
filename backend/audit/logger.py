"""Audit logging service.

Every AI agent interaction — allowed OR denied — is persisted here. This is a
mandatory control: it provides the who/what/when trail for AI usage and makes
RBAC enforcement observable. The logger is intentionally separate from the
route logic so it can be reused and tested independently.
"""
from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.models import AuditLog


def log_interaction(
    db: Session,
    *,
    user_email: str,
    role: str,
    question: str,
    decision: str,
    agent: str = "",
    tool_called: str = "",
    reason: str = "",
) -> AuditLog:
    """Persist one audit record. `decision` is 'allowed' or 'denied'."""
    entry = AuditLog(
        user_email=user_email,
        role=role,
        question=question[:500],
        agent=agent or "",
        tool_called=tool_called or "",
        decision=decision,
        reason=reason or "",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_logs(db: Session, limit: int = 200) -> list[AuditLog]:
    """Most recent audit records first."""
    return (
        db.query(AuditLog)
        .order_by(desc(AuditLog.timestamp), desc(AuditLog.id))
        .limit(limit)
        .all()
    )
