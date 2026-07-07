"""Layer 3 — Pattern. Knowledge nobody stated, discovered from episodes.

Detectors are deterministic scans over the episodic layer (fast path, zero
tokens). A candidate pattern is promoted to trusted knowledge only when
enough sourced episodes agree — min_support occurrences across min_sessions
distinct sessions, from confidence_policy.yaml. Qwen (slow path) is used
only to phrase the human-readable description of an already-proven pattern.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .core import MemoryEvent, MemoryState, PatternRecord, new_id

# A detector maps the full ordered event list to a list of
# (pattern_name, default_description, supporting_event) hits.
Detector = Callable[[list[MemoryEvent]], list[tuple[str, str, MemoryEvent]]]


def _detect_post_break_reschedules(events: list[MemoryEvent]) -> list:
    """Calendar reschedules that happen right after a gap of >= 3 days."""
    hits = []
    ordered = sorted(events, key=lambda e: e.occurred_at)
    last_seen: datetime | None = None
    for ev in ordered:
        if (
            ev.type == "calendar"
            and ev.meta.get("action") == "reschedule"
            and last_seen is not None
            and (ev.occurred_at - last_seen).days >= 3
        ):
            hits.append(
                (
                    "post_break_reschedules",
                    "Meetings are frequently rescheduled right after long weekends or breaks.",
                    ev,
                )
            )
        last_seen = ev.occurred_at
    return hits


def _detect_monday_reschedules(events: list[MemoryEvent]) -> list:
    """Reschedules that cluster on Mondays."""
    return [
        (
            "monday_reschedules",
            "Monday meetings are rescheduled more often than any other weekday.",
            ev,
        )
        for ev in events
        if ev.type == "calendar"
        and ev.meta.get("action") == "reschedule"
        and ev.occurred_at.weekday() == 0
    ]


DETECTORS: list[Detector] = [_detect_post_break_reschedules, _detect_monday_reschedules]


def scan_patterns(state: MemoryState, now: datetime, policy: dict) -> list[dict]:
    """Re-run all detectors; promote candidates that earned enough evidence.

    Idempotent: support lists are rebuilt from the episodic layer each scan,
    so a pattern can never claim more evidence than the events actually hold.
    """
    notifications: list[dict] = []
    min_support = policy["patterns"]["min_support"]
    min_sessions = policy["patterns"]["min_sessions"]

    hits_by_name: dict[str, list] = {}
    for detector in DETECTORS:
        for name, description, event in detector(state.events):
            hits_by_name.setdefault(name, []).append((description, event))

    for name, hits in hits_by_name.items():
        record = next((p for p in state.patterns.values() if p.name == name), None)
        if record is None:
            record = PatternRecord(id=new_id(), name=name, description=hits[0][0])
            state.patterns[record.id] = record
        record.support_event_ids = [ev.id for _, ev in hits]
        record.sessions = sorted({ev.session_id for _, ev in hits})
        support = len(record.support_event_ids)
        record.confidence = round(
            min(support / (min_support * 2), 1.0) * min(len(record.sessions) / min_sessions, 1.0), 4
        )
        earned = support >= min_support and len(record.sessions) >= min_sessions
        if earned and not record.promoted:
            record.promoted = True
            state.log(
                now,
                "pattern",
                "pattern_promoted",
                pattern_id=record.id,
                name=name,
                support=support,
                sessions=record.sessions,
            )
            notifications.append(
                {
                    "type": "pattern_promoted",
                    "pattern_id": record.id,
                    "name": name,
                    "description": record.description,
                    "support": support,
                    "sessions": record.sessions,
                }
            )
    return notifications
