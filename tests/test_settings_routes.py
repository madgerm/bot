"""Admin-Einstellungen (/admin/settings)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bot.config.models import MediaGlobalConfig
from bot.config.media_admin import load_media_global, save_media_global
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
    r = client.post(
        "/login",
        data={"username": username, "password": "secret"},
        follow_redirects=False,
    )
    assert r.status_code == 302


def test_settings_requires_admin(client: TestClient) -> None:
    _login(client, "viewer")
    assert client.get("/admin/settings").status_code == 403

    client.post("/logout")
    _login(client, "admin")
    r = client.get("/admin/settings")
    assert r.status_code == 200
    assert "Einstellungen" in r.text
    assert "Nutzer" in r.text
    assert "/admin/settings/users" in r.text
    assert "/admin/media" in r.text


def test_admin_page_links_settings(client: TestClient) -> None:
    _login(client, "admin")
    r = client.get("/admin")
    assert r.status_code == 200
    assert "/admin/settings" in r.text


def test_media_save_uses_atomic_writer(web_project: Path) -> None:
    media = load_media_global(web_project)
    save_media_global(web_project, media.model_copy(update={}))
    path = web_project / "config" / "system.json"
    assert path.is_file()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "media_global" in raw
