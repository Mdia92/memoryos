"""Core in-memory data structures shared by the four memory layers.

The memory engine is pure Python operating on `MemoryState` — no database,
no LLM. That makes every memory dynamic (merge, decay, contradiction,
promotion) deterministic, unit-testable, and reproducible. Persistence is a
separate adapter (`app.store`), and the LLM is a separate slow path
(`app.qwen_client`) used only where genuine reasoning is required.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


def new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class SourceRef:
    """Where a piece of evidence came from. Provenance is never optional."""

    event_id: str
    origin: str  # calendar | email | note | task | chat | user
    occurred_at: datetime
    excerpt: str = ""


@dataclass
class Assertion:
    """One structured claim extracted from an event: (subject, key) = value."""

    subject: str
    key: str
    value: str
    statement: str = ""  # human-readable form


@dataclass
class MemoryEvent:
    """Episodic layer unit: a raw event, recorded, never interpreted."""

    id: str
    session_id: int
    type: str  # calendar | email | note | task | chat
    content: str
    occurred_at: datetime
    assertions: list[Assertion] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@dataclass
class MemoryFact:
    """Semantic layer unit: a deduplicated claim plus its full evidence chain."""

    id: str
    subject: str
    key: str
    value: str
    statement: str
    sources: list[SourceRef] = field(default_factory=list)
    first_seen: datetime | None = None
    last_supported: datetime | None = None
    verification: str = "unverified"  # unverified | verified | failed
    user_confirmation: str = "none"  # none | confirmed | corrected
    active: bool = True
    superseded_by: str | None = None
    confidence: float = 0.0  # cached; recomputed by the decay pass
    stale: bool = False

    @property
    def distinct_origins(self) -> int:
        return len({s.origin for s in self.sources})


@dataclass
class PatternRecord:
    """Pattern layer unit: knowledge nobody stated, discovered from episodes."""

    id: str
    name: str
    description: str
    support_event_ids: list[str] = field(default_factory=list)
    sessions: list[int] = field(default_factory=list)
    promoted: bool = False
    confidence: float = 0.0


@dataclass
class Contradiction:
    """Two active facts disagree about the same (subject, key)."""

    id: str
    subject: str
    key: str
    fact_a_id: str  # incumbent
    fact_b_id: str  # challenger
    detected_at: datetime
    status: str = "open"  # open | resolved_superseded | resolved_by_user | dismissed
    resolution: str = ""
    resolved_at: datetime | None = None


@dataclass
class AuditEntry:
    ts: datetime
    actor: str  # episodic | semantic | pattern | decay | auditor | verifier | user | qwen
    action: str
    detail: dict = field(default_factory=dict)


@dataclass
class MemoryState:
    """The whole memory of one agent, across all four layers."""

    events: list[MemoryEvent] = field(default_factory=list)
    facts: dict[str, MemoryFact] = field(default_factory=dict)
    patterns: dict[str, PatternRecord] = field(default_factory=dict)
    contradictions: dict[str, Contradiction] = field(default_factory=dict)
    audit: list[AuditEntry] = field(default_factory=list)

    def active_facts(self, subject: str | None = None, key: str | None = None) -> list[MemoryFact]:
        out = [f for f in self.facts.values() if f.active]
        if subject is not None:
            out = [f for f in out if f.subject == subject]
        if key is not None:
            out = [f for f in out if f.key == key]
        return out

    def log(self, ts: datetime, actor: str, action: str, **detail) -> None:
        self.audit.append(AuditEntry(ts=ts, actor=actor, action=action, detail=detail))
