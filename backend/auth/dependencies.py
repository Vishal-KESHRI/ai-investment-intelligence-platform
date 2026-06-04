"""FastAPI auth dependencies: extract the current user from a Bearer token,
and a reusable permission-guard dependency factory for routes."""
from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.jwt_handler import decode_access_token
from backend.auth.permissions import DENIED_REASON, check_user_permission

_bearer = HTTPBearer(auto_error=True)


@dataclass
class CurrentUser:
    email: str
    role: str


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> CurrentUser:
    """Decode the Bearer token into a CurrentUser, or 401."""
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email, role = payload.get("email"), payload.get("role")
    if not email or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="malformed token claims",
        )
    return CurrentUser(email=email, role=role)


def require_permission(resource: str):
    """Dependency factory: guards a route behind RBAC for a given resource.

    On denial returns HTTP 403 with the canonical denied payload so the
    dashboard can render a clean 'permission denied' banner.
    """

    def _guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not check_user_permission(user.role, resource):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "denied", "reason": DENIED_REASON},
            )
        return user

    return _guard
