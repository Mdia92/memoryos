"""The confidence formula must be recomputable by hand from the evidence."""

from app.confidence import (
    compute_confidence,
    corroboration_score,
    effective_corroboration,
    gate_for,
)

from .conftest import NOW, make_fact


def test_single_source_has_zero_corroboration(policy):
    fact = make_fact(origins=["calendar"])
    assert corroboration_score(fact, policy) == 0.0


def test_independent_origins_beat_repeats_from_one_origin(policy):
    three_independent = make_fact(origins=["calendar", "email", "note"])
    three_same = make_fact(origins=["email", "email", "email"])
    assert corroboration_score(three_independent, policy) > corroboration_score(
        three_same, policy
    )
    # effective count: 3 independent = 3.0; 3 from one origin = 1 + 0.25*2 = 1.5
    assert effective_corroboration(three_independent, policy) == 3.0
    assert effective_corroboration(three_same, policy) == 1.5


def test_confidence_grows_with_evidence(policy):
    weak = make_fact(origins=["email"])
    strong = make_fact(origins=["email", "calendar", "note", "task"])
    assert compute_confidence(strong, NOW, policy) > compute_confidence(weak, NOW, policy)


def test_fresh_single_source_fact_cannot_act(policy):
    fact = make_fact(origins=["email"], age_days=0)
    confidence = compute_confidence(fact, NOW, policy)
    assert gate_for(confidence, policy) != "act"


def test_corroborated_verified_confirmed_fact_may_act(policy):
    fact = make_fact(
        origins=["email", "calendar", "note", "task"],
        verification="verified",
        user_confirmation="confirmed",
    )
    confidence = compute_confidence(fact, NOW, policy)
    assert gate_for(confidence, policy) == "act"


def test_failed_verification_costs_confidence(policy):
    ok = make_fact(origins=["email", "calendar"], verification="verified")
    failed = make_fact(origins=["email", "calendar"], verification="failed")
    gap = compute_confidence(ok, NOW, policy) - compute_confidence(failed, NOW, policy)
    # the full verification weight separates them
    assert abs(gap - policy["confidence"]["weights"]["verification"]) < 1e-6


def test_confidence_is_bounded(policy):
    maxed = make_fact(
        origins=["email", "calendar", "note", "task", "chat"] * 5,
        verification="verified",
        user_confirmation="confirmed",
    )
    assert compute_confidence(maxed, NOW, policy) <= 1.0
