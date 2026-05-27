"""Story-Service."""

from __future__ import annotations

from pathlib import Path

from bot.story.store import StoryStore


class StoryService:
    def __init__(self, root: Path, team_id: str) -> None:
        self.store = StoryStore(Path(root), team_id)

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> StoryService:
        return cls(Path(root), team_id)
