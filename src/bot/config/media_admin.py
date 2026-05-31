"""Lesen/Schreiben von media_global (system.json) und teams/<id>/media.json."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from bot.config.models import ImageGenerationConfig, MediaChannelConfig, MediaGlobalConfig
from bot.config.writers import atomic_write_json
from bot.media.config import TeamMediaConfig


class MediaAdminError(Exception):
    pass


def _system_path(root: Path) -> Path:
    return root / "config" / "system.json"


def load_system_raw(root: Path) -> dict:
    path = _system_path(root)
    if not path.is_file():
        raise MediaAdminError(f"{path} fehlt")
    return json.loads(path.read_text(encoding="utf-8"))


def load_media_global(root: Path) -> MediaGlobalConfig:
    data = load_system_raw(root)
    block = data.get("media_global") or {}
    try:
        return MediaGlobalConfig.model_validate(block)
    except ValidationError as exc:
        raise MediaAdminError(f"media_global ungültig: {exc}") from exc


def save_media_global(root: Path, media: MediaGlobalConfig) -> None:
    data = load_system_raw(root)
    data["media_global"] = media.model_dump(mode="json", exclude_none=True)
    atomic_write_json(_system_path(root), data)


def load_team_media_file(root: Path, team_id: str) -> TeamMediaConfig | None:
    path = root / "teams" / team_id / "media.json"
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    block = raw.get("media", raw)
    return TeamMediaConfig.model_validate(block)


def save_team_media_file(root: Path, team_id: str, media: TeamMediaConfig) -> Path:
    path = root / "teams" / team_id / "media.json"
    atomic_write_json(
        path,
        {"media": media.model_dump(mode="json", exclude_none=True)},
    )
    return path


def media_global_from_form(
    *,
    stt_endpoint: str,
    tts_endpoint: str,
    tts_voice_id: str,
    image_type: str,
    image_url: str,
    vision_model: str,
) -> MediaGlobalConfig:
    return MediaGlobalConfig(
        vision=MediaChannelConfig(
            source="global",
            provider="litellm",
            model=vision_model or "gpt-4o-mini",
            secret_ref="LITELLM_API_KEY",
        ),
        stt=MediaChannelConfig(
            source="global",
            endpoint=stt_endpoint or None,
            secret_ref=None,
        ),
        tts=MediaChannelConfig(
            source="global",
            endpoint=tts_endpoint or None,
            voice_id=tts_voice_id or "de_DE_neural",
        ),
        image_generation=ImageGenerationConfig(
            source="global",
            type=image_type if image_type in ("webhook", "selfhosted", "minimax") else "webhook",
            url=image_url or None,
        ),
    )
