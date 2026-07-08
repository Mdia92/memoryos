"""API integration tests — cover the demo-critical paths.

DB persistence is mocked to no-ops (the routes' correctness doesn't depend
on the DB layer; that's tested elsewhere). Focus is on: does /api/ask fall
through to hybrid retrieval when there's no tracked key; does /api/stats
expose the cost tile; do reset + seed cleanly zero and repopulate.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """A TestClient with the DB layer stubbed out."""
    async def _noop_init_db():
        return None

    async def _noop_save_state(session, state):
        return None

    async def _noop_load_state(session):
        from app.memory.core import MemoryState
        return MemoryState()

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    class _FakeSessionmaker:
        def __call__(self):
            return _FakeSession()

    monkeypatch.setattr("app.main.init_db", _noop_init_db)
    monkeypatch.setattr("app.main.load_state", _noop_load_state)
    monkeypatch.setattr("app.api.routes.save_state", _noop_save_state)
    monkeypatch.setattr("app.main.get_sessionmaker", lambda: _FakeSessionmaker())
    monkeypatch.setattr("app.api.routes.get_sessionmaker", lambda: _FakeSessionmaker())

    # Re-import to grab the app with patches applied.
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health_reports_qwen_and_counts(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "qwen_available" in body
    assert body["events"] == 0
    assert body["facts"] == 0


def test_stats_exposes_cost_tile(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert "cost" in body
    for field in (
        "qwen_calls",
        "qwen_input_tokens_est",
        "qwen_by_model",
        "rules_fallbacks",
        "deterministic_decisions",
        "deterministic_ops",
        "fast_path_pct",
    ):
        assert field in body["cost"], f"missing cost.{field}"


def test_demo_seed_then_reset(client):
    r = client.post("/api/demo/seed", json={"sessions": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["events"] > 0
    assert body["facts_active"] > 0

    stats = client.get("/api/stats").json()
    assert stats["events_total"] == body["events"]

    r = client.post("/api/demo/reset")
    assert r.status_code == 200
    stats = client.get("/api/stats").json()
    assert stats["events_total"] == 0
    assert stats["cost"]["qwen_calls"] == 0
    assert stats["cost"]["deterministic_ops"] == 0


def test_ask_tracked_fact_path(client, monkeypatch):
    """Ask with a matched key returns tracked-fact path with a decision."""
    from app import extraction

    async def _map(question, keys, key_values):
        return "meeting_time_preference", "test-stub"

    async def _phrase(question, decision):
        return "morning", "test-stub"

    monkeypatch.setattr(extraction, "map_question_to_key", _map)
    monkeypatch.setattr("app.api.routes.map_question_to_key", _map)
    monkeypatch.setattr("app.api.routes.phrase_answer", _phrase)

    client.post("/api/demo/seed", json={"sessions": 10})
    r = client.post("/api/ask", json={"question": "when meetings?", "compare": False})
    assert r.status_code == 200
    body = r.json()
    assert body["path"] == "tracked-fact"
    assert body["key"] == "meeting_time_preference"
    assert body["decision"] is not None
    assert body["decision"]["gate"] in ("act", "show_sources", "ask")


def test_ask_hybrid_retrieval_path(client, monkeypatch):
    """Ask with no matched key returns hybrid-retrieval path with evidence."""

    async def _map_none(question, keys, key_values):
        return None, "test-stub"

    monkeypatch.setattr("app.api.routes.map_question_to_key", _map_none)

    client.post("/api/demo/seed", json={"sessions": 10})
    r = client.post("/api/ask", json={"question": "anything unrelated", "compare": False})
    assert r.status_code == 200
    body = r.json()
    assert body["key"] is None
    assert body["path"] in ("hybrid-retrieval", "abstain")
    if body["path"] == "hybrid-retrieval":
        assert body["decision"]["evidence"], "hybrid path must include evidence"


def test_ask_baseline_only_for_tracked_fact(client, monkeypatch):
    """The last-wins baseline comparison only makes sense with a tracked key."""

    async def _map_none(question, keys, key_values):
        return None, "test-stub"

    monkeypatch.setattr("app.api.routes.map_question_to_key", _map_none)

    client.post("/api/demo/seed", json={"sessions": 10})
    r = client.post("/api/ask", json={"question": "unrelated", "compare": True})
    assert r.status_code == 200
    body = r.json()
    assert "baseline" not in body
