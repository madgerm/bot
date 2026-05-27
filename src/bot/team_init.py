"""Team-Ressourcen initialisieren (Qdrant + Chat-DB)."""

from __future__ import annotations

from pathlib import Path


def init_team_resources(root: Path, team_id: str) -> dict[str, str]:
    results: dict[str, str] = {}

    from bot.chat import ChatStore

    ChatStore(root, team_id)
    results["chat"] = str((root / "data" / team_id / "chat.sqlite").resolve())

    try:
        from bot.qdrant import QdrantService

        service = QdrantService.from_root(root)
        names = service.ensure_team_collections(team_id)
        results["qdrant"] = ", ".join(names.values())
    except Exception as exc:
        results["qdrant"] = f"übersprungen ({exc})"

    return results
