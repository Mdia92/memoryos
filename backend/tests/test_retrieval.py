"""Hybrid retrieval: semantic search over episodic events, no Qwen required."""

import pytest

from app.memory.core import MemoryEvent, MemoryState, new_id
from app.retrieval import semantic_search

from .conftest import NOW, make_event


@pytest.mark.asyncio
async def test_semantic_search_returns_top_k_events():
    state = MemoryState()
    state.events = [
        make_event("morning", key="meeting_time_preference"),
        make_event("Rust", key="primary_language"),
        make_event("Berlin", key="city_of_residence"),
    ]
    hits, _ = await semantic_search(state, "where does the user live", k=2)
    assert len(hits) == 2
    # top hit should mention Berlin (bag-of-words fallback matches "user"/"city"/"live")
    assert any("Berlin" in h.event.content for h in hits)


@pytest.mark.asyncio
async def test_semantic_search_empty_state():
    state = MemoryState()
    hits, provider = await semantic_search(state, "anything", k=3)
    assert hits == []
    assert provider == "empty"


@pytest.mark.asyncio
async def test_semantic_search_never_calls_llm_without_key(monkeypatch):
    """No API key → falls back to local hash embedder; still returns results."""
    from app import qwen_client

    monkeypatch.setattr(qwen_client, "get_client", lambda: None)
    state = MemoryState()
    state.events = [
        MemoryEvent(
            id=new_id(),
            session_id=1,
            type="note",
            content=f"note {i}: user prefers option {i}",
            occurred_at=NOW,
            assertions=[],
        )
        for i in range(5)
    ]
    hits, provider = await semantic_search(state, "user preferences", k=3)
    assert len(hits) == 3
    assert provider == "local-hash"
