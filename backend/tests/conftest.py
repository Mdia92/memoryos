from datetime import UTC, datetime, timedelta

import pytest

from app.config import get_policy
from app.memory.core import Assertion, MemoryEvent, MemoryFact, SourceRef, new_id

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def policy() -> dict:
    return get_policy()


def make_fact(
    value: str = "morning",
    key: str = "meeting_time_preference",
    origins: list[str] | None = None,
    age_days: float = 0.0,
    verification: str = "unverified",
    user_confirmation: str = "none",
) -> MemoryFact:
    """A fact whose last support is `age_days` old, one source per origin."""
    origins = origins if origins is not None else ["calendar"]
    supported = NOW - timedelta(days=age_days)
    return MemoryFact(
        id=new_id(),
        subject="user",
        key=key,
        value=value,
        statement=f"user {key} = {value}",
        sources=[
            SourceRef(event_id=new_id(), origin=o, occurred_at=supported - timedelta(hours=i))
            for i, o in enumerate(origins)
        ],
        first_seen=supported - timedelta(days=1),
        last_supported=supported,
        verification=verification,
        user_confirmation=user_confirmation,
    )


def make_event(
    value: str,
    key: str = "meeting_time_preference",
    origin: str = "email",
    session_id: int = 1,
    at: datetime | None = None,
) -> MemoryEvent:
    at = at or NOW
    return MemoryEvent(
        id=new_id(),
        session_id=session_id,
        type=origin,
        content=f"{origin} says {key}={value}",
        occurred_at=at,
        assertions=[Assertion(subject="user", key=key, value=value)],
    )
