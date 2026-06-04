"""Auth request/response schemas."""
from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

# Loose email shape — must allow demo addresses like "analyst@local"
# (no TLD), which strict RFC validators reject. Input validation requirement.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


class LoginRequest(BaseModel):
    # Demo: email-only login. Validated against the seeded users table.
    email: str

    @field_validator("email")
    @classmethod
    def normalize(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v) or len(v) > 120:
            raise ValueError("invalid email format")
        return v


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    role: str
    allowed_resources: list[str]
