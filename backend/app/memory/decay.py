"""Layer 4 — Decay. Unsupported memories weaken; corroborated ones endure.

A fact supported by one uncorroborated source has a short half-life. A fact
confirmed by several independent origins fades three times slower. Decay is
pure math over timestamps — deterministic, free, and runs on every pass.
"""

from __future__ import annotations

from datetime import datetime

from .core import MemoryState


def half_life_days(distinct_origins: int, policy: dict) -> float:
    d = policy["decay"]
    if distinct_origins >= d["multi_source_min"]:
        return float(d["half_life_days"]["multi_source"])
    if distinct_origins == 2:
        return float(d["half_life_days"]["two_sources"])
    return float(d["half_life_days"]["single_source"])


def recency_score(fact, now: datetime, policy: dict) -> float:
    """Exponential decay of support: 0.5 ** (age / half_life)."""
    if fact.last_supported is None:
        return 0.0
    age_days = max((now - fact.last_supported).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (age_days / half_life_days(fact.distinct_origins, policy))


def apply_decay(state: MemoryState, now: datetime, policy: dict) -> list[dict]:
    """Recompute cached confidence for every active fact; flag stale memories.

    Returns a list of notifications (stale facts newly detected) so the
    event bus can wake the auditor — memory maintenance is event-driven,
    not prompt-driven.
    """
    from ..confidence import compute_confidence  # local import to avoid a cycle

    notifications: list[dict] = []
    stale_below = policy["decay"]["stale_below"]
    for fact in state.active_facts():
        fact.confidence = compute_confidence(fact, now, policy)
        is_stale = recency_score(fact, now, policy) < stale_below
        if is_stale and not fact.stale:
            notifications.append(
                {
                    "type": "stale_memory",
                    "fact_id": fact.id,
                    "statement": fact.statement,
                    "confidence": fact.confidence,
                }
            )
            state.log(now, "decay", "fact_marked_stale", fact_id=fact.id, key=fact.key)
        fact.stale = is_stale
    return notifications
