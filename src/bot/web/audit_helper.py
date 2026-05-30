"""Hilfsfunktionen für zentrales Audit-Logging aus Web-Routen."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bot.audit import AuditStore


def log_panel_action(
    root: Path,
    *,
    category: str,
    action: str,
    actor: str,
    team_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    AuditStore(root).log(
        category=category,
        action=action,
        actor=actor,
        team_id=team_id,
        details=details or {},
    )
