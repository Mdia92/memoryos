"""The eval harness: the same decision tasks, asked after every session.

For each session 1..N it ingests that session's events, then asks all 12
fixed decision tasks against (a) MemoryOS and (b) the last-assertion-wins
baseline, and scores both against ground truth AT THAT SESSION (flipped
truths count — a memory that can't update is wrong).

Everything is deterministic (seeded dataset, zero LLM calls), so the curve
is a structural result: accuracy rises because evidence accumulates.

Metrics per session:
  - accuracy:            fraction of tasks whose best answer matches truth
  - precision_when_acting: of the tasks where the gate allowed acting,
                           how many were right (the trust metric)
  - act_rate / ask_rate: how often the agent was confident enough to act
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.baseline import baseline_answer
from app.decision import decide
from app.engine import ingest_event
from app.memory.core import MemoryState

from .dataset import TRUTH_KEYS, dataset_summary, generate_dataset


def run_eval(sessions: int = 20, seed: int = 42, policy: dict | None = None) -> dict:
    if policy is None:
        from app.config import get_policy

        policy = get_policy()

    by_session = generate_dataset(sessions=sessions, seed=seed)
    state = MemoryState()
    per_session: list[dict] = []
    notifications_total = 0

    for s in range(1, sessions + 1):
        events = by_session[s]
        for event in events:
            notifications_total += len(ingest_event(state, event, policy))
        now = max((e.occurred_at for e in events), default=datetime.now(UTC))

        tasks = []
        mos_correct = baseline_correct = acts = correct_acts = asks = 0
        for tk in TRUTH_KEYS:
            truth = tk.truth_at(s)
            decision = decide(state, "user", tk.key, now, policy)
            base = baseline_answer(state.events, "user", tk.key)

            mos_ok = decision["value"] == truth
            base_ok = base["value"] == truth
            mos_correct += mos_ok
            baseline_correct += base_ok
            if decision["gate"] == "act":
                acts += 1
                correct_acts += mos_ok
            elif decision["gate"] == "ask":
                asks += 1
            tasks.append(
                {
                    "key": tk.key,
                    "truth": truth,
                    "memoryos": {
                        "value": decision["value"],
                        "gate": decision["gate"],
                        "confidence": decision["confidence"],
                        "correct": mos_ok,
                    },
                    "baseline": {"value": base["value"], "correct": base_ok},
                }
            )

        n = len(TRUTH_KEYS)
        active = state.active_facts()
        per_session.append(
            {
                "session": s,
                "memoryos_accuracy": round(mos_correct / n, 4),
                "baseline_accuracy": round(baseline_correct / n, 4),
                "precision_when_acting": round(correct_acts / acts, 4) if acts else None,
                "act_rate": round(acts / n, 4),
                "ask_rate": round(asks / n, 4),
                "facts_active": len(active),
                "facts_verified": sum(1 for f in active if f.verification == "verified"),
                "avg_confidence": round(
                    sum(f.confidence for f in active) / len(active), 4
                )
                if active
                else 0.0,
                "contradictions_open": sum(
                    1 for c in state.contradictions.values() if c.status == "open"
                ),
                "contradictions_resolved": sum(
                    1 for c in state.contradictions.values() if c.status.startswith("resolved")
                ),
                "patterns_promoted": sum(1 for p in state.patterns.values() if p.promoted),
                "tasks": tasks,
            }
        )

    first, last = per_session[0], per_session[-1]
    acting_precisions = [
        x["precision_when_acting"] for x in per_session if x["precision_when_acting"] is not None
    ]
    results = {
        "dataset": dataset_summary(by_session),
        "sessions": per_session,
        "summary": {
            "memoryos_first": first["memoryos_accuracy"],
            "memoryos_last": last["memoryos_accuracy"],
            "baseline_first": first["baseline_accuracy"],
            "baseline_last": last["baseline_accuracy"],
            "mean_precision_when_acting": round(
                sum(acting_precisions) / len(acting_precisions), 4
            )
            if acting_precisions
            else None,
            "final_act_rate": last["act_rate"],
            "notifications_emitted": notifications_total,
        },
    }
    return {"results": results, "final_state": state}
