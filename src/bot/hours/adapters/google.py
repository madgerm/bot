"""Google Business Profile — Snapshot (Datei-Fallback oder HTTP-Stub)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bot.hours.config import HoursTeamConfig


def fetch_google_snapshot(root: Path, team_id: str, cfg: HoursTeamConfig) -> dict[str, Any] | None:
    gb = cfg.google_business
    if not gb.enabled:
        return None

    # MVP: optional lokale Snapshot-Datei (vom Betreiber gepflegt oder später API)
    snapshot = root / "data" / team_id / "google_hours.snapshot.json"
    if snapshot.is_file():
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        return data.get("hours", data)

    # Kein Snapshot → leer; echter API-Client in späterer Phase
    return {"hours": {}, "_note": "google_api_not_configured"}
