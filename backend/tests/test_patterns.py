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


def _reschedule(day_offset: int, session: int = 1) -> MemoryEvent:
    base = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)  # Monday
    return MemoryEvent(
        id=new_id(),
        session_id=session,
        type="calendar",
        content="Weekly sync rescheduled",
        occurred_at=base + timedelta(days=day_offset),
        assertions=[],
        meta={"action": "reschedule"},
    )


def test_post_break_reschedules_promotes(policy):
    """Reschedules preceded by a >=3-day gap earn a pattern promotion."""
    state = MemoryState()
    # An event, then a >=3-day gap, then 4 reschedules across sessions
    from app.memory.core import MemoryEvent, new_id

    state.events = [
        MemoryEvent(
            id=new_id(),
            session_id=1,
            type="chat",
            content="hello",
            occurred_at=datetime(2026, 5, 25, 10, tzinfo=UTC),
            assertions=[],
        ),
        _reschedule(0, session=1),   # Mon after long weekend
        _reschedule(28, session=2),  # 4 weeks later, Mon after long weekend
        _reschedule(56, session=3),
    ]
    scan_patterns(state, datetime(2026, 8, 1, tzinfo=UTC), policy)
    promoted_names = {p.name for p in state.patterns.values() if p.promoted}
    assert "post_break_reschedules" in promoted_names


def test_monday_reschedules_promotes(policy):
    """Reschedules on Mondays specifically."""
    state = MemoryState()
    state.events = [
        _reschedule(0, session=1),   # Monday 2026-06-01
        _reschedule(7, session=2),   # next Monday
        _reschedule(14, session=3),  # week after
    ]
    scan_patterns(state, datetime(2026, 7, 1, tzinfo=UTC), policy)
    promoted_names = {p.name for p in state.patterns.values() if p.promoted}
    assert "monday_reschedules" in promoted_names


def test_reschedule_on_thursday_does_not_promote_monday_pattern(policy):
    """The Monday-specific detector must not fire on other weekdays."""
    state = MemoryState()
    state.events = [
        _reschedule(3, session=1),   # Thursday
        _reschedule(10, session=2),  # Thursday
        _reschedule(17, session=3),  # Thursday
    ]
    scan_patterns(state, datetime(2026, 7, 1, tzinfo=UTC), policy)
    promoted_names = {p.name for p in state.patterns.values() if p.promoted}
    assert "monday_reschedules" not in promoted_names
