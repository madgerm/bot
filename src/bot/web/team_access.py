"""Feinere Team-Rechte: reader vs. operator."""

from __future__ import annotations

from fastapi import HTTPException, status

from bot.web.auth import SessionUser, require_team_access


def team_access_level(user: SessionUser, team_id: str) -> str:
    if user.role == "admin":
        return "admin"
    return user.access_for_team(team_id)


def require_team_write(team_id: str, user: SessionUser) -> None:
    """Lesen erlaubt für reader+operator; Schreiben nur operator/admin."""
    require_team_access(team_id, user)
    level = team_access_level(user, team_id)
    if level in ("admin", "operator"):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Nur Leserechte (reader) — keine Änderungen erlaubt",
    )
