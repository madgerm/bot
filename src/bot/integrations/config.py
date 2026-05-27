"""teams/<id>/integrations.json"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


class TelegramConfig(BaseModel):
    enabled: bool = False
    bot_token_ref: str = "TELEGRAM_BOT_TOKEN"
    webhook_path: str = "/integrations/telegram"
    default_team_id: str | None = None
    default_agent_id: str = "orchestrator"


class MatrixConfig(BaseModel):
    enabled: bool = False
    homeserver: str = "https://matrix.org"
    access_token_ref: str = "MATRIX_ACCESS_TOKEN"
    room_id: str | None = None
    default_team_id: str | None = None
    default_agent_id: str = "orchestrator"


class IntegrationsConfig(BaseModel):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)


def load_integrations_config(root: Path, team_id: str) -> IntegrationsConfig | None:
    path = root / "teams" / team_id / "integrations.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return IntegrationsConfig.model_validate(data.get("integrations", data))


def resolve_ref(ref: str) -> str | None:
    return os.environ.get(ref)
