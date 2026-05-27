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

    from bot.mail.store import MailStore

    MailStore(root, team_id)
    results["email"] = str((root / "data" / team_id / "email.sqlite").resolve())

    from bot.hours.store import HoursStore

    HoursStore(root, team_id)
    results["hours"] = str((root / "data" / team_id / "hours.sqlite").resolve())

    from bot.tasks.store import TaskStore

    TaskStore(root, team_id)
    results["tasks"] = str((root / "data" / team_id / "tasks.sqlite").resolve())

    from bot.story.store import StoryStore

    StoryStore(root, team_id)
    results["story"] = str((root / "data" / team_id / "story.sqlite").resolve())

    from bot.files import FileService

    FileService.for_team(root, team_id)
    results["workspace"] = str((root / "data" / team_id / "workspace").resolve())

    return results
