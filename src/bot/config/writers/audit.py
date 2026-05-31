"""Audit-Hilfen für Konfigurationsänderungen aus dem Panel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bot.web.audit_helper import log_panel_action


def log_config_change(
    root: Path,
    *,
    actor: str,
    config_path: str,
    action: str = "update",
    team_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    payload = {"config_path": config_path, **(details or {})}
    log_panel_action(
        root,
        category="config",
        action=action,
        actor=actor,
        team_id=team_id,
        details=payload,
    )
