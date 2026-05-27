"""Team-Öffnungszeiten (`teams/<id>/hours.json`)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class HoursConfigError(Exception):
    pass


class WebsiteFileConfig(BaseModel):
    type: Literal["file"] = "file"
    path: str


class WebsiteHttpConfig(BaseModel):
    type: Literal["http"] = "http"
    url: str
    secret_ref: str | None = None


class GoogleBusinessConfig(BaseModel):
    enabled: bool = False
    account_id: str | None = None
    location_id: str | None = None
    secret_ref: str | None = None


class HoursSchedule(BaseModel):
    check_cron: str = "0 6 * * *"
    timezone: str = "Europe/Berlin"


class HoursTeamConfig(BaseModel):
    enabled: bool = True
    master_file: str = "teams/{team_id}/hours.master.json"
    website: WebsiteFileConfig | WebsiteHttpConfig
    google_business: GoogleBusinessConfig = Field(default_factory=GoogleBusinessConfig)
    schedule: HoursSchedule = Field(default_factory=HoursSchedule)
    require_approval: bool = True


class HoursConfig(BaseModel):
    hours: HoursTeamConfig


def load_hours_config(root: Path, team_id: str) -> HoursTeamConfig:
    path = root / "teams" / team_id / "hours.json"
    if not path.is_file():
        raise HoursConfigError(f"Keine Hours-Config: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    parsed = HoursConfig.model_validate(data)
    if not parsed.hours.enabled:
        raise HoursConfigError(f"Öffnungszeiten für Team '{team_id}' deaktiviert")
    cfg = parsed.hours
    cfg.master_file = cfg.master_file.replace("{team_id}", team_id)
    return cfg


def resolve_secret(secret_ref: str | None) -> str | None:
    if not secret_ref:
        return None
    value = os.environ.get(secret_ref, "").strip()
    if not value:
        raise HoursConfigError(f"Secret '{secret_ref}' nicht gesetzt")
    return value
