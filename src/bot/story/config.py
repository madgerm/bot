"""teams/<id>/story_review.json — parallele Prüfer-Agenten."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


DEFAULT_CHECKERS = [
    {
        "id": "logik-pruefer",
        "name": "Logik-Prüfer",
        "task_category": "logic_check",
        "agent_id": "logik-pruefer",
        "prompt": (
            "Prüfe die Szene auf logische Konsistenz, Zeitablauf und Handlungsfolge. "
            "Antworte mit OK oder nummerierten PROBLEMEN."
        ),
    },
    {
        "id": "worldkeeper",
        "name": "Worldkeeper",
        "task_category": "world_consistency",
        "agent_id": "worldkeeper",
        "prompt": (
            "Prüfe die Szene gegen die World-Regeln und Orte. "
            "Antworte mit OK oder WORLD-ISSUES (kurz)."
        ),
    },
    {
        "id": "character-manager",
        "name": "Character-Manager",
        "task_category": "character_consistency",
        "agent_id": "character-manager",
        "prompt": (
            "Prüfe Charakterverhalten, Beziehungen und Speech-Patterns. "
            "Antworte mit OK oder CHARACTER-ISSUES."
        ),
    },
    {
        "id": "stil-pruefer",
        "name": "Stil-Prüfer",
        "task_category": "style_check",
        "agent_id": "stil-pruefer",
        "prompt": "Prüfe Stil und Erzählton. OK oder STYLE-ISSUES.",
    },
    {
        "id": "deutsch-pruefer",
        "name": "Deutsch-Prüfer",
        "task_category": "grammar_check",
        "agent_id": "deutsch-pruefer",
        "prompt": "Prüfe Grammatik und Rechtschreibung (DE). OK oder GRAMMAR-ISSUES.",
    },
    {
        "id": "zeit-pruefer",
        "name": "Zeit-Prüfer",
        "task_category": "tense_check",
        "agent_id": "zeit-pruefer",
        "prompt": "Prüfe Zeitformen und Tempus-Konsistenz. OK oder TENSE-ISSUES.",
    },
    {
        "id": "detail-pruefer",
        "name": "Detail-Prüfer",
        "task_category": "detail_check",
        "agent_id": "detail-pruefer",
        "prompt": "Prüfe Details, Wiederholungen und Plot-Löcher. OK oder DETAIL-ISSUES.",
    },
]


class StoryCheckerConfig(BaseModel):
    id: str
    name: str
    task_category: str
    agent_id: str
    prompt: str
    enabled: bool = True


class StoryReviewConfig(BaseModel):
    checkers: list[StoryCheckerConfig] = Field(default_factory=list)
    max_parallel: int = Field(default=7, ge=1, le=16)
    dispatch_to_agent_inbox: bool = True
    """Zusätzlich Messages in Agent-Inboxen (file-basiert) legen."""


def load_story_review_config(root: Path, team_id: str) -> StoryReviewConfig:
    path = root / "teams" / team_id / "story_review.json"
    if not path.is_file():
        return StoryReviewConfig(
            checkers=[StoryCheckerConfig.model_validate(c) for c in DEFAULT_CHECKERS]
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    block = data.get("story_review", data)
    return StoryReviewConfig.model_validate(block)
