"""Layer 2 — Semantic. Duplicate facts merge; their evidence merges with them.

Instead of storing "user prefers morning meetings" five times, MemoryOS
stores it once with five sources. Corroboration — not repetition — is what
raises confidence. Disagreeing values are NOT overwritten: they coexist as
competing facts until the Evidence Auditor resolves them.
"""

from __future__ import annotations

from .core import Assertion, MemoryEvent, MemoryFact, MemoryState, SourceRef, new_id


def integrate_assertion(
    state: MemoryState, event: MemoryEvent, assertion: Assertion
) -> tuple[MemoryFact, str]:
    """Fold one assertion into semantic memory.

    Returns the touched fact and an outcome: "corroborated" | "created".
    """
    source = SourceRef(
        event_id=event.id,
        origin=event.type,
        occurred_at=event.occurred_at,
        excerpt=(assertion.statement or event.content)[:160],
    )
    siblings = state.active_facts(assertion.subject, assertion.key)

    same_value = next((f for f in siblings if f.value == assertion.value), None)
    if same_value is None:
        # The world may be re-asserting a value the auditor once superseded.
        # Evidence accumulates on the same fact — reactivate it rather than
        # restarting from zero, or a changed preference could never win.
        superseded = next(
            (
                f
                for f in state.facts.values()
                if not f.active
                and f.subject == assertion.subject
                and f.key == assertion.key
                and f.value == assertion.value
            ),
            None,
        )
        if superseded is not None:
            superseded.active = True
            superseded.superseded_by = None
            state.log(
                event.occurred_at,
                "semantic",
                "fact_reactivated",
                fact_id=superseded.id,
                key=assertion.key,
                value=assertion.value,
            )
            same_value = superseded
    if same_value is not None:
        if not any(s.event_id == event.id for s in same_value.sources):
            same_value.sources.append(source)
        if same_value.last_supported is None or event.occurred_at > same_value.last_supported:
            same_value.last_supported = event.occurred_at
        state.log(
            event.occurred_at,
            "semantic",
            "fact_corroborated",
            fact_id=same_value.id,
            key=assertion.key,
            sources=len(same_value.sources),
            origins=same_value.distinct_origins,
        )
        return same_value, "corroborated"

    fact = MemoryFact(
        id=new_id(),
        subject=assertion.subject,
        key=assertion.key,
        value=assertion.value,
        statement=assertion.statement
        or f"{assertion.subject}: {assertion.key} = {assertion.value}",
        sources=[source],
        first_seen=event.occurred_at,
        last_supported=event.occurred_at,
    )
    state.facts[fact.id] = fact
    state.log(
        event.occurred_at,
        "semantic",
        "fact_created",
        fact_id=fact.id,
        key=assertion.key,
        value=assertion.value,
        competing_values=len(siblings),
    )
    return fact, "created"
