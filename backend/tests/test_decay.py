"""Uncorroborated memories must fade faster than corroborated ones."""

from datetime import timedelta

from app.memory.core import MemoryState
from app.memory.decay import apply_decay, half_life_days, recency_score

from .conftest import NOW, make_fact


def test_half_life_grows_with_independent_origins(policy):
    assert half_life_days(1, policy) == 180
    assert half_life_days(2, policy) == 360
    assert half_life_days(3, policy) == 540
    assert half_life_days(5, policy) == 540


def test_fresh_fact_has_full_recency(policy):
    fact = make_fact(age_days=0)
    assert recency_score(fact, NOW, policy) > 0.99


def test_single_source_fades_faster_than_multi_source(policy):
    single = make_fact(origins=["email"], age_days=180)
    multi = make_fact(origins=["email", "calendar", "note"], age_days=180)
    assert recency_score(single, NOW, policy) < recency_score(multi, NOW, policy)
    # at exactly one half-life the single-source memory is at 50%
    assert abs(recency_score(single, NOW, policy) - 0.5) < 0.01


def test_apply_decay_flags_stale_memories(policy):
    state = MemoryState()
    ancient = make_fact(origins=["email"], age_days=500)
    fresh = make_fact(origins=["email"], age_days=1, key="other_key")
    state.facts[ancient.id] = ancient
    state.facts[fresh.id] = fresh

    notifications = apply_decay(state, NOW, policy)

    assert ancient.stale and not fresh.stale
    assert any(
        n["type"] == "stale_memory" and n["fact_id"] == ancient.id for n in notifications
    )
    # notification fires once, not on every pass
    assert apply_decay(state, NOW, policy) == []


def test_never_supported_fact_has_zero_recency(policy):
    fact = make_fact()
    fact.last_supported = None
    assert recency_score(fact, NOW, policy) == 0.0


def test_future_support_does_not_exceed_one(policy):
    fact = make_fact()
    fact.last_supported = NOW + timedelta(days=3)
    assert recency_score(fact, NOW, policy) <= 1.0
