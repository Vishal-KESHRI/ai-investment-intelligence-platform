"""Agent query request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, field_validator


class AgentQuery(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        if len(v) > 500:
            raise ValueError("question too long (max 500 chars)")
        return v


class AgentResponse(BaseModel):
    status: str  # "allowed" | "denied"
    answer: str
    agent: str | None = None
    tool_called: str | None = None
    reason: str | None = None
    llm_provider: str | None = None
    # Raw structured tool output, for transparency / dashboard display.
    data: dict | None = None
