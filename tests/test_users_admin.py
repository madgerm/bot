"""Nutzer-Admin (config/users.json)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.config.writers.users_admin import (
    UsersAdminError,
    create_user,
    delete_user,
    load_users_config,
    update_user,
)
from bot.web.auth import authenticate


@pytest.fixture
def users_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "teams" / "alpha").mkdir(parents=True)
    (tmp_path / "teams" / "beta").mkdir(parents=True)
    (tmp_path / "config" / "users.json").write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "admin",
                        "password": "secret",
                        "role": "admin",
                        "teams": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_create_and_login(users_root: Path) -> None:
    create_user(
        users_root,
        username="worker1",
        password_plain="hunter2",
        role="user",
        team_levels={"alpha": "operator", "beta": "reader"},
        enabled=True,
        actor="admin",
    )
    cfg = load_users_config(users_root)
    worker = next(u for u in cfg.users if u.username == "worker1")
    assert worker.teams == ["alpha"]
    assert len(worker.team_access) == 1
    assert worker.team_access[0].team_id == "beta"
    assert worker.password.startswith("$2")

    session = authenticate(users_root, "worker1", "hunter2")
    assert session is not None
    assert session.can_access_team("alpha")
    assert session.access_for_team("beta") == "reader"


def test_cannot_delete_last_admin(users_root: Path) -> None:
    with pytest.raises(UsersAdminError, match="letzte Admin"):
        delete_user(users_root, username="admin", actor="other")


def test_cannot_delete_self(users_root: Path) -> None:
    create_user(
        users_root,
        username="bob",
        password_plain="x",
        role="user",
        team_levels={},
        actor="admin",
    )
    with pytest.raises(UsersAdminError, match="Eigenes Konto"):
        delete_user(users_root, username="bob", actor="bob")


def test_disabled_user_cannot_login(users_root: Path) -> None:
    create_user(
        users_root,
        username="gone",
        password_plain="pw",
        role="user",
        team_levels={},
        actor="admin",
    )
    update_user(
        users_root,
        username="gone",
        role="user",
        team_levels={},
        enabled=False,
        password_plain=None,
        actor="admin",
    )
    assert authenticate(users_root, "gone", "pw") is None
