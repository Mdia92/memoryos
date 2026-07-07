"""In-process event bus → Server-Sent Events.

MemoryOS is event-driven: the memory layers and the Evidence Auditor emit
notifications (contradiction detected, clarification needed, pattern
promoted, stale memory, fact verified) and the dashboard receives them live
over SSE. The system wakes itself when something meaningful happens.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, notification: dict) -> None:
        payload = {"ts": datetime.now(UTC).isoformat(), **notification}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                self._subscribers.discard(queue)


bus = EventBus()


def sse_format(notification: dict) -> str:
    return json.dumps(notification, default=str)
