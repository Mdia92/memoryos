"""Duplicates merge with their sources; disagreements coexist until audited."""

from datetime import timedelta

from app.engine import ingest_event
from app.memory.core import MemoryState
from app.memory.semantic import integrate_assertion

from .conftest import NOW, make_event


def test_same_value_merges_sources(policy):
    state = MemoryState()
    e1 = make_event("morning", origin="email", at=NOW)
    e2 = make_event("morning", origin="calendar", at=NOW + timedelta(hours=1))

    fact1, outcome1 = integrate_assertion(state, e1, e1.assertions[0])
    fact2, outcome2 = integrate_assertion(state, e2, e2.assertions[0])

    assert outcome1 == "created" and outcome2 == "corroborated"
    assert fact1.id == fact2.id
    assert len(fact1.sources) == 2
    assert fact1.distinct_origins == 2
    assert fact1.last_supported == e2.occurred_at


def test_same_event_never_counted_twice(policy):
    state = MemoryState()
    event = make_event("morning")
    integrate_assertion(state, event, event.assertions[0])
    fact, _ = integrate_assertion(state, event, event.assertions[0])
    assert len(fact.sources) == 1


def test_conflicting_value_creates_competing_fact_not_overwrite(policy):
    state = MemoryState()
    e1 = make_event("morning", origin="email")
    e2 = make_event("afternoon", origin="chat", at=NOW + timedelta(hours=2))
    integrate_assertion(state, e1, e1.assertions[0])
    integrate_assertion(state, e2, e2.assertions[0])

    values = {f.value for f in state.active_facts("user", "meeting_time_preference")}
    assert values == {"morning", "afternoon"}


def test_reactivation_accumulates_evidence_after_supersede(policy):
    """A value the auditor once superseded must regain its evidence chain
    when the world re-asserts it — otherwise a changed preference can
    never win."""
    state = MemoryState()
    # strong incumbent
    for i, origin in enumerate(["email", "calendar", "note"]):
        ev = make_event("remote", key="meeting_mode", origin=origin, at=NOW + timedelta(hours=i))
        ingest_event(state, ev, policy)
    # weak challenger gets superseded by the auditor (noise path)
    ch = make_event("office", key="meeting_mode", origin="chat", at=NOW + timedelta(hours=5))
    ingest_event(state, ch, policy)
    # more incumbent support arrives after the challenger → challenger loses
    ev = make_event("remote", key="meeting_mode", origin="task", at=NOW + timedelta(hours=8))
    ingest_event(state, ev, policy)

    office_facts = [f for f in state.facts.values() if f.value == "office"]
    assert len(office_facts) == 1
    superseded = office_facts[0]
    assert not superseded.active

    # the world re-asserts "office" — the SAME fact accumulates the evidence
    # (it may lose the confidence-gap contest again, but it never restarts
    # from zero)
    again = make_event("office", key="meeting_mode", origin="email", at=NOW + timedelta(days=7))
    ingest_event(state, again, policy)
    office_facts = [f for f in state.facts.values() if f.value == "office"]
    assert len(office_facts) == 1
    assert office_facts[0].id == superseded.id
    assert len(office_facts[0].sources) == 2

    # a second independent re-assertion makes the challenge SUSTAINED —
    # now it is a preference change and office wins
    more = make_event("office", key="meeting_mode", origin="note", at=NOW + timedelta(days=8))
    ingest_event(state, more, policy)
    active = state.active_facts("user", "meeting_mode")
    assert {f.value for f in active} == {"office"}
    assert active[0].id == superseded.id
    assert len(active[0].sources) == 3
