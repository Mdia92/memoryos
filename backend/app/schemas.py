"""Pydantic API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AssertionIn(BaseModel):
    subject: str = "user"
    key: str
    value: str
    statement: str = ""


class EventIn(BaseModel):
    type: str = Field(pattern="^(calendar|email|note|task|chat)$")
    content: str
    occurred_at: datetime | None = None
    session_id: int | None = None
    assertions: list[AssertionIn] | None = None  # None → Qwen extraction
    meta: dict = Field(default_factory=dict)


class AskIn(BaseModel):
    question: str
    compare: bool = True


class ResolveIn(BaseModel):
    chosen_fact_id: str


class SeedIn(BaseModel):
    sessions: int = Field(default=20, ge=1, le=20)


class EvalRunIn(BaseModel):
    label: str = "default"
    sessions: int = Field(default=20, ge=2, le=20)
    seed: int = 42
