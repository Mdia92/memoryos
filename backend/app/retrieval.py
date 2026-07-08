"""Semantic retrieval over the episodic layer.

Used as a hybrid fallback for the ask path: when key-mapping does not find
a tracked fact, we embed the question and retrieve top-k evidence events
directly. Qwen then answers over those events. This is a mini-RAG that
runs against MemoryOS's own event store, so answers still cite their
sources (event id, origin, timestamp) — no source-less bluff.

Two backends: DashScope embeddings (primary) via app.fallback_chain and the
local hashing embedder (fallback). Both are deterministic given the same
inputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .embeddings import cosine, local_hash_embeddings
from .fallback_chain import run_embedding_task, run_text_task
from .memory.core import MemoryEvent, MemoryState


@dataclass
class RetrievedEvent:
    event: MemoryEvent
    score: float


HYBRID_ANSWER_SYSTEM = """You are MemoryOS, an evidence-based memory agent.

Answer the user's question using ONLY the retrieved events provided.
Rules:
- Extract the answer from the events even when it is stated once or requires
  simple joining across events (e.g. a date from one event, a fact from another).
- Cite the event ids you used. If two events directly disagree on the answer,
  surface both values and mark the newer one as current.
- Only say "I don't hold evidence about that" when NONE of the retrieved events
  mentions the topic at all.
- Be concise (1-3 sentences). Never invent details the events don't support."""


async def semantic_search(
    state: MemoryState,
    query: str,
    k: int = 5,
) -> tuple[list[RetrievedEvent], str]:
    """Return the top-k events most similar to the query."""
    events = list(state.events)
    if not events:
        return [], "empty"

    corpus = [_event_text(e) for e in events]
    all_texts = [query] + corpus
    vectors, provider = await run_embedding_task(all_texts)
    if not vectors:
        vectors = local_hash_embeddings(all_texts)
        provider = "local-hash"

    q_vec, doc_vecs = vectors[0], vectors[1:]
    scored = [
        RetrievedEvent(event=e, score=cosine(q_vec, v))
        for e, v in zip(events, doc_vecs, strict=False)
    ]
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:k], provider


def _event_text(event: MemoryEvent) -> str:
    parts = [event.content or ""]
    for a in event.assertions:
        parts.append(f"[{a.key}={a.value}] {a.statement}")
    return " ".join(p for p in parts if p)


async def hybrid_answer(
    state: MemoryState,
    question: str,
    k: int = 5,
) -> tuple[str, list[RetrievedEvent], str, str]:
    """Retrieve then answer with citations.

    Returns (answer, evidence, retrieval_provider, answer_provider).
    """
    top, retrieval_provider = await semantic_search(state, question, k=k)

    if not top:
        return "I don't hold evidence about that.", [], retrieval_provider, "rules-only"

    events_payload = [
        {
            "id": r.event.id,
            "origin": r.event.type,
            "occurred_at": r.event.occurred_at.isoformat(),
            "content": (r.event.content or "")[:400],
            "assertions": [
                {"key": a.key, "value": a.value} for a in r.event.assertions
            ],
            "similarity": round(r.score, 3),
        }
        for r in top
    ]

    def rules_fallback() -> str:
        best = top[0]
        excerpt = (best.event.content or "").split(".")[0][:200]
        return (
            f'Based on event {best.event.id} ({best.event.type}, '
            f'{best.event.occurred_at.date()}): "{excerpt}"'
        )

    user = (
        f"Question: {question}\n"
        f"Retrieved events (top-{len(top)} by cosine similarity):\n"
        f"{json.dumps(events_payload, ensure_ascii=False, default=str)}"
    )
    answer, ans_provider = await run_text_task(HYBRID_ANSWER_SYSTEM, user, rules_fallback)
    return answer, top, retrieval_provider, ans_provider


async def pure_rag_answer(
    state: MemoryState,
    question: str,
    k: int = 5,
) -> tuple[str, list[RetrievedEvent], str, str]:
    """Baseline: same semantic search + Qwen answer, but without MemoryOS's
    confidence gating, contradiction resolution, or fact merging. Used only
    for baseline comparison — deliberately identical retrieval quality so
    the delta is attributable to the fact layer, not the embedder."""
    top, retrieval_provider = await semantic_search(state, question, k=k)
    if not top:
        return "I don't have relevant context.", [], retrieval_provider, "rules-only"

    events_payload = [
        {
            "content": (r.event.content or "")[:400],
            "occurred_at": r.event.occurred_at.isoformat(),
        }
        for r in top
    ]

    rag_system = (
        "You are a helpful assistant. Answer the user's question using the retrieved chat "
        "history below. Be concise. If the history does not contain the answer, guess based "
        "on what seems most likely. Never say 'I don't know'."
    )

    def rules_fallback() -> str:
        return (top[0].event.content or "")[:200]

    user = (
        f"Question: {question}\n"
        f"Retrieved chat history:\n{json.dumps(events_payload, ensure_ascii=False, default=str)}"
    )
    answer, ans_provider = await run_text_task(rag_system, user, rules_fallback)
    return answer, top, retrieval_provider, ans_provider
