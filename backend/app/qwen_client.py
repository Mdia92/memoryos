"""Qwen on Alibaba Cloud Model Studio — the slow path of MemoryOS.

This file is the project's Alibaba Cloud integration point: every LLM call
goes through DashScope's OpenAI-compatible endpoint
(https://dashscope-intl.aliyuncs.com/compatible-mode/v1) using Qwen models,
and every embedding uses DashScope's text-embedding models.

Qwen is invoked ONLY where genuine reasoning is required (assertion
extraction from unstructured text, natural-language answers, pattern
descriptions). All memory dynamics — merging, confidence, decay,
contradiction resolution — are deterministic and never call a model.
"""

from __future__ import annotations

import json
from functools import lru_cache

from openai import AsyncOpenAI

from .config import get_settings


@lru_cache
def get_client() -> AsyncOpenAI | None:
    settings = get_settings()
    if not settings.dashscope_api_key:
        return None
    return AsyncOpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


def qwen_available() -> bool:
    return get_client() is not None


async def chat_json(system: str, user: str, model: str, timeout: float = 30.0) -> dict:
    """One structured-output chat call. Raises on any failure — the fallback
    chain (app.fallback_chain) decides what happens next, not this client."""
    client = get_client()
    if client is None:
        raise RuntimeError("DASHSCOPE_API_KEY not configured")
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        timeout=timeout,
    )
    return json.loads(response.choices[0].message.content or "{}")


async def chat_text(system: str, user: str, model: str, timeout: float = 30.0) -> str:
    client = get_client()
    if client is None:
        raise RuntimeError("DASHSCOPE_API_KEY not configured")
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        timeout=timeout,
    )
    return response.choices[0].message.content or ""


async def embed_texts(texts: list[str], dimensions: int = 512) -> list[list[float]]:
    """DashScope embeddings (text-embedding-v3). Raises on failure."""
    client = get_client()
    if client is None:
        raise RuntimeError("DASHSCOPE_API_KEY not configured")
    settings = get_settings()
    response = await client.embeddings.create(
        model=settings.qwen_embedding_model,
        input=texts,
        dimensions=dimensions,
    )
    return [item.embedding for item in response.data]
