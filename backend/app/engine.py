"""The perceive → reason → decide → execute → verify pipeline for one event.

This is the fast path: pure deterministic memory dynamics, zero tokens.
The slow path (Qwen) only enters upstream of this pipeline, when a raw
unstructured event needs its assertions extracted (`app.extraction`).
"""

from __future__ import annotations

from datetime import datetime

from .evidence_auditor import detect_contradictions, resolve_contradictions
from .memory.core import MemoryEvent, MemoryState
from .memory.decay import apply_decay
from .memory.episodic import record_event
from .memory.pattern import scan_patterns
from .memory.semantic import integrate_assertion
from .verification import run_verification


def ingest_event(
    state: MemoryState, event: MemoryEvent, policy: dict, now: datetime | None = None
) -> list[dict]:
    """Fold one event through all four layers plus auditor and verifier.

    Returns the notifications this event produced (contradictions found or
    resolved, clarifications needed, patterns promoted, stale memories,
    verifications) — the event-driven surface of the system.
    """
    now = now or event.occurred_at
    notifications: list[dict] = []

    # 1. Episodic: record, never interpret.
    record_event(state, event)

    # 2. Semantic: merge each assertion into the fact store.
    for assertion in event.assertions:
        integrate_assertion(state, event, assertion)

    # 3. Decay: recompute every confidence with fresh timestamps.
    notifications += apply_decay(state, now, policy)

    # 4. Auditor: find disagreements, resolve what evidence can decide.
    notifications += detect_contradictions(state, now)
    notifications += resolve_contradictions(state, now, policy)

    # 5. Verifier: promote facts the world kept confirming.
    notifications += run_verification(state, now)

    # 6. Patterns: promote knowledge that earned enough sourced episodes.
    notifications += scan_patterns(state, now, policy)

    # Auditor and verifier may have changed inputs to the formula — refresh.
    apply_decay(state, now, policy)
    return notifications
