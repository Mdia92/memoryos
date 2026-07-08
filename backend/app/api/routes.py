"""HTTP API. All memory mutations run through the deterministic engine and
persist a snapshot; every meaningful outcome is also published on the SSE
event bus so the dashboard reacts live."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ..baseline import baseline_answer
from ..config import get_policy
from ..db import get_sessionmaker
from ..decision import decide
from ..engine import ingest_event
from ..events import bus, sse_format
from ..evidence_auditor import user_resolve
from ..extraction import extract_assertions, map_question_to_key, phrase_answer
from ..memory.core import Assertion, MemoryEvent, MemoryState, new_id
from ..qwen_client import qwen_available
from ..schemas import AskIn, EvalRunIn, EventIn, ResolveIn, SeedIn
from ..store import list_eval_runs, save_eval_run, save_state

router = APIRouter()


def _now() -> datetime:
    return datetime.now(UTC)


def _state(request: Request) -> MemoryState:
    return request.app.state.memory


async def _persist(request: Request) -> None:
    async with get_sessionmaker()() as session:
        await save_state(session, request.app.state.memory)


def _known_keys(state: MemoryState) -> list[str]:
    from evals.dataset import TRUTH_KEYS

    keys = {f.key for f in state.facts.values()}
    keys.update(tk.key for tk in TRUTH_KEYS)
    return sorted(keys)


def _fact_payload(state: MemoryState, fact, policy: dict, now: datetime) -> dict:
    from ..confidence import explain_confidence

    return {
        "id": fact.id,
        "subject": fact.subject,
        "key": fact.key,
        "value": fact.value,
        "statement": fact.statement,
        "confidence": fact.confidence,
        "verification": fact.verification,
        "user_confirmation": fact.user_confirmation,
        "active": fact.active,
        "stale": fact.stale,
        "superseded_by": fact.superseded_by,
        "first_seen": fact.first_seen.isoformat() if fact.first_seen else None,
        "last_supported": fact.last_supported.isoformat() if fact.last_supported else None,
        "sources": [
            {
                "event_id": s.event_id,
                "origin": s.origin,
                "occurred_at": s.occurred_at.isoformat(),
                "excerpt": s.excerpt,
            }
            for s in fact.sources
        ],
        "breakdown": explain_confidence(fact, now, policy),
    }


# ── Health ──────────────────────────────────────────────────────────


@router.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "qwen_available": qwen_available(),
        "facts": len(_state(request).facts),
        "events": len(_state(request).events),
    }


# ── Ingest ──────────────────────────────────────────────────────────


@router.post("/api/events")
async def create_event(request: Request, body: EventIn):
    state = _state(request)
    policy = get_policy()
    occurred = body.occurred_at or _now()
    session_id = body.session_id or (max((e.session_id for e in state.events), default=0) or 1)

    provider = "structured-input"
    if body.assertions is not None:
        assertions = [
            Assertion(subject=a.subject, key=a.key, value=a.value, statement=a.statement)
            for a in body.assertions
        ]
    else:
        # Slow path: Qwen extracts structured claims from the raw text.
        assertions, provider = await extract_assertions(body.content, _known_keys(state))

    event = MemoryEvent(
        id=new_id(),
        session_id=session_id,
        type=body.type,
        content=body.content,
        occurred_at=occurred,
        assertions=assertions,
        meta=body.meta,
    )
    async with request.app.state.lock:
        notifications = ingest_event(state, event, policy, now=_now())
        await _persist(request)
    for n in notifications:
        bus.publish(n)

    return {
        "event_id": event.id,
        "extraction_provider": provider,
        "assertions": [
            {"subject": a.subject, "key": a.key, "value": a.value, "statement": a.statement}
            for a in assertions
        ],
        "notifications": notifications,
    }


@router.get("/api/events")
async def list_events(request: Request, limit: int = 100):
    events = sorted(_state(request).events, key=lambda e: e.occurred_at, reverse=True)[:limit]
    return [
        {
            "id": e.id,
            "session_id": e.session_id,
            "type": e.type,
            "content": e.content,
            "occurred_at": e.occurred_at.isoformat(),
            "assertions": [
                {"key": a.key, "value": a.value, "statement": a.statement} for a in e.assertions
            ],
            "meta": e.meta,
        }
        for e in events
    ]


# ── Memory browsing ────────────────────────────────────────────────


@router.get("/api/facts")
async def list_facts(request: Request, include_inactive: bool = False):
    state = _state(request)
    policy = get_policy()
    now = _now()
    facts = state.facts.values() if include_inactive else state.active_facts()
    ordered = sorted(facts, key=lambda f: f.confidence, reverse=True)
    return [_fact_payload(state, f, policy, now) for f in ordered]


@router.get("/api/facts/{fact_id}")
async def get_fact(request: Request, fact_id: str):
    state = _state(request)
    fact = state.facts.get(fact_id)
    if fact is None:
        raise HTTPException(404, "fact not found")
    payload = _fact_payload(state, fact, get_policy(), _now())
    payload["contradictions"] = [
        {
            "id": c.id,
            "status": c.status,
            "resolution": c.resolution,
            "other_fact_id": c.fact_b_id if c.fact_a_id == fact_id else c.fact_a_id,
        }
        for c in state.contradictions.values()
        if fact_id in (c.fact_a_id, c.fact_b_id)
    ]
    return payload


@router.get("/api/contradictions")
async def list_contradictions(request: Request):
    state = _state(request)
    out = []
    for c in sorted(state.contradictions.values(), key=lambda c: c.detected_at, reverse=True):
        fact_a, fact_b = state.facts.get(c.fact_a_id), state.facts.get(c.fact_b_id)
        out.append(
            {
                "id": c.id,
                "subject": c.subject,
                "key": c.key,
                "status": c.status,
                "resolution": c.resolution,
                "detected_at": c.detected_at.isoformat(),
                "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
                "fact_a": fact_a
                and {
                    "id": fact_a.id,
                    "value": fact_a.value,
                    "confidence": fact_a.confidence,
                    "sources": len(fact_a.sources),
                    "active": fact_a.active,
                },
                "fact_b": fact_b
                and {
                    "id": fact_b.id,
                    "value": fact_b.value,
                    "confidence": fact_b.confidence,
                    "sources": len(fact_b.sources),
                    "active": fact_b.active,
                },
            }
        )
    return out


@router.post("/api/contradictions/{contradiction_id}/resolve")
async def resolve_contradiction(request: Request, contradiction_id: str, body: ResolveIn):
    state = _state(request)
    if contradiction_id not in state.contradictions:
        raise HTTPException(404, "contradiction not found")
    if body.chosen_fact_id not in state.facts:
        raise HTTPException(404, "fact not found")
    async with request.app.state.lock:
        notification = user_resolve(state, contradiction_id, body.chosen_fact_id, _now())
        # user confirmation changes the confidence inputs — refresh caches
        from ..memory.decay import apply_decay

        apply_decay(state, _now(), get_policy())
        await _persist(request)
    bus.publish(notification)
    return notification


@router.get("/api/patterns")
async def list_patterns(request: Request):
    state = _state(request)
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "promoted": p.promoted,
            "confidence": p.confidence,
            "support": len(p.support_event_ids),
            "sessions": p.sessions,
            "support_event_ids": p.support_event_ids,
        }
        for p in sorted(state.patterns.values(), key=lambda p: p.confidence, reverse=True)
    ]


@router.get("/api/audit")
async def audit_trail(request: Request, limit: int = 200):
    entries = _state(request).audit[-limit:]
    return [
        {"ts": a.ts.isoformat(), "actor": a.actor, "action": a.action, "detail": a.detail}
        for a in reversed(entries)
    ]


@router.get("/api/stats")
async def stats(request: Request):
    from ..decision import deterministic_decision_count
    from ..fallback_chain import counter as slow_counter

    state = _state(request)
    active = state.active_facts()
    corroborated = [f for f in active if f.distinct_origins >= 2]
    slow = slow_counter.snapshot()
    det_decisions = deterministic_decision_count()
    # Each event flows through 4 deterministic passes (episodic, semantic,
    # decay+auditor, verification+pattern). Each decide() is another. The
    # rules_fallbacks are Qwen invocations we intentionally routed away from.
    det_ops = len(state.events) * 4 + det_decisions + slow["rules_fallbacks"]
    total_ops = det_ops + slow["qwen_calls"]
    fast_path_pct = round(det_ops / total_ops, 4) if total_ops else 0.0
    return {
        "events_total": len(state.events),
        "facts_active": len(active),
        "facts_verified": sum(1 for f in active if f.verification == "verified"),
        "pct_corroborated": round(len(corroborated) / len(active), 4) if active else 0.0,
        "avg_confidence": round(sum(f.confidence for f in active) / len(active), 4)
        if active
        else 0.0,
        "stale_facts": sum(1 for f in active if f.stale),
        "contradictions_open": sum(
            1 for c in state.contradictions.values() if c.status == "open"
        ),
        "contradictions_resolved": sum(
            1 for c in state.contradictions.values() if c.status.startswith("resolved")
        ),
        "patterns_promoted": sum(1 for p in state.patterns.values() if p.promoted),
        "qwen_available": qwen_available(),
        "cost": {
            "qwen_calls": slow["qwen_calls"],
            "qwen_input_tokens_est": slow["qwen_input_tokens_est"],
            "qwen_by_model": slow["by_model"],
            "rules_fallbacks": slow["rules_fallbacks"],
            "deterministic_decisions": det_decisions,
            "deterministic_ops": det_ops,
            "fast_path_pct": fast_path_pct,
        },
    }


# ── Ask (the demo moment) ──────────────────────────────────────────


@router.post("/api/ask")
async def ask(request: Request, body: AskIn):
    state = _state(request)
    policy = get_policy()
    now = _now()

    key_values: dict[str, list[str]] = {}
    for fact in state.facts.values():
        key_values.setdefault(fact.key, []).append(fact.value)
    key, mapping_provider = await map_question_to_key(
        body.question, _known_keys(state), key_values
    )
    if key is None:
        return {
            "question": body.question,
            "key": None,
            "answer": "I don't hold any memory related to that question yet.",
            "decision": None,
            "baseline": None,
            "providers": {"mapping": mapping_provider},
        }

    decision = decide(state, "user", key, now, policy)
    answer, answer_provider = await phrase_answer(body.question, decision)
    response = {
        "question": body.question,
        "key": key,
        "answer": answer,
        "decision": decision,
        "providers": {"mapping": mapping_provider, "answer": answer_provider},
    }
    if body.compare:
        base = baseline_answer(state.events, "user", key)
        response["baseline"] = {
            **base,
            "answer": (
                f"You prefer {base['value']}."
                if base["value"]
                else "I don't know."
            ),
            "note": "last-assertion-wins: no sources, no confidence, always acts",
        }
    return response


# ── Eval ───────────────────────────────────────────────────────────


@router.post("/api/eval/run")
async def trigger_eval(request: Request, body: EvalRunIn):
    from evals.harness import run_eval

    # Deterministic and CPU-light, but run off the event loop anyway.
    outcome = await asyncio.to_thread(run_eval, body.sessions, body.seed)
    results = outcome["results"]
    async with get_sessionmaker()() as session:
        run_id = await save_eval_run(
            session,
            label=body.label,
            config={"sessions": body.sessions, "seed": body.seed},
            results=results,
            created_at=_now(),
        )
    bus.publish(
        {
            "type": "eval_completed",
            "run_id": run_id,
            "summary": results["summary"],
        }
    )
    return {"run_id": run_id, **results}


@router.get("/api/eval/runs")
async def eval_runs():
    async with get_sessionmaker()() as session:
        return await list_eval_runs(session)


@router.get("/api/eval/latest")
async def eval_latest():
    async with get_sessionmaker()() as session:
        runs = await list_eval_runs(session)
    if not runs:
        raise HTTPException(404, "no eval runs yet — POST /api/eval/run first")
    return runs[0]


# ── Demo helpers ───────────────────────────────────────────────────


@router.post("/api/demo/seed")
async def demo_seed(request: Request, body: SeedIn):
    """Replay the synthetic dataset into live memory (sessions 1..N).

    Seeding 3 sessions shows a cautious young memory; 20 shows a confident
    one — the cross-session story, live on the dashboard.
    """
    from evals.dataset import generate_dataset

    policy = get_policy()
    state = MemoryState()
    notifications: list[dict] = []
    by_session = generate_dataset(sessions=body.sessions)
    for s in range(1, body.sessions + 1):
        for event in by_session[s]:
            notifications += ingest_event(state, event, policy)
    async with request.app.state.lock:
        request.app.state.memory = state
        await _persist(request)
    bus.publish(
        {
            "type": "memory_seeded",
            "sessions": body.sessions,
            "events": len(state.events),
            "facts": len(state.active_facts()),
            "notifications": len(notifications),
        }
    )
    return {
        "sessions": body.sessions,
        "events": len(state.events),
        "facts_active": len(state.active_facts()),
        "notifications_emitted": len(notifications),
    }


@router.post("/api/demo/reset")
async def demo_reset(request: Request):
    from ..decision import reset_deterministic_decisions
    from ..fallback_chain import counter as slow_counter

    async with request.app.state.lock:
        request.app.state.memory = MemoryState()
        slow_counter.reset()
        reset_deterministic_decisions()
        await _persist(request)
    bus.publish({"type": "memory_reset"})
    return {"status": "reset"}


# ── Live notifications ─────────────────────────────────────────────


@router.get("/api/stream")
async def stream(request: Request):
    queue = bus.subscribe()

    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    notification = await asyncio.wait_for(queue.get(), timeout=15)
                    yield {"event": "notification", "data": sse_format(notification)}
                except TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(generator())
