"""JWT creation and decoding. Demo login is email-only; the token still
carries a signed (email, role) claim set so all downstream auth is token-based."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from backend.config import settings


def create_access_token(email: str, role: str) -> str:
    """Mint a signed JWT carrying the user's identity and role."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT. Raises jwt.PyJWTError on any problem."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
