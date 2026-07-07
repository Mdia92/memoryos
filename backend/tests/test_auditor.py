"""The Evidence Auditor: detect, resolve from evidence, escalate when unsure."""

from datetime import timedelta

from app.engine import ingest_event
from app.evidence_auditor import user_resolve
from app.memory.core import MemoryState

from .conftest import NOW, make_event


def _ingest_many(state, policy, value, origins, key="meeting_mode", start=NOW, session=1):
    for i, origin in enumerate(origins):
        ev = make_event(
            value, key=key, origin=origin, session_id=session, at=start + timedelta(hours=i)
        )
        ingest_event(state, ev, policy)


def test_contradiction_detected_between_competing_values(policy):
    state = MemoryState()
    _ingest_many(state, policy, "remote", ["email", "calendar"])
    notifications = ingest_event(
        state,
        make_event("office", key="meeting_mode", origin="chat", at=NOW + timedelta(days=1)),
        policy,
    )
    assert any(n["type"] == "contradiction_detected" for n in notifications)


def test_single_stray_claim_is_dismissed_as_noise(policy):
    """One uncorroborated claim, contradicted by newer evidence, loses."""
    state = MemoryState()
    _ingest_many(state, policy, "remote", ["email", "calendar", "note"], session=1)
    ingest_event(
        state,
        make_event("office", key="meeting_mode", origin="chat", at=NOW + timedelta(days=1)),
        policy,
    )
    # incumbent gets supported again AFTER the stray claim
    _ingest_many(state, policy, "remote", ["task"], start=NOW + timedelta(days=2), session=2)

    active_values = {f.value for f in state.active_facts("user", "meeting_mode")}
    assert active_values == {"remote"}
    assert any(c.status == "resolved_superseded" for c in state.contradictions.values())


def test_sustained_independent_challenge_wins_as_preference_change(policy):
    """Evidence that keeps arriving after the incumbent went quiet is a
    preference change, not noise — regardless of the incumbent's totals."""
    state = MemoryState()
    _ingest_many(state, policy, "remote", ["email", "calendar", "note", "task"], session=1)
    # the world changes: office evidence from two independent origins,
    # all AFTER the last remote support
    _ingest_many(
        state,
        policy,
        "office",
        ["calendar", "chat"],
        start=NOW + timedelta(days=7),
        session=2,
    )

    active = state.active_facts("user", "meeting_mode")
    assert {f.value for f in active} == {"office"}
    remote = next(f for f in state.facts.values() if f.value == "remote")
    assert not remote.active
    assert remote.verification == "failed"  # the world stopped confirming it


def test_ambiguous_conflict_escalates_to_user_once(policy):
    state = MemoryState()
    _ingest_many(state, policy, "remote", ["email", "calendar"], session=1)
    # comparable strength for the challenger, interleaved in time so neither
    # side shows a sustained post-incumbent pattern
    notifications = ingest_event(
        state,
        make_event("office", key="meeting_mode", origin="note", at=NOW + timedelta(minutes=30)),
        policy,
    )
    clarifications = [n for n in notifications if n["type"] == "clarification_needed"]
    assert len(clarifications) == 1
    # a second supporting event for the challenger does not re-escalate
    notifications = ingest_event(
        state,
        make_event("office", key="meeting_mode", origin="chat", at=NOW + timedelta(minutes=40)),
        policy,
    )
    assert not any(n["type"] == "clarification_needed" for n in notifications)
    # both values still active — the agent asks instead of guessing
    assert {f.value for f in state.active_facts("user", "meeting_mode")} == {"remote", "office"}
    # escalation happens once, not on every subsequent ingest
    more = ingest_event(
        state,
        make_event(
            "morning", key="meeting_time_preference", origin="email", at=NOW + timedelta(hours=2)
        ),
        policy,
    )
    assert not any(n["type"] == "clarification_needed" for n in more)


def test_user_resolution_confirms_and_supersedes(policy):
    state = MemoryState()
    _ingest_many(state, policy, "remote", ["email", "calendar"], session=1)
    ingest_event(
        state,
        make_event("office", key="meeting_mode", origin="note", at=NOW + timedelta(minutes=30)),
        policy,
    )
    open_contradiction = next(
        c for c in state.contradictions.values() if c.status == "open"
    )
    chosen = next(f for f in state.facts.values() if f.value == "office")

    notification = user_resolve(state, open_contradiction.id, chosen.id, NOW + timedelta(hours=1))

    assert notification["winner"] == "office"
    assert chosen.user_confirmation == "confirmed"
    loser = next(f for f in state.facts.values() if f.value == "remote")
    assert loser.user_confirmation == "corrected"
    assert not loser.active
    assert open_contradiction.status == "resolved_by_user"
