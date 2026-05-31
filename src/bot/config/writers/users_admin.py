"""Lesen/Schreiben von config/users.json (Panel)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from bot.config.writers import ConfigWriterError, atomic_write_json, relative_config_path
from bot.config.writers.audit import log_config_change
from bot.web.auth import (
    TeamAccessRecord,
    UserRecord,
    UsersConfig,
    hash_password,
    load_users_config,
)

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,63}$")


class UsersAdminError(ConfigWriterError):
    pass


def users_config_path(root: Path) -> Path:
    return root / "config" / "users.json"


def list_known_team_ids(root: Path) -> list[str]:
    """Team-IDs aus teams/ und team_hosts.json."""
    ids: set[str] = set()
    teams_dir = root / "teams"
    if teams_dir.is_dir():
        for p in teams_dir.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                ids.add(p.name)
    try:
        from bot.hosts.registry import load_team_hosts_config

        hosts = load_team_hosts_config(root)
        for entry in hosts.hosts:
            ids.update(entry.teams)
    except Exception:
        pass
    return sorted(ids)


def save_users_config(root: Path, cfg: UsersConfig) -> None:
    path = users_config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, cfg.model_dump(mode="json"))


def validate_username(username: str) -> None:
    name = username.strip()
    if not name or not _USERNAME_RE.match(name):
        raise UsersAdminError(
            "Benutzername: 2–64 Zeichen, Buchstaben/Ziffern, optional . _ -"
        )


def count_admins(cfg: UsersConfig) -> int:
    return sum(1 for u in cfg.users if u.role == "admin")


def get_user(cfg: UsersConfig, username: str) -> UserRecord | None:
    for u in cfg.users:
        if u.username == username:
            return u
    return None


def team_access_levels_for_user(record: UserRecord, team_ids: list[str]) -> dict[str, str]:
    """team_id → none | reader | operator."""
    levels = {tid: "none" for tid in team_ids}
    for tid in record.teams:
        if tid in levels:
            levels[tid] = "operator"
    for entry in record.team_access:
        if entry.team_id in levels:
            levels[entry.team_id] = entry.access
    return levels


def levels_to_teams_and_access(
    levels: dict[str, str],
) -> tuple[list[str], list[TeamAccessRecord]]:
    teams: list[str] = []
    team_access: list[TeamAccessRecord] = []
    for team_id, level in levels.items():
        if level == "operator":
            teams.append(team_id)
        elif level == "reader":
            team_access.append(TeamAccessRecord(team_id=team_id, access="reader"))
    return sorted(set(teams)), team_access


def create_user(
    root: Path,
    *,
    username: str,
    password_plain: str,
    role: Literal["admin", "user"],
    team_levels: dict[str, str],
    enabled: bool = True,
    actor: str,
) -> UserRecord:
    validate_username(username)
    if not password_plain:
        raise UsersAdminError("Passwort ist erforderlich.")
    cfg = load_users_config(root)
    if get_user(cfg, username.strip()):
        raise UsersAdminError(f"Benutzer '{username}' existiert bereits.")
    teams, team_access = levels_to_teams_and_access(team_levels)
    record = UserRecord(
        username=username.strip(),
        password=hash_password(password_plain),
        role=role,
        teams=teams,
        team_access=team_access,
        enabled=enabled,
    )
    try:
        new_cfg = UsersConfig(users=[*cfg.users, record])
    except ValidationError as exc:
        raise UsersAdminError(str(exc)) from exc
    save_users_config(root, new_cfg)
    log_config_change(
        root,
        actor=actor,
        config_path=relative_config_path(root, users_config_path(root)),
        action="create",
        details={"username": record.username},
    )
    return record


def update_user(
    root: Path,
    *,
    username: str,
    role: Literal["admin", "user"],
    team_levels: dict[str, str],
    enabled: bool,
    password_plain: str | None,
    actor: str,
) -> UserRecord:
    cfg = load_users_config(root)
    existing = get_user(cfg, username)
    if existing is None:
        raise UsersAdminError(f"Benutzer '{username}' nicht gefunden.")
    if existing.role == "admin" and role != "admin" and count_admins(cfg) <= 1:
        raise UsersAdminError("Der letzte Admin kann nicht herabgestuft werden.")
    if not enabled and existing.role == "admin" and count_admins(cfg) <= 1:
        raise UsersAdminError("Der letzte Admin kann nicht deaktiviert werden.")
    teams, team_access = levels_to_teams_and_access(team_levels)
    password = existing.password
    if password_plain:
        password = hash_password(password_plain)
    updated = UserRecord(
        username=existing.username,
        password=password,
        role=role,
        teams=teams,
        team_access=team_access,
        enabled=enabled,
    )
    new_users = [updated if u.username == username else u for u in cfg.users]
    new_cfg = UsersConfig(users=new_users)
    save_users_config(root, new_cfg)
    log_config_change(
        root,
        actor=actor,
        config_path=relative_config_path(root, users_config_path(root)),
        action="update",
        details={"username": username, "password_changed": bool(password_plain)},
    )
    return updated


def delete_user(root: Path, *, username: str, actor: str) -> None:
    if username == actor:
        raise UsersAdminError("Eigenes Konto kann nicht gelöscht werden.")
    cfg = load_users_config(root)
    target = get_user(cfg, username)
    if target is None:
        raise UsersAdminError(f"Benutzer '{username}' nicht gefunden.")
    if target.role == "admin" and count_admins(cfg) <= 1:
        raise UsersAdminError("Der letzte Admin kann nicht gelöscht werden.")
    new_cfg = UsersConfig(users=[u for u in cfg.users if u.username != username])
    save_users_config(root, new_cfg)
    log_config_change(
        root,
        actor=actor,
        config_path=relative_config_path(root, users_config_path(root)),
        action="delete",
        details={"username": username},
    )
