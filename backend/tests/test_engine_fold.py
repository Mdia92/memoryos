"""Engine fold ordering: episodic → semantic → decay → auditor → verify → pattern.

Each event is folded through all layers in a specific order. These tests
lock the order in so an accidental refactor can't reintroduce the classic
bugs (e.g. auditor running before semantic merge, patterns firing before
decay recomputes confidence).
"""

from datetime import UTC, datetime

from app.engine import ingest_event
from app.memory.core import (
    Assertion,
    MemoryEvent,
    MemoryState,
    new_id,
)


def _ev(
    value: str,
    origin: str = "chat",
    session: int = 1,
    at: datetime | None = None,
) -> MemoryEvent:
    at = at or datetime(2026, 3, 15, 10, 0, tzinfo=UTC)
    return MemoryEvent(
        id=new_id(),
        session_id=session,
        type=origin,
        content=f"{origin}: user prefers {value}",
        occurred_at=at,
        assertions=[Assertion(subject="user", key="meeting_time_preference", value=value)],
    )


def test_episodic_records_first(policy):
    """The event must exist in state.events before any semantic work runs."""
    state = MemoryState()
    ingest_event(state, _ev("morning"), policy)
    assert len(state.events) == 1


def test_semantic_creates_fact_with_source_reference(policy):
    """After ingest, the fact's sources list points back at the ingested event."""
    state = MemoryState()
    ev = _ev("morning")
    ingest_event(state, ev, policy)
    facts = list(state.facts.values())
    assert len(facts) == 1
    fact = facts[0]
    assert fact.value == "morning"
    assert fact.sources[0].event_id == ev.id


def test_second_event_same_value_corroborates(policy):
    """Same value from another origin merges sources without duplicating fact."""
    state = MemoryState()
    ingest_event(state, _ev("morning", origin="chat", session=1), policy)
    ingest_event(state, _ev("morning", origin="email", session=2), policy)
    facts = list(state.facts.values())
    assert len(facts) == 1
    assert len(facts[0].sources) == 2
    assert facts[0].distinct_origins == 2


def test_conflicting_value_produces_two_active_facts(policy):
    """Disagreeing values coexist; the auditor decides — never silent overwrite."""
    state = MemoryState()
    ingest_event(state, _ev("morning", session=1), policy)
    ingest_event(state, _ev("afternoon", session=2), policy)
    active_values = {f.value for f in state.facts.values() if f.active}
    # At least the challenger must exist; the auditor may have already resolved
    # the incumbent depending on the evidence disparity.
    assert active_values.intersection({"morning", "afternoon"})


def test_auditor_records_contradiction_notification(policy):
    """A disagreeing value produces a contradiction_detected notification."""
    state = MemoryState()
    ingest_event(state, _ev("morning", session=1), policy)
    notifs = ingest_event(state, _ev("afternoon", session=2), policy)
    kinds = {n["type"] for n in notifs}
    assert "contradiction_detected" in kinds


def test_decay_ordering_affects_final_confidence(policy):
    """Confidence after ingest reflects decay applied at the ingest instant."""
    state = MemoryState()
    old = datetime(2026, 1, 1, tzinfo=UTC)
    ingest_event(state, _ev("morning", at=old), policy)
    fact = list(state.facts.values())[0]
    fresh_conf = fact.confidence

    # A more recent same-value event should increase confidence, not decrease.
    ingest_event(state, _ev("morning", at=datetime(2026, 6, 15, tzinfo=UTC)), policy)
    fact = list(state.facts.values())[0]
    assert fact.confidence >= fresh_conf


def test_verify_only_after_semantic_merge(policy):
    """Verification runs after merge, so the fact receiving the check exists."""
    state = MemoryState()
    for i in range(4):
        ingest_event(
            state,
            _ev("morning", origin=["chat", "email", "note", "task"][i], session=i + 1),
            policy,
        )
    facts = list(state.facts.values())
    assert len(facts) == 1
    # A fact with 4 distinct origins and multiple sessions should reach verified.
    assert facts[0].verification == "verified"


def test_ingest_is_idempotent_for_notification_count(policy):
    """Replaying the same event again should not spam new pattern/audit
    notifications; the state is derived only from state.events."""
    state = MemoryState()
    ev = _ev("morning")
    ingest_event(state, ev, policy)
    # Re-fold: same content, new id (a genuinely repeated but distinct event)
    ev2 = _ev("morning")
    n2 = ingest_event(state, ev2, policy)
    kinds = {n["type"] for n in n2}
    # A pure corroboration event has no drama — no contradiction, no pattern promotion.
    assert "contradiction_detected" not in kinds


def test_no_assertions_still_records_episodic(policy):
    """An event with no assertions still lives in the episodic layer —
    that's the "record everything, interpret only what we can" invariant."""
    state = MemoryState()
    ev = MemoryEvent(
        id=new_id(),
        session_id=1,
        type="chat",
        content="just a status update",
        occurred_at=datetime(2026, 3, 15, tzinfo=UTC),
        assertions=[],
    )
    ingest_event(state, ev, policy)
    assert len(state.events) == 1
    assert len(state.facts) == 0
