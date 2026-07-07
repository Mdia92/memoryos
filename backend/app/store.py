"""Persistence adapter: MemoryState ⇄ PostgreSQL.

The engine operates on in-memory dataclasses (deterministic, testable); this
module is the only place that touches the database. Persistence is a full
snapshot write inside one transaction — at prototype scale (hundreds of
rows) that is simpler and more obviously correct than row-level diffing.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .memory.core import (
    Assertion,
    AuditEntry,
    Contradiction,
    MemoryEvent,
    MemoryFact,
    MemoryState,
    PatternRecord,
    SourceRef,
)
from .models import AuditRow, ContradictionRow, EvalRunRow, EventRow, FactRow, PatternRow


def _dt(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


async def save_state(session: AsyncSession, state: MemoryState) -> None:
    for table in (EventRow, FactRow, PatternRow, ContradictionRow, AuditRow):
        await session.execute(delete(table))

    session.add_all(
        EventRow(
            id=uuid.UUID(e.id),
            session_id=e.session_id,
            type=e.type,
            content=e.content,
            occurred_at=e.occurred_at,
            assertions=[
                {"subject": a.subject, "key": a.key, "value": a.value, "statement": a.statement}
                for a in e.assertions
            ],
            meta=e.meta,
        )
        for e in state.events
    )
    session.add_all(
        FactRow(
            id=uuid.UUID(f.id),
            subject=f.subject,
            key=f.key,
            value=f.value,
            statement=f.statement,
            sources=[
                {
                    "event_id": s.event_id,
                    "origin": s.origin,
                    "occurred_at": s.occurred_at.isoformat(),
                    "excerpt": s.excerpt,
                }
                for s in f.sources
            ],
            first_seen=f.first_seen,
            last_supported=f.last_supported,
            verification=f.verification,
            user_confirmation=f.user_confirmation,
            active=f.active,
            superseded_by=uuid.UUID(f.superseded_by) if f.superseded_by else None,
            confidence=f.confidence,
            stale=f.stale,
        )
        for f in state.facts.values()
    )
    session.add_all(
        PatternRow(
            id=uuid.UUID(p.id),
            name=p.name,
            description=p.description,
            support_event_ids=p.support_event_ids,
            sessions=p.sessions,
            promoted=p.promoted,
            confidence=p.confidence,
        )
        for p in state.patterns.values()
    )
    session.add_all(
        ContradictionRow(
            id=uuid.UUID(c.id),
            subject=c.subject,
            key=c.key,
            fact_a_id=uuid.UUID(c.fact_a_id),
            fact_b_id=uuid.UUID(c.fact_b_id),
            detected_at=c.detected_at,
            status=c.status,
            resolution=c.resolution,
            resolved_at=c.resolved_at,
        )
        for c in state.contradictions.values()
    )
    session.add_all(
        AuditRow(ts=a.ts, actor=a.actor, action=a.action, detail=a.detail) for a in state.audit
    )
    await session.commit()


async def load_state(session: AsyncSession) -> MemoryState:
    state = MemoryState()
    for row in (await session.execute(select(EventRow).order_by(EventRow.occurred_at))).scalars():
        state.events.append(
            MemoryEvent(
                id=str(row.id),
                session_id=row.session_id,
                type=row.type,
                content=row.content,
                occurred_at=row.occurred_at,
                assertions=[Assertion(**a) for a in row.assertions],
                meta=row.meta,
            )
        )
    for row in (await session.execute(select(FactRow))).scalars():
        state.facts[str(row.id)] = MemoryFact(
            id=str(row.id),
            subject=row.subject,
            key=row.key,
            value=row.value,
            statement=row.statement,
            sources=[
                SourceRef(
                    event_id=s["event_id"],
                    origin=s["origin"],
                    occurred_at=_dt(s["occurred_at"]),
                    excerpt=s.get("excerpt", ""),
                )
                for s in row.sources
            ],
            first_seen=row.first_seen,
            last_supported=row.last_supported,
            verification=row.verification,
            user_confirmation=row.user_confirmation,
            active=row.active,
            superseded_by=str(row.superseded_by) if row.superseded_by else None,
            confidence=row.confidence,
            stale=row.stale,
        )
    for row in (await session.execute(select(PatternRow))).scalars():
        state.patterns[str(row.id)] = PatternRecord(
            id=str(row.id),
            name=row.name,
            description=row.description,
            support_event_ids=row.support_event_ids,
            sessions=row.sessions,
            promoted=row.promoted,
            confidence=row.confidence,
        )
    for row in (await session.execute(select(ContradictionRow))).scalars():
        state.contradictions[str(row.id)] = Contradiction(
            id=str(row.id),
            subject=row.subject,
            key=row.key,
            fact_a_id=str(row.fact_a_id),
            fact_b_id=str(row.fact_b_id),
            detected_at=row.detected_at,
            status=row.status,
            resolution=row.resolution,
            resolved_at=row.resolved_at,
        )
    for row in (await session.execute(select(AuditRow).order_by(AuditRow.id))).scalars():
        state.audit.append(
            AuditEntry(ts=row.ts, actor=row.actor, action=row.action, detail=row.detail)
        )
    return state


async def save_eval_run(
    session: AsyncSession, label: str, config: dict, results: dict, created_at: datetime
) -> str:
    row = EvalRunRow(created_at=created_at, label=label, config=config, results=results)
    session.add(row)
    await session.commit()
    return str(row.id)


async def list_eval_runs(session: AsyncSession) -> list[dict]:
    rows = (
        (await session.execute(select(EvalRunRow).order_by(EvalRunRow.created_at.desc())))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "created_at": r.created_at.isoformat(),
            "label": r.label,
            "config": r.config,
            "results": r.results,
        }
        for r in rows
    ]
