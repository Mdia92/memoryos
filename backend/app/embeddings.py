"""Embeddings with graceful degradation.

Primary: DashScope text-embedding-v3 (512 dims). Fallback: a deterministic
local hashing embedder — far weaker semantically, but it keeps similarity
search available offline and it is reproducible across runs, which the eval
harness requires.
"""

from __future__ import annotations

import hashlib
import math
import re

EMBEDDING_DIM = 512
_token_re = re.compile(r"[a-z0-9]+")


def local_hash_embeddings(texts: list[str], dim: int = EMBEDDING_DIM) -> list[list[float]]:
    """Hashing-trick bag-of-words embedding. Deterministic, dependency-free."""
    out: list[list[float]] = []
    for text in texts:
        vec = [0.0] * dim
        for token in _token_re.findall(text.lower()):
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[index] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


def cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=False))
    da = math.sqrt(sum(x * x for x in a)) or 1.0
    db = math.sqrt(sum(y * y for y in b)) or 1.0
    return num / (da * db)
