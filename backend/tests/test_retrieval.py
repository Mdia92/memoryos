"""Hybrid retrieval: semantic search over episodic events, no Qwen required."""

import pytest

from app.memory.core import MemoryEvent, MemoryState, new_id
from app.retrieval import semantic_search

from .conftest import NOW, make_event


@pytest.fixture(autouse=True)
def _force_local_embedder(monkeypatch):
    """Every retrieval test runs against the deterministic local hash
    embedder, regardless of whether an API key is configured. Keeps results
    reproducible and independent of test ordering."""
    from app import qwen_client

    monkeypatch.setattr(qwen_client, "get_client", lambda: None)


@pytest.mark.asyncio
async def test_semantic_search_returns_top_k_events():
    state = MemoryState()
    state.events = [
        make_event("morning", key="meeting_time_preference"),
        make_event("Rust", key="primary_language"),
        make_event("Berlin", key="city_of_residence"),
    ]
    hits, provider = await semantic_search(state, "user city residence Berlin", k=2)
    assert len(hits) == 2
    assert provider == "local-hash"
    # The local hash embedder matches on token overlap; Berlin+city_of_residence
    # in the target event share the most tokens with the query.
    assert "Berlin" in hits[0].event.content


@pytest.mark.asyncio
async def test_semantic_search_empty_state():
    state = MemoryState()
    hits, provider = await semantic_search(state, "anything", k=3)
    assert hits == []
    assert provider == "empty"


@pytest.mark.asyncio
async def test_semantic_search_never_calls_llm_without_key():
    """No API key → falls back to local hash embedder; still returns results."""
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
