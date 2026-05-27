"""Master-Öffnungszeiten (JSON)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class HoursConfigError(Exception):
    pass


class DayHours(BaseModel):
    open: str | None = None
    close: str | None = None
    closed: bool = False


class HoursMaster(BaseModel):
    timezone: str = "Europe/Berlin"
    weekly: dict[str, DayHours] = Field(default_factory=dict)
    exceptions: list[dict[str, Any]] = Field(default_factory=list)
    note: str | None = None

    def normalized(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def master_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    return (root / relative).resolve()


def load_master(root: Path, relative_path: str) -> HoursMaster:
    path = master_path(root, relative_path)
    if not path.is_file():
        raise HoursConfigError(f"Master-Datei fehlt: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return HoursMaster.model_validate(data.get("hours", data))


def save_master(root: Path, relative_path: str, master: HoursMaster) -> Path:
    path = master_path(root, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"hours": master.model_dump(mode="json")}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
