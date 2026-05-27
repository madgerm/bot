"""Aufgelöste Playwright-Konfiguration (global oder Team-Override)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from bot.config import load_runtime_config
from bot.config.models import PlaywrightGlobalConfig


class TeamPlaywrightOverride(BaseModel):
    source: str = "global"
    mode: str | None = None
    ws_endpoints: list[str] = Field(default_factory=list)
    headless: bool | None = None


def load_team_playwright(root: Path, team_id: str) -> TeamPlaywrightOverride | None:
    path = root / "teams" / team_id / "playwright.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return TeamPlaywrightOverride.model_validate(data.get("playwright", data))
    except (json.JSONDecodeError, ValidationError):
        return None


def resolve_playwright_config(root: Path, team_id: str) -> PlaywrightGlobalConfig:
    config = load_runtime_config(root)
    global_cfg = config.system.playwright_global or PlaywrightGlobalConfig()
    override = load_team_playwright(root, team_id)
    if override is None or override.source == "global":
        return global_cfg
    return PlaywrightGlobalConfig(
        mode=override.mode or global_cfg.mode,  # type: ignore[arg-type]
        ws_endpoints=override.ws_endpoints or global_cfg.ws_endpoints,
        base_host=global_cfg.base_host,
        secret_ref=global_cfg.secret_ref,
        headless=override.headless if override.headless is not None else global_cfg.headless,
        timeout_seconds=global_cfg.timeout_seconds,
    )
