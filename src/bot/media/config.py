"""teams/<id>/media.json + media_global aus system.json."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel

from bot.config.models import ImageGenerationConfig, MediaChannelConfig, MediaGlobalConfig


class MediaConfigError(Exception):
    pass


class TeamMediaConfig(BaseModel):
    vision: MediaChannelConfig | None = None
    stt: MediaChannelConfig | None = None
    tts: MediaChannelConfig | None = None
    image_generation: ImageGenerationConfig | None = None


def resolve_secret(secret_ref: str | None) -> str | None:
    if not secret_ref:
        return None
    return os.environ.get(secret_ref)


def load_team_media(root: Path, team_id: str) -> TeamMediaConfig | None:
    path = root / "teams" / team_id / "media.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    block = data.get("media", data)
    return TeamMediaConfig.model_validate(block)


def resolve_channel(
    global_cfg: MediaGlobalConfig | None,
    team_cfg: TeamMediaConfig | None,
    channel: str,
) -> MediaChannelConfig | ImageGenerationConfig:
    global_media = global_cfg or MediaGlobalConfig()
    team = team_cfg or TeamMediaConfig()
    if channel == "image_generation":
        team_ch = team.image_generation
        global_ch = global_media.image_generation
    else:
        team_ch = getattr(team, channel, None)
        global_ch = getattr(global_media, channel)
    if team_ch and team_ch.source == "custom":
        return team_ch
    return global_ch
