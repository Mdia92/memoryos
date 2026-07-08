"""Qwen-based judge for LongMemEval responses.

LongMemEval's official evaluation uses GPT-4 as judge; we substitute Qwen-plus
(qwen-turbo → rules-only fallback). Scoring is binary correct/incorrect.
The rules fallback normalizes whitespace/case and checks substring inclusion —
enough for facts (e.g. "Business Administration") but conservative.
"""

from __future__ import annotations

import re
import unicodedata

from app.fallback_chain import run_json_task

JUDGE_SYSTEM = """You grade an answer against a gold reference for a memory-agent benchmark.

Return JSON: {"correct": true|false, "reason": "<one sentence>"}

Rules:
- correct=true when the answer conveys the same fact as gold (paraphrases OK).
- correct=false when the answer contradicts gold, is missing the fact, or refuses.
- Ignore surface differences (case, punctuation, wording). Focus on the informational match.
- For numeric or date answers, allow small formatting differences; require the same value."""


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _rules_grade(answer: str, gold: str) -> dict:
    a, g = _normalize(answer), _normalize(gold)
    if not g:
        return {"correct": False, "reason": "empty gold"}
    if g in a:
        return {"correct": True, "reason": "gold substring present"}
    g_tokens = set(g.split())
    a_tokens = set(a.split())
    overlap = len(g_tokens & a_tokens) / max(len(g_tokens), 1)
    return {
        "correct": overlap >= 0.7,
        "reason": f"token overlap {overlap:.0%}",
    }


async def grade(question: str, answer: str, gold: str) -> tuple[bool, str, str]:
    """Returns (correct, reason, provider)."""

    def fallback() -> dict:
        return _rules_grade(answer, gold)

    user = f"Question: {question}\nGold answer: {gold}\nCandidate answer: {answer}"
    result, provider = await run_json_task(JUDGE_SYSTEM, user, fallback)
    correct = bool(result.get("correct"))
    reason = str(result.get("reason", ""))[:200]
    return correct, reason, provider
