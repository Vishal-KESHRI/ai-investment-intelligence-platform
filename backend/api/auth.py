"""Auth routes: email-only demo login that issues a JWT."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.jwt_handler import create_access_token
from backend.auth.permissions import allowed_resources
from backend.database.db import get_db
from backend.models import User
from backend.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Demo login: email only. The email must match a seeded user."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unknown user — try analyst@local, risk@local, manager@local, or intern@local",
        )
    token = create_access_token(email=user.email, role=user.role)
    return LoginResponse(
        access_token=token,
        email=user.email,
        role=user.role,
        allowed_resources=allowed_resources(user.role),
    )
