"""Decision-making over memory, gated by confidence.

The agent always computes its best answer, then the confidence gate decides
what it may DO with it: act autonomously, answer while showing sources, or
ask a clarifying question. The gate thresholds live in policy YAML — the
agent never acts on low-confidence memory, by configuration.
"""

from __future__ import annotations

from datetime import datetime

from .confidence import explain_confidence, gate_for
from .memory.core import MemoryState

# Fast-path counter: every gated decision is deterministic (zero tokens).
# Exposed on /api/stats so the dashboard can show fast-path vs LLM ratio.
_deterministic_decisions = [0]


def deterministic_decision_count() -> int:
    return _deterministic_decisions[0]


def reset_deterministic_decisions() -> None:
    _deterministic_decisions[0] = 0


def decide(state: MemoryState, subject: str, key: str, now: datetime, policy: dict) -> dict:
    _deterministic_decisions[0] += 1
    facts = state.active_facts(subject, key)
    if not facts:
        return {
            "key": key,
            "value": None,
            "confidence": 0.0,
            "gate": "ask",
            "reason": "no memory for this key yet",
            "evidence": [],
        }

    ranked = sorted(facts, key=lambda f: f.confidence, reverse=True)
    top = ranked[0]
    margin = top.confidence - ranked[1].confidence if len(ranked) > 1 else None
    gate = gate_for(top.confidence, policy)
    reason = f"confidence {top.confidence:.2f}"
    if margin is not None and margin < policy["gates"]["ambiguity_margin"]:
        gate = "ask"
        reason = (
            f"ambiguous: '{top.value}' ({top.confidence:.2f}) vs "
            f"'{ranked[1].value}' ({ranked[1].confidence:.2f}) — margin {margin:.2f} "
            f"below {policy['gates']['ambiguity_margin']}"
        )

    return {
        "key": key,
        "value": top.value,
        "statement": top.statement,
        "fact_id": top.id,
        "confidence": top.confidence,
        "gate": gate,
        "reason": reason,
        "margin": margin,
        "competing_values": [
            {"value": f.value, "confidence": f.confidence, "sources": len(f.sources)}
            for f in ranked[1:]
        ],
        "evidence": [
            {
                "event_id": s.event_id,
                "origin": s.origin,
                "occurred_at": s.occurred_at.isoformat(),
                "excerpt": s.excerpt,
            }
            for s in top.sources
        ],
        "confidence_breakdown": explain_confidence(top, now, policy),
    }
