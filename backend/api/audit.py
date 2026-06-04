"""Audit log API. RBAC-guarded: only roles with 'audit_logs' may read it."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.audit.logger import list_logs
from backend.auth.dependencies import require_permission
from backend.database.db import get_db
from backend.schemas.dashboard import AuditLogOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogOut])
def get_logs(
    db: Session = Depends(get_db),
    _=Depends(require_permission("audit_logs")),
) -> list[AuditLogOut]:
    """Return audit records (allowed AND denied AI interactions), newest first."""
    return [AuditLogOut.model_validate(row, from_attributes=True) for row in list_logs(db)]
