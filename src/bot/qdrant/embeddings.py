"""Text-Embeddings (Hash-Fallback oder LiteLLM)."""

from __future__ import annotations

import hashlib
import math
import os
import struct

from bot.config.models import EmbeddingConfig


def hash_embedding(text: str, *, vector_size: int) -> list[float]:
    """Deterministischer Vektor ohne externen Dienst (Tests/Offline)."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    while len(values) < vector_size:
        for i in range(0, len(digest), 4):
            chunk = digest[i : i + 4]
            if len(chunk) < 4:
                chunk = chunk.ljust(4, b"\0")
            num = struct.unpack("!I", chunk)[0]
            values.append((num / 2**32) * 2 - 1)
            if len(values) >= vector_size:
                break
        digest = hashlib.sha256(digest).digest()
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def embed_text(text: str, config: EmbeddingConfig) -> list[float]:
    if config.provider == "hash":
        return hash_embedding(text, vector_size=config.vector_size)
    if config.provider == "litellm":
        import litellm

        model = config.model or "text-embedding-3-small"
        response = litellm.embedding(model=model, input=[text])
        vector = response.data[0]["embedding"]
        return list(vector)
    raise ValueError(f"Unbekannter embedding.provider: {config.provider}")


def resolve_api_key(secret_ref: str | None) -> str | None:
    if not secret_ref:
        return None
    return os.environ.get(secret_ref)
