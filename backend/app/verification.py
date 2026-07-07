"""Verification loop: EXECUTE → QUERY → COMPARE → VERIFY → UPDATE → LOG.

A fact does not stay "unverified" forever. After it is written, later
independent evidence either confirms it (verified) or the Evidence Auditor
resolves a contradiction against it (failed). Verification is a measured
outcome, and it feeds 20% of the confidence formula.
"""

from __future__ import annotations

from datetime import datetime

from .memory.core import MemoryState
from .memory.episodic import get_event


def run_verification(state: MemoryState, now: datetime) -> list[dict]:
    """Re-check every active fact against the episodic record.

    A fact passes verification when independent origins across at least two
    distinct sessions agree with it — i.e. the world kept confirming it
    after we first wrote it down. A fact that lost a contradiction is marked
    failed by the auditor path (supersede) and keeps its history.
    """
    notifications: list[dict] = []
    for fact in state.active_facts():
        if fact.verification == "verified":
            continue
        sessions = set()
        for src in fact.sources:
            event = get_event(state, src.event_id)
            if event is not None:
                sessions.add(event.session_id)
        if fact.distinct_origins >= 2 and len(sessions) >= 2:
            fact.verification = "verified"
            state.log(
                now,
                "verifier",
                "fact_verified",
                fact_id=fact.id,
                key=fact.key,
                origins=fact.distinct_origins,
                sessions=sorted(sessions),
            )
            notifications.append(
                {
                    "type": "fact_verified",
                    "fact_id": fact.id,
                    "statement": fact.statement,
                    "origins": fact.distinct_origins,
                    "sessions": len(sessions),
                }
            )
    # Facts superseded in a resolved contradiction are the "failed" outcome.
    for record in state.contradictions.values():
        if record.status not in ("resolved_superseded", "resolved_by_user"):
            continue
        for fact_id in (record.fact_a_id, record.fact_b_id):
            fact = state.facts.get(fact_id)
            if fact is not None and not fact.active and fact.verification != "failed":
                fact.verification = "failed"
                state.log(
                    now, "verifier", "fact_verification_failed", fact_id=fact.id, key=fact.key
                )
    return notifications
