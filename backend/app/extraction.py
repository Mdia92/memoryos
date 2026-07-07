"""Slow-path reasoning tasks delegated to Qwen, each with a rules fallback.

Three tasks need genuine language understanding:
  1. Extracting structured assertions from raw event text (ingest).
  2. Mapping a free-text question to a memory key (ask panel).
  3. Phrasing a natural-language answer over evidence (ask panel).

Everything else in MemoryOS is deterministic. Note the rules fallback for
extraction returns NO assertions rather than guessed ones — when we cannot
interpret reliably, we record the event episodically and interpret nothing.
Provenance is preserved; invention is not an option.
"""

from __future__ import annotations

import json

from .fallback_chain import run_json_task, run_text_task
from .memory.core import Assertion

EXTRACTION_SYSTEM = """You extract structured preference/behavior assertions from workplace events.
Return JSON: {"assertions": [{"subject": "user", "key": "<snake_case_key>",
"value": "<short value>", "statement": "<one sentence>"}]}
Rules:
- Only extract claims the text actually supports. Never invent.
- Keys are stable snake_case identifiers (e.g. meeting_time_preference, report_format).
- If the text contains no extractable claim, return {"assertions": []}.
- If a list of known keys is provided, reuse them whenever the claim matches one."""

ANSWER_SYSTEM = """You are MemoryOS, an evidence-based memory agent. Answer the user's question
using ONLY the decision JSON provided. State the answer, the confidence, and cite the evidence
(origins and dates). If the gate is "ask", ask the clarifying question instead of answering.
Never claim anything the evidence does not contain. Be concise (2-4 sentences)."""


async def extract_assertions(
    content: str, known_keys: list[str] | None = None
) -> tuple[list[Assertion], str]:
    """Extract assertions from raw text. Returns (assertions, provider)."""
    user = content
    if known_keys:
        user += "\n\nKnown keys: " + ", ".join(sorted(known_keys))

    def rules_fallback() -> dict:
        # Honest degradation: no interpretation without a model.
        return {"assertions": []}

    result, provider = await run_json_task(EXTRACTION_SYSTEM, user, rules_fallback)
    assertions = [
        Assertion(
            subject=a.get("subject", "user"),
            key=a["key"],
            value=str(a["value"]),
            statement=a.get("statement", ""),
        )
        for a in result.get("assertions", [])
        if a.get("key") and a.get("value")
    ]
    return assertions, provider


def _stem(token: str) -> str:
    return token[:-1] if token.endswith("s") and len(token) > 3 else token


async def map_question_to_key(
    question: str,
    known_keys: list[str],
    key_values: dict[str, list[str]] | None = None,
) -> tuple[str | None, str]:
    """Map a free-text question to one of the known memory keys.

    `key_values` (optional) maps each key to values seen in memory, so the
    rules fallback can match "remote or office?" → meeting_mode even when
    the key name itself never appears in the question.
    """

    def rules_fallback() -> dict:
        q_tokens = {_stem(t) for t in question.lower().replace("?", " ").split()}
        best, best_score = None, 0
        for key in known_keys:
            key_tokens = {_stem(t) for t in key.split("_")}
            value_tokens = {
                _stem(t)
                for v in (key_values or {}).get(key, [])
                for t in v.lower().split()
            }
            score = 2 * len(q_tokens & key_tokens) + len(q_tokens & value_tokens)
            if score > best_score:
                best, best_score = key, score
        return {"key": best}

    system = (
        "Map the user's question to exactly one key from the list, or null if none fits. "
        'Return JSON: {"key": "<key-or-null>"}'
    )
    user = f"Question: {question}\nKeys: {json.dumps(sorted(known_keys))}"
    result, provider = await run_json_task(system, user, rules_fallback)
    key = result.get("key")
    return (key if key in known_keys else None), provider


async def phrase_answer(question: str, decision: dict) -> tuple[str, str]:
    """Turn a gated decision into a natural answer that cites its evidence."""

    def rules_fallback() -> str:
        if decision.get("value") is None:
            return "I don't hold any evidence about that yet. Could you tell me?"
        evidence = decision.get("evidence", [])
        origins = ", ".join(sorted({e["origin"] for e in evidence})) or "no sources"
        if decision["gate"] == "ask":
            return (
                f"My evidence is not conclusive: {decision['reason']}. "
                "Which is correct?"
            )
        return (
            f"{decision.get('statement') or decision['value']} "
            f"(confidence {decision['confidence']:.0%}, based on {len(evidence)} "
            f"pieces of evidence from: {origins})."
        )

    user = f"Question: {question}\nDecision JSON: {json.dumps(decision, default=str)}"
    return await run_text_task(ANSWER_SYSTEM, user, rules_fallback)


async def describe_pattern(name: str, support_excerpts: list[str], default: str) -> tuple[str, str]:
    """Phrase a human description for an already-proven pattern."""

    def rules_fallback() -> str:
        return default

    system = (
        "Given a behavioral pattern name and the event excerpts that support it, write ONE clear "
        "sentence describing the pattern. Do not speculate beyond the excerpts."
    )
    user = f"Pattern: {name}\nSupporting events:\n" + "\n".join(f"- {x}" for x in support_excerpts)
    return await run_text_task(system, user, rules_fallback)
