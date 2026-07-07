"""The naive baseline MemoryOS is measured against: last-assertion-wins.

This is what "a chatbot with retrieval attached" effectively does — the most
recently stored claim about a topic is treated as the truth, with no
corroboration, no contradiction handling, no decay, and no gate: it always
acts. The eval harness and the /api/ask compare mode both use it.
"""

from __future__ import annotations

from .memory.core import MemoryEvent


def baseline_answer(events: list[MemoryEvent], subject: str, key: str) -> dict:
    latest_value: str | None = None
    latest_event: MemoryEvent | None = None
    for event in sorted(events, key=lambda e: e.occurred_at):
        for assertion in event.assertions:
            if assertion.subject == subject and assertion.key == key:
                latest_value = assertion.value
                latest_event = event
    return {
        "key": key,
        "value": latest_value,
        "gate": "act",  # the baseline never doubts itself
        "confidence": None,  # and it cannot say why it believes anything
        "source": (
            {
                "event_id": latest_event.id,
                "origin": latest_event.type,
                "occurred_at": latest_event.occurred_at.isoformat(),
            }
            if latest_event
            else None
        ),
    }
