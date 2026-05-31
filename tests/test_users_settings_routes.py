"""Web-Routen /admin/settings/users."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bot.web import create_app


@pytest.fixture
def web_project(runtime_project: Path) -> Path:
    (runtime_project / "config" / "users.json").write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "admin",
                        "password": "secret",
                        "role": "admin",
                        "teams": ["alpha"],
                    },
                    {
                        "username": "viewer",
                        "password": "secret",
                        "role": "user",
                        "teams": ["alpha"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return runtime_project


@pytest.fixture
def client(web_project: Path) -> TestClient:
    return TestClient(create_app(web_project))


def _login(client: TestClient, username: str = "admin") -> None:
    client.get("/login")
    assert (
        client.post(
            "/login",
            data={"username": username, "password": "secret"},
            follow_redirects=False,
        ).status_code
        == 302
    )


def test_users_settings_requires_admin(client: TestClient) -> None:
    _login(client, "viewer")
    assert client.get("/admin/settings/users").status_code == 403


def test_create_user_via_panel(client: TestClient, web_project: Path) -> None:
    _login(client, "admin")
    r = client.get("/admin/settings/users")
    assert r.status_code == 200
    assert "Neuer Nutzer" in r.text

    r = client.post(
        "/admin/settings/users/create",
        data={
            "username": "newbie",
            "password": "newpass123",
            "password_confirm": "newpass123",
            "role": "user",
            "enabled": "on",
            "access_alpha": "operator",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "saved=created" in r.headers.get("location", "")

    cfg = json.loads((web_project / "config" / "users.json").read_text(encoding="utf-8"))
    names = [u["username"] for u in cfg["users"]]
    assert "newbie" in names

    client.post("/logout")
    assert (
        client.post(
            "/login",
            data={"username": "newbie", "password": "newpass123"},
            follow_redirects=False,
        ).status_code
        == 302
    )


def test_settings_index_links_users(client: TestClient) -> None:
    _login(client, "admin")
    r = client.get("/admin/settings")
    assert "/admin/settings/users" in r.text
    assert "Phase 1" not in r.text or "in Arbeit" not in r.text
