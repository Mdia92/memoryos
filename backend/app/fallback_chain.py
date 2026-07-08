"""Graceful degradation: qwen-plus → qwen-turbo → deterministic rules.

The system never hard-fails because a model call failed. Every slow-path
task declares a rules-only fallback, so with zero working API keys MemoryOS
still records events episodically, keeps every confidence score correct,
and defers only the interpretation work.

Every slow-path call is counted here so the dashboard can surface how
often Qwen was actually invoked vs. how often the deterministic fast path
handled the job. The 80/20 hybrid claim is a measurement, not a slogan.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from .config import get_settings
from .qwen_client import chat_json, chat_text, qwen_available

logger = logging.getLogger("memoryos.fallback")


class SlowPathCounter:
    """Process-wide counters. Read via `snapshot()`, zero via `reset()`."""

    def __init__(self) -> None:
        self.qwen_calls = 0
        self.qwen_input_tokens_est = 0
        self.rules_fallbacks = 0
        self.by_model: dict[str, int] = {}

    def record_qwen(self, model: str, prompt_chars: int) -> None:
        self.qwen_calls += 1
        self.qwen_input_tokens_est += prompt_chars // 4  # ~4 chars/token
        self.by_model[model] = self.by_model.get(model, 0) + 1

    def record_fallback(self) -> None:
        self.rules_fallbacks += 1

    def snapshot(self) -> dict:
        total = self.qwen_calls + self.rules_fallbacks
        return {
            "qwen_calls": self.qwen_calls,
            "rules_fallbacks": self.rules_fallbacks,
            "qwen_input_tokens_est": self.qwen_input_tokens_est,
            "fast_path_ratio": round(self.rules_fallbacks / total, 4) if total else 0.0,
            "by_model": dict(self.by_model),
        }

    def reset(self) -> None:
        self.__init__()


counter = SlowPathCounter()


async def run_json_task(
    system: str,
    user: str,
    rules_fallback: Callable[[], dict],
) -> tuple[dict, str]:
    """Try Qwen primary, then Qwen fallback model, then deterministic rules.

    Returns (result, provider) where provider is the model id or "rules-only".
    """
    settings = get_settings()
    prompt_chars = len(system) + len(user)
    if qwen_available():
        for model in (settings.qwen_primary_model, settings.qwen_fallback_model):
            try:
                result = await chat_json(system, user, model)
                counter.record_qwen(model, prompt_chars)
                return result, model
            except Exception as exc:  # noqa: BLE001 — any model failure falls through
                logger.warning("model %s failed (%s); falling back", model, exc)
    counter.record_fallback()
    return rules_fallback(), "rules-only"


async def run_text_task(
    system: str,
    user: str,
    rules_fallback: Callable[[], str],
) -> tuple[str, str]:
    settings = get_settings()
    prompt_chars = len(system) + len(user)
    if qwen_available():
        for model in (settings.qwen_primary_model, settings.qwen_fallback_model):
            try:
                result = await chat_text(system, user, model)
                counter.record_qwen(model, prompt_chars)
                return result, model
            except Exception as exc:  # noqa: BLE001
                logger.warning("model %s failed (%s); falling back", model, exc)
    counter.record_fallback()
    return rules_fallback(), "rules-only"


async def run_embedding_task(
    texts: list[str],
    local_fallback: Callable[[list[str]], Awaitable[list[list[float]]]] | None = None,
) -> tuple[list[list[float]], str]:
    from .embeddings import local_hash_embeddings
    from .qwen_client import embed_texts

    if qwen_available():
        try:
            return await embed_texts(texts), get_settings().qwen_embedding_model
        except Exception as exc:  # noqa: BLE001
            logger.warning("embedding call failed (%s); using local hash embeddings", exc)
    return local_hash_embeddings(texts), "local-hash"
