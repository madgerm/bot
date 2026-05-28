"""Story-Service — delegiert an StoryDB."""

from __future__ import annotations

from pathlib import Path

from bot.story.db import StoryDB, StoryDBError


class StoryService:
    def __init__(self, root: Path | str, team_id: str) -> None:
        self.db = StoryDB(root, team_id)

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> StoryService:
        return cls(root, team_id)
