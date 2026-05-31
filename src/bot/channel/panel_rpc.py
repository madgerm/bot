"""RPC-Ausführung auf dem Panel (Qdrant, Medien, …)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def execute_panel_rpc(panel_root: Path, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "qdrant.search":
        from bot.qdrant.service import QdrantService, QdrantServiceError

        team_id = str(payload["team_id"])
        collection = str(payload.get("collection", "project"))
        query = str(payload.get("query", ""))
        limit = int(payload.get("limit", 5))
        service = QdrantService.from_root(panel_root)
        hits = service.search(team_id, collection, query, limit=limit)
        return {"hits": hits}

    if kind == "qdrant.index_workspace":
        from bot.qdrant.indexer import index_team_workspace

        team_id = str(payload["team_id"])
        count = index_team_workspace(panel_root, team_id)
        return {"count": count}

    if kind == "media.generate_image":
        from bot.media import MediaService, MediaServiceError

        team_id = str(payload["team_id"])
        prompt = str(payload.get("prompt", ""))
        try:
            result = MediaService.for_team(panel_root, team_id).generate_image(prompt)
        except MediaServiceError as exc:
            raise RuntimeError(str(exc)) from exc
        return {"result": result}

    if kind == "media.describe_image":
        from bot.media import MediaService, MediaServiceError

        team_id = str(payload["team_id"])
        path = Path(str(payload.get("path", "")))
        prompt = str(payload.get("prompt", "Beschreibe das Bild."))
        try:
            text = MediaService.for_team(panel_root, team_id).describe_image(path, prompt)
        except MediaServiceError as exc:
            raise RuntimeError(str(exc)) from exc
        return {"text": text}

    raise ValueError(f"Unbekannte Panel-RPC: {kind}")
