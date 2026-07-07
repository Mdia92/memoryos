"""The Evidence Auditor — never trust memory without checking the evidence.

Runs after every ingest (event-driven, not prompt-driven):
  1. Detect contradictions: competing active values for the same (subject, key).
  2. Try to resolve them from evidence alone — the side whose confidence
     leads by `supersede_margin` wins; the loser is superseded, not deleted,
     so the audit trail keeps the full history.
  3. When evidence cannot decide (scores within the margin), escalate to the
     user with a clarification request instead of guessing.

All checks are deterministic fast-path logic. The auditor never invents; it
only weighs evidence that the memory layers already recorded.
"""

from __future__ import annotations

from datetime import datetime

from .memory.core import Contradiction, MemoryState, new_id


def detect_contradictions(state: MemoryState, now: datetime) -> list[dict]:
    """Open a contradiction record for every disagreeing pair of active facts."""
    notifications: list[dict] = []
    by_key: dict[tuple[str, str], list] = {}
    for fact in state.active_facts():
        by_key.setdefault((fact.subject, fact.key), []).append(fact)

    for (subject, key), facts in by_key.items():
        if len(facts) < 2:
            continue
        facts.sort(key=lambda f: f.first_seen)
        incumbent = facts[0]
        for challenger in facts[1:]:
            already = any(
                c.status == "open"
                and {c.fact_a_id, c.fact_b_id} == {incumbent.id, challenger.id}
                for c in state.contradictions.values()
            )
            if already:
                continue
            record = Contradiction(
                id=new_id(),
                subject=subject,
                key=key,
                fact_a_id=incumbent.id,
                fact_b_id=challenger.id,
                detected_at=now,
            )
            state.contradictions[record.id] = record
            state.log(
                now,
                "auditor",
                "contradiction_detected",
                contradiction_id=record.id,
                key=key,
                value_a=incumbent.value,
                value_b=challenger.value,
            )
            notifications.append(
                {
                    "type": "contradiction_detected",
                    "contradiction_id": record.id,
                    "key": key,
                    "incumbent": {"fact_id": incumbent.id, "value": incumbent.value},
                    "challenger": {"fact_id": challenger.id, "value": challenger.value},
                }
            )
    return notifications


def resolve_contradictions(state: MemoryState, now: datetime, policy: dict) -> list[dict]:
    """Resolve what the evidence can decide; escalate what it cannot."""
    notifications: list[dict] = []
    margin = policy["auditor"]["supersede_margin"]
    noise_floor = policy["auditor"]["noise_floor"]

    for record in state.contradictions.values():
        if record.status != "open":
            continue
        fact_a = state.facts.get(record.fact_a_id)
        fact_b = state.facts.get(record.fact_b_id)
        if fact_a is None or fact_b is None or not (fact_a.active and fact_b.active):
            record.status = "dismissed"
            record.resolution = "one side no longer active"
            record.resolved_at = now
            continue

        # Timeline awareness: totals alone cannot distinguish noise from a
        # genuine preference change. What matters is whether the challenge is
        # SUSTAINED — independent evidence keeps arriving after the incumbent
        # stopped being supported.
        incumbent, challenger = (
            (fact_a, fact_b) if fact_a.first_seen <= fact_b.first_seen else (fact_b, fact_a)
        )
        sustained = [
            s
            for s in challenger.sources
            if incumbent.last_supported and s.occurred_at > incumbent.last_supported
        ]
        if len(sustained) >= 2 and len({s.origin for s in sustained}) >= 2:
            winner, loser = challenger, incumbent
            resolution = (
                f"preference change: {len(sustained)} pieces of independent evidence for "
                f"'{challenger.value}' arrived after the last support for '{incumbent.value}' "
                f"({incumbent.last_supported:%Y-%m-%d})"
            )
            loser.active = False
            loser.superseded_by = winner.id
            record.status = "resolved_superseded"
            record.resolution = resolution
            record.resolved_at = now
            state.log(
                now,
                "auditor",
                "contradiction_resolved",
                contradiction_id=record.id,
                winner=winner.value,
                loser=loser.value,
                resolution=resolution,
            )
            notifications.append(
                {
                    "type": "contradiction_resolved",
                    "contradiction_id": record.id,
                    "key": record.key,
                    "winner": winner.value,
                    "loser": loser.value,
                    "resolution": resolution,
                }
            )
            continue

        winner, loser = (
            (fact_a, fact_b) if fact_a.confidence >= fact_b.confidence else (fact_b, fact_a)
        )
        gap = winner.confidence - loser.confidence

        if (
            loser.confidence < noise_floor
            and len(loser.sources) == 1
            and (
                loser.last_supported is None
                or (winner.last_supported and winner.last_supported > loser.last_supported)
            )
        ):
            # A single stray claim, already contradicted by newer evidence.
            resolution = "challenger below noise floor with a single uncorroborated source"
        elif gap > margin:
            resolution = (
                f"evidence favors '{winner.value}' "
                f"({winner.confidence:.2f} vs {loser.confidence:.2f}, gap {gap:.2f} > {margin})"
            )
        else:
            # Evidence cannot decide — ask instead of guessing. Escalate once.
            if not record.resolution:
                record.resolution = "awaiting user clarification"
                notifications.append(
                    {
                        "type": "clarification_needed",
                        "contradiction_id": record.id,
                        "key": record.key,
                        "question": (
                            f"I hold conflicting evidence about '{record.key}': "
                            f"'{fact_a.value}' ({fact_a.confidence:.0%}, "
                            f"{len(fact_a.sources)} sources) vs "
                            f"'{fact_b.value}' ({fact_b.confidence:.0%}, "
                            f"{len(fact_b.sources)} sources). "
                            "Which is correct?"
                        ),
                        "options": [
                            {"fact_id": fact_a.id, "value": fact_a.value},
                            {"fact_id": fact_b.id, "value": fact_b.value},
                        ],
                    }
                )
                state.log(now, "auditor", "clarification_requested", contradiction_id=record.id)
            continue

        loser.active = False
        loser.superseded_by = winner.id
        record.status = "resolved_superseded"
        record.resolution = resolution
        record.resolved_at = now
        state.log(
            now,
            "auditor",
            "contradiction_resolved",
            contradiction_id=record.id,
            winner=winner.value,
            loser=loser.value,
            resolution=resolution,
        )
        notifications.append(
            {
                "type": "contradiction_resolved",
                "contradiction_id": record.id,
                "key": record.key,
                "winner": winner.value,
                "loser": loser.value,
                "resolution": resolution,
            }
        )
    return notifications


def user_resolve(
    state: MemoryState, contradiction_id: str, chosen_fact_id: str, now: datetime
) -> dict:
    """Human-in-the-loop resolution — user confirmation is the strongest evidence."""
    record = state.contradictions[contradiction_id]
    chosen = state.facts[chosen_fact_id]
    other_id = record.fact_b_id if chosen_fact_id == record.fact_a_id else record.fact_a_id
    other = state.facts[other_id]

    chosen.user_confirmation = "confirmed"
    other.user_confirmation = "corrected"
    other.active = False
    other.superseded_by = chosen.id
    record.status = "resolved_by_user"
    record.resolution = f"user confirmed '{chosen.value}'"
    record.resolved_at = now
    state.log(
        now,
        "user",
        "contradiction_resolved_by_user",
        contradiction_id=contradiction_id,
        confirmed=chosen.value,
        corrected=other.value,
    )
    return {
        "type": "contradiction_resolved",
        "contradiction_id": contradiction_id,
        "key": record.key,
        "winner": chosen.value,
        "loser": other.value,
        "resolution": record.resolution,
    }
