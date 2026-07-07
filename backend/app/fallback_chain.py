"""Graceful degradation: qwen-plus → qwen-turbo → deterministic rules.

The system never hard-fails because a model call failed. Every slow-path
task declares a rules-only fallback, so with zero working API keys MemoryOS
still records events episodically, keeps every confidence score correct,
and defers only the interpretation work.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from .config import get_settings
from .qwen_client import chat_json, chat_text, qwen_available

logger = logging.getLogger("memoryos.fallback")


async def run_json_task(
    system: str,
    user: str,
    rules_fallback: Callable[[], dict],
) -> tuple[dict, str]:
    """Try Qwen primary, then Qwen fallback model, then deterministic rules.

    Returns (result, provider) where provider is the model id or "rules-only".
    """
    settings = get_settings()
    if qwen_available():
        for model in (settings.qwen_primary_model, settings.qwen_fallback_model):
            try:
                return await chat_json(system, user, model), model
            except Exception as exc:  # noqa: BLE001 — any model failure falls through
                logger.warning("model %s failed (%s); falling back", model, exc)
    return rules_fallback(), "rules-only"


async def run_text_task(
    system: str,
    user: str,
    rules_fallback: Callable[[], str],
) -> tuple[str, str]:
    settings = get_settings()
    if qwen_available():
        for model in (settings.qwen_primary_model, settings.qwen_fallback_model):
            try:
                return await chat_text(system, user, model), model
            except Exception as exc:  # noqa: BLE001
                logger.warning("model %s failed (%s); falling back", model, exc)
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
