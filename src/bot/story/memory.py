"""Qdrant Story-Memory: Szenen, Charaktere, World, Plot indexieren & suchen."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bot.story.db import StoryDB


class StoryMemoryError(Exception):
    pass


class StoryMemoryService:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.db = StoryDB(root, team_id)

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> StoryMemoryService:
        return cls(Path(root), team_id)

    def ensure_collections(self) -> dict[str, str]:
        from bot.qdrant import QdrantService, QdrantServiceError

        try:
            return QdrantService.from_root(self.root).ensure_team_collections(self.team_id)
        except QdrantServiceError as exc:
            raise StoryMemoryError(str(exc)) from exc

    def reindex_all(self) -> dict[str, int]:
        from bot.qdrant import QdrantService, QdrantServiceError

        try:
            qdrant = QdrantService.from_root(self.root)
        except QdrantServiceError as exc:
            raise StoryMemoryError(str(exc)) from exc

        self.ensure_collections()
        counts = {"story": 0, "world_consistency": 0}
        docs = self.db.gather_memory_documents()

        for doc in docs:
            suffix = "world_consistency" if doc["kind"] == "world" else "story"
            payload = {
                "kind": doc["kind"],
                "doc_id": doc["id"],
                "team_id": self.team_id,
            }
            if doc.get("chapter_id"):
                payload["chapter_id"] = doc["chapter_id"]
                payload["scene_id"] = doc.get("scene_id")
            import hashlib

            pid = hashlib.sha256(f"{self.team_id}:{doc['kind']}:{doc['id']}".encode()).hexdigest()[
                :32
            ]
            qdrant.upsert(
                self.team_id,
                suffix,
                text=doc["text"],
                payload=payload,
                point_id=pid,
            )
            counts[suffix] += 1
        return counts

    def search(
        self, query: str, *, collection: str = "story", limit: int = 8
    ) -> list[dict[str, Any]]:
        from bot.qdrant import QdrantService, QdrantServiceError

        try:
            return QdrantService.from_root(self.root).search(
                self.team_id, collection, query, limit=limit
            )
        except QdrantServiceError as exc:
            raise StoryMemoryError(str(exc)) from exc

    def search_for_scene_context(
        self, chapter_id: str, scene_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        meta, body = self.db.get_scene(chapter_id, scene_id)
        query = f"{meta.get('title', '')} {body[:500]}"
        return self.search(query, collection="story", limit=limit)
