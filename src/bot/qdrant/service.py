"""Qdrant-Client: Collections anlegen, Upsert, Suche."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from bot.config import load_runtime_config
from bot.config.models import QdrantGlobalConfig
from bot.qdrant.collections import all_collections, load_registry, save_registry
from bot.qdrant.embeddings import embed_text, resolve_api_key


class QdrantServiceError(Exception):
    pass


class QdrantService:
    def __init__(self, root: Path, cfg: QdrantGlobalConfig) -> None:
        self.root = root.resolve()
        self.cfg = cfg
        self._client = None

    @classmethod
    def from_root(cls, root: Path) -> QdrantService:
        config = load_runtime_config(root)
        if not config.system.qdrant_global:
            raise QdrantServiceError("qdrant_global fehlt in config/system.json")
        if not config.system.qdrant_global.enabled:
            raise QdrantServiceError("Qdrant ist deaktiviert (qdrant_global.enabled=false)")
        return cls(root, config.system.qdrant_global)

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise QdrantServiceError("qdrant-client nicht installiert") from exc

        api_key = resolve_api_key(self.cfg.secret_ref)
        if self.cfg.url in (":memory:", "memory"):
            kwargs: dict[str, Any] = {"location": ":memory:", "timeout": self.cfg.timeout_seconds}
        else:
            kwargs = {"url": self.cfg.url, "timeout": self.cfg.timeout_seconds}
            if api_key:
                kwargs["api_key"] = api_key
        self._client = QdrantClient(**kwargs)
        return self._client

    def ensure_team_collections(self, team_id: str) -> dict[str, str]:
        from qdrant_client.models import Distance, VectorParams

        client = self._get_client()
        from bot.story.db import StoryDB

        include_story = (self.root / "data" / team_id / "story" / "meta.json").is_file()
        names = all_collections(team_id, include_story=include_story)
        dim = self.cfg.embedding.vector_size
        for suffix, name in names.items():
            if not client.collection_exists(name):
                client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                )
        return save_registry(self.root, team_id)

    def upsert(
        self,
        team_id: str,
        collection_suffix: str,
        *,
        text: str,
        payload: dict[str, Any] | None = None,
        point_id: str | None = None,
    ) -> str:
        from qdrant_client.models import PointStruct

        client = self._get_client()
        names = load_registry(self.root, team_id)
        collection = names.get(collection_suffix)
        if not collection:
            raise QdrantServiceError(f"Unbekannte Collection '{collection_suffix}'")

        vector = embed_text(text, self.cfg.embedding)
        pid = point_id or str(uuid.uuid4())
        body = {"text": text, **(payload or {})}
        client.upsert(
            collection_name=collection,
            points=[PointStruct(id=pid, vector=vector, payload=body)],
        )
        return pid

    def search(
        self,
        team_id: str,
        collection_suffix: str,
        query: str,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        client = self._get_client()
        names = load_registry(self.root, team_id)
        collection = names.get(collection_suffix)
        if not collection:
            raise QdrantServiceError(f"Unbekannte Collection '{collection_suffix}'")

        vector = embed_text(query, self.cfg.embedding)
        response = client.query_points(
            collection_name=collection,
            query=vector,
            limit=limit,
        )
        results = []
        for hit in response.points:
            results.append(
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload or {},
                }
            )
        return results
