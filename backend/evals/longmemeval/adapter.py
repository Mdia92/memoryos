"""Replay a LongMemEval instance's haystack into MemoryOS, then answer.

For each session in the instance:
  - each user turn becomes a `chat` MemoryEvent
  - Qwen extraction pulls structured assertions from the turn text
  - the deterministic engine (episodic → semantic → auditor → decay → pattern)
    ingests it exactly as it would in production

After all turns are ingested, the question is asked through the same
`map_question_to_key` → `decide` → `phrase_answer` pipeline used by the API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.config import get_policy
from app.decision import decide
from app.engine import ingest_event
from app.extraction import extract_assertions, map_question_to_key, phrase_answer
from app.memory.core import MemoryEvent, MemoryState, new_id
from app.retrieval import hybrid_answer, pure_rag_answer


@dataclass
class InstanceResult:
    question_id: str
    question_type: str
    question: str
    gold_answer: str
    memoryos_answer: str
    memoryos_key: str | None
    memoryos_confidence: float | None
    memoryos_gate: str | None
    memoryos_path: str  # "tracked-fact" | "hybrid-retrieval" | "abstain"
    events_ingested: int
    assertions_extracted: int
    qwen_calls: int
    rag_answer: str | None = None  # baseline for comparison


def _parse_date(s: str) -> datetime:
    """LongMemEval dates: 'YYYY/MM/DD (Ddd) HH:MM'."""
    return datetime.strptime(s.split(" (")[0] + " " + s.split(") ")[-1], "%Y/%m/%d %H:%M").replace(
        tzinfo=UTC
    )


async def replay_and_answer(
    instance: dict[str, Any],
    max_sessions: int | None = None,
    compare_rag: bool = False,
) -> InstanceResult:
    """Ingest a LongMemEval instance and answer its question."""
    state = MemoryState()
    policy = get_policy()
    events_ingested = 0
    assertions_extracted = 0
    qwen_calls = 0

    sessions = instance["haystack_sessions"]
    session_dates = instance["haystack_dates"]
    if max_sessions is not None:
        sessions = sessions[:max_sessions]
        session_dates = session_dates[:max_sessions]

    for s_idx, (session, s_date) in enumerate(zip(sessions, session_dates, strict=False), start=1):
        base_ts = _parse_date(s_date)
        for turn_idx, turn in enumerate(session):
            if turn.get("role") != "user":
                continue
            content = (turn.get("content") or "").strip()
            if not content or len(content) < 10:
                continue

            known = sorted({f.key for f in state.facts.values()})
            assertions, provider = await extract_assertions(content, known)
            if provider.startswith("qwen"):
                qwen_calls += 1
            assertions_extracted += len(assertions)

            event = MemoryEvent(
                id=new_id(),
                session_id=s_idx,
                type="chat",
                content=content[:2000],
                occurred_at=base_ts,
                assertions=assertions,
                meta={
                    "longmemeval_session": instance["haystack_session_ids"][s_idx - 1],
                    "turn": turn_idx,
                    "extraction_provider": provider,
                },
            )
            ingest_event(state, event, policy, now=base_ts)
            events_ingested += 1

    now = _parse_date(instance["question_date"])
    key_values: dict[str, list[str]] = {}
    for fact in state.facts.values():
        key_values.setdefault(fact.key, []).append(fact.value)
    known = sorted({f.key for f in state.facts.values()})

    key, map_provider = await map_question_to_key(instance["question"], known, key_values)
    if map_provider.startswith("qwen"):
        qwen_calls += 1

    path = "tracked-fact"
    confidence: float | None = None
    gate: str | None = None
    answer = ""

    if key is not None:
        decision = decide(state, "user", key, now, policy)
        confidence = decision.get("confidence")
        gate = decision.get("gate")
        if gate in ("act", "show_sources"):
            answer, ans_provider = await phrase_answer(instance["question"], decision)
            if ans_provider.startswith("qwen"):
                qwen_calls += 1
        else:
            key = None

    if key is None:
        answer, top, retr_provider, ans_provider = await hybrid_answer(
            state, instance["question"], k=5
        )
        if retr_provider.startswith("text-embedding") or retr_provider.startswith("qwen"):
            qwen_calls += 1
        if ans_provider.startswith("qwen"):
            qwen_calls += 1
        path = "hybrid-retrieval" if top else "abstain"
        gate = gate or ("show_sources" if top else "unknown")

    rag_answer: str | None = None
    if compare_rag:
        rag_answer, _, rag_retr, rag_ans_prov = await pure_rag_answer(
            state, instance["question"], k=5
        )
        if rag_retr.startswith("text-embedding") or rag_retr.startswith("qwen"):
            qwen_calls += 1
        if rag_ans_prov.startswith("qwen"):
            qwen_calls += 1

    return InstanceResult(
        question_id=instance["question_id"],
        question_type=instance["question_type"],
        question=instance["question"],
        gold_answer=str(instance["answer"]),
        memoryos_answer=answer,
        memoryos_key=key,
        memoryos_confidence=confidence,
        memoryos_gate=gate,
        memoryos_path=path,
        events_ingested=events_ingested,
        assertions_extracted=assertions_extracted,
        qwen_calls=qwen_calls,
        rag_answer=rag_answer,
    )


def result_to_dict(r: InstanceResult) -> dict:
    return {
        "question_id": r.question_id,
        "question_type": r.question_type,
        "question": r.question,
        "gold_answer": r.gold_answer,
        "memoryos_answer": r.memoryos_answer,
        "memoryos_key": r.memoryos_key,
        "memoryos_confidence": r.memoryos_confidence,
        "memoryos_gate": r.memoryos_gate,
        "memoryos_path": r.memoryos_path,
        "events_ingested": r.events_ingested,
        "assertions_extracted": r.assertions_extracted,
        "qwen_calls": r.qwen_calls,
        "rag_answer": r.rag_answer,
    }


def dumps_result(r: InstanceResult) -> str:
    return json.dumps(result_to_dict(r), ensure_ascii=False)
