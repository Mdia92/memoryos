"""Pattern detectors — deterministic, fast-path, no LLM."""

from datetime import UTC, datetime, timedelta

from app.memory.core import MemoryEvent, MemoryState, new_id
from app.memory.pattern import scan_patterns


def _ev(hour: int, day_offset: int, session: int = 1) -> MemoryEvent:
    base = datetime(2026, 6, 1, hour, 0, tzinfo=UTC)  # Monday 2026-06-01
    return MemoryEvent(
        id=new_id(),
        session_id=session,
        type="chat",
        content="x",
        occurred_at=base + timedelta(days=day_offset),
        assertions=[],
    )


def test_late_night_activity_promotes(policy):
    """5+ late-night events across 2+ sessions → pattern promoted."""
    state = MemoryState()
    state.events = [
        _ev(22, 0, session=1),
        _ev(23, 0, session=1),
        _ev(1, 0, session=1),
        _ev(22, 7, session=2),
        _ev(2, 7, session=2),
    ]
    notifications = scan_patterns(state, datetime(2026, 6, 15, tzinfo=UTC), policy)
    promoted = [p for p in state.patterns.values() if p.promoted]
    assert any(p.name == "late_night_activity" for p in promoted)
    assert any(n["type"] == "pattern_promoted" for n in notifications)


def test_weekend_avoidance_promotes(policy):
    """Two weeks with 5 weekday events and 0 weekend events → pattern promoted."""
    state = MemoryState()
    events = []
    # Week 1: Mon–Fri only
    for d in range(5):
        events.append(_ev(10, d, session=1))
    # Week 2: Mon–Fri only
    for d in range(5):
        events.append(_ev(10, 7 + d, session=2))
    state.events = events
    scan_patterns(state, datetime(2026, 6, 20, tzinfo=UTC), policy)
    promoted = [p for p in state.patterns.values() if p.promoted]
    assert any(p.name == "weekend_avoidance" for p in promoted)


def test_weekend_avoidance_does_not_promote_with_weekend_activity(policy):
    """Any Saturday/Sunday event in a week breaks the pattern."""
    state = MemoryState()
    events = []
    for d in range(5):
        events.append(_ev(10, d, session=1))
    events.append(_ev(10, 5, session=1))  # Saturday
    state.events = events
    scan_patterns(state, datetime(2026, 6, 15, tzinfo=UTC), policy)
    promoted_names = {p.name for p in state.patterns.values() if p.promoted}
    assert "weekend_avoidance" not in promoted_names
