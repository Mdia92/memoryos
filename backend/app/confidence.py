"""The confidence formula. Confidence is earned from evidence, never assumed.

    confidence = 0.40 * corroboration  (independent sources agreeing)
               + 0.30 * recency        (half-life depends on corroboration)
               + 0.20 * verification   (did later evidence confirm the fact?)
               + 0.10 * user_confirmation

Every term is observable in the evidence chain, so a judge (or a user) can
recompute any score by hand from the fact's sources. Weights and gates live
in config/confidence_policy.yaml.
"""

from __future__ import annotations

import math
from datetime import datetime

from .memory.core import MemoryFact
from .memory.decay import recency_score


def effective_corroboration(fact: MemoryFact, policy: dict) -> float:
    """Count evidence with diminishing returns for repeats from one origin.

    Three confirmations from three independent origins are worth far more
    than three confirmations from the same email thread.
    """
    same_origin_w = policy["corroboration"]["same_origin_weight"]
    total = len(fact.sources)
    distinct = fact.distinct_origins
    return distinct + same_origin_w * (total - distinct)


def corroboration_score(fact: MemoryFact, policy: dict) -> float:
    """Saturating score in [0, 1): 1 source ~ 0, each independent source adds less."""
    n_eff = effective_corroboration(fact, policy)
    if n_eff <= 1:
        return 0.0
    k = policy["corroboration"]["saturation_k"]
    return 1.0 - math.exp(-(n_eff - 1) / k)


def verification_score(fact: MemoryFact) -> float:
    return {"verified": 1.0, "unverified": 0.5, "failed": 0.0}[fact.verification]


def confirmation_score(fact: MemoryFact) -> float:
    return {"confirmed": 1.0, "none": 0.0, "corrected": 0.0}[fact.user_confirmation]


def compute_confidence(fact: MemoryFact, now: datetime, policy: dict) -> float:
    w = policy["confidence"]["weights"]
    score = (
        w["corroboration"] * corroboration_score(fact, policy)
        + w["recency"] * recency_score(fact, now, policy)
        + w["verification"] * verification_score(fact)
        + w["user_confirmation"] * confirmation_score(fact)
    )
    return round(min(max(score, 0.0), 1.0), 4)


def gate_for(confidence: float, policy: dict) -> str:
    """Map a confidence score to what the agent is allowed to do."""
    gates = policy["gates"]
    if confidence >= gates["act"]:
        return "act"
    if confidence >= gates["show_sources"]:
        return "show_sources"
    return "ask"


def explain_confidence(fact: MemoryFact, now: datetime, policy: dict) -> dict:
    """Break the score down term by term, so the UI can show its work."""
    w = policy["confidence"]["weights"]
    terms = {
        "corroboration": corroboration_score(fact, policy),
        "recency": recency_score(fact, now, policy),
        "verification": verification_score(fact),
        "user_confirmation": confirmation_score(fact),
    }
    return {
        "confidence": compute_confidence(fact, now, policy),
        "terms": {
            name: {"score": round(val, 4), "weight": w[name], "weighted": round(w[name] * val, 4)}
            for name, val in terms.items()
        },
        "sources": len(fact.sources),
        "independent_origins": fact.distinct_origins,
    }
