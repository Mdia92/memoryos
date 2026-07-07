"""Layer 1 — Episodic. Raw events with complete provenance.

Nothing is interpreted here. Every email, meeting, note, task, and chat
message is recorded with its origin and timestamp, so any semantic fact can
always be traced back to the exact moments that produced it.
"""

from __future__ import annotations

from .core import MemoryEvent, MemoryState


def record_event(state: MemoryState, event: MemoryEvent) -> MemoryEvent:
    state.events.append(event)
    state.log(
        event.occurred_at,
        "episodic",
        "event_recorded",
        event_id=event.id,
        type=event.type,
        session_id=event.session_id,
        assertions=len(event.assertions),
    )
    return event


def events_for_session(state: MemoryState, session_id: int) -> list[MemoryEvent]:
    return [e for e in state.events if e.session_id == session_id]


def get_event(state: MemoryState, event_id: str) -> MemoryEvent | None:
    return next((e for e in state.events if e.id == event_id), None)
