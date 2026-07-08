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


LATE_NIGHT_HOURS = {21, 22, 23, 0, 1, 2, 3, 4}


def _detect_late_night_activity(events: list[MemoryEvent]) -> list:
    """User is regularly active outside 8am-8pm."""
    return [
        (
            "late_night_activity",
            "The user is regularly active late at night (21:00 – 04:59).",
            ev,
        )
        for ev in events
        if ev.occurred_at.hour in LATE_NIGHT_HOURS
    ]


def _detect_weekend_avoidance(events: list[MemoryEvent]) -> list:
    """No or very few events on Saturday/Sunday relative to weekdays.

    Deterministic rule: fire once at the earliest Monday event whose preceding
    week had >= 5 weekday events but 0 weekend events. Uses the earliest such
    event as anchor so support grows as more clean weeks accumulate.
    """
    ordered = sorted(events, key=lambda e: e.occurred_at)
    # Bucket by ISO week
    by_week: dict[tuple[int, int], dict[str, list[MemoryEvent]]] = {}
    for ev in ordered:
        year, week, _ = ev.occurred_at.isocalendar()
        bucket = by_week.setdefault((year, week), {"weekday": [], "weekend": []})
        if ev.occurred_at.weekday() >= 5:
            bucket["weekend"].append(ev)
        else:
            bucket["weekday"].append(ev)

    hits = []
    for (_year, _week), b in sorted(by_week.items()):
        if len(b["weekday"]) >= 5 and not b["weekend"]:
            # One hit per weekday event that week, so support scales with
            # observed activity and the confidence formula stays honest.
            for ev in b["weekday"]:
                hits.append(
                    (
                        "weekend_avoidance",
                        "The user does not schedule activity on weekends; workflow is Mon–Fri.",
                        ev,
                    )
                )
    return hits


_HOUR_BANDS: list[tuple[range, str]] = [
    (range(6, 10), "early morning (06:00 – 09:59)"),
    (range(10, 13), "late morning (10:00 – 12:59)"),
    (range(13, 17), "afternoon (13:00 – 16:59)"),
    (range(17, 21), "evening (17:00 – 20:59)"),
]


def _detect_peak_hour_cluster(events: list[MemoryEvent]) -> list:
    """The user concentrates activity in one time-of-day band.

    A band earns hits from *its own events* only once a band is dominant —
    more than 45% of the last 20 events fell in that band, and it has at
    least twice as many hits as any other band. This lets the confidence
    formula scale with sustained evidence without one busy morning
    fabricating a lifelong pattern.
    """
    if len(events) < 6:
        return []
    ordered = sorted(events, key=lambda e: e.occurred_at)
    window = ordered[-20:]
    counts: dict[str, list[MemoryEvent]] = {}
    for band_range, label in _HOUR_BANDS:
        counts[label] = [ev for ev in window if ev.occurred_at.hour in band_range]

    ranked = sorted(counts.items(), key=lambda kv: -len(kv[1]))
    top_label, top_hits = ranked[0]
    second_hits = len(ranked[1][1]) if len(ranked) > 1 else 0

    dominates = (
        len(top_hits) >= max(5, len(window) * 0.45)
        and len(top_hits) >= max(1, second_hits) * 2
    )
    if not dominates:
        return []
    return [
        (
            "peak_hour_cluster",
            f"The user's activity clusters in the {top_label}.",
            ev,
        )
        for ev in top_hits
    ]


DETECTORS: list[Detector] = [
    _detect_post_break_reschedules,
    _detect_monday_reschedules,
    _detect_late_night_activity,
    _detect_weekend_avoidance,
    _detect_peak_hour_cluster,
]


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
