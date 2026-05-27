"""Session-Auth und Team-Scoping."""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

SESSION_USER_KEY = "user"
SESSION_ROLE_KEY = "role"
SESSION_TEAMS_KEY = "teams"


class UserRecord(BaseModel):
    username: str
    password: str
    role: Literal["admin", "user"] = "user"
    teams: list[str] = Field(default_factory=list)


class UsersConfig(BaseModel):
    users: list[UserRecord]


@dataclass(frozen=True)
class SessionUser:
    username: str
    role: Literal["admin", "user"]
    teams: list[str]

    def can_access_team(self, team_id: str) -> bool:
        if self.role == "admin":
            return True
        return team_id in self.teams


def load_users_config(root: Path) -> UsersConfig:
    path = root / "config" / "users.json"
    if not path.is_file():
        return UsersConfig(users=[])
    data = json.loads(path.read_text(encoding="utf-8"))
    return UsersConfig.model_validate(data)


def verify_password(plain: str, stored: str) -> bool:
    if stored.startswith("$2"):
        return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
    return secrets.compare_digest(plain, stored)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def authenticate(root: Path, username: str, password: str) -> SessionUser | None:
    cfg = load_users_config(root)
    for record in cfg.users:
        if record.username == username and verify_password(password, record.password):
            return SessionUser(
                username=record.username,
                role=record.role,
                teams=list(record.teams),
            )
    return None


def session_secret() -> str:
    secret = os.environ.get("BOT_SESSION_SECRET")
    if not secret:
        secret = "dev-insecure-change-me"
    return secret


def get_current_user(request: Request) -> SessionUser:
    username = request.session.get(SESSION_USER_KEY)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht angemeldet",
        )
    role = request.session.get(SESSION_ROLE_KEY, "user")
    teams = request.session.get(SESSION_TEAMS_KEY, [])
    return SessionUser(username=username, role=role, teams=teams)  # type: ignore[arg-type]


def get_optional_user(request: Request) -> SessionUser | None:
    if not request.session.get(SESSION_USER_KEY):
        return None
    return get_current_user(request)


CurrentUser = Annotated[SessionUser, Depends(get_current_user)]


def require_team_access(team_id: str, user: SessionUser) -> None:
    if not user.can_access_team(team_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Kein Zugriff auf Team '{team_id}'",
        )


def require_admin(user: SessionUser) -> None:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin-Rechte erforderlich",
        )
