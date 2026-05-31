"""Web: /admin/settings/system und /models."""

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
                        "teams": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return runtime_project


@pytest.fixture
def client(web_project: Path) -> TestClient:
    return TestClient(create_app(web_project))


def _login(client: TestClient) -> None:
    client.get("/login")
    client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )


def test_system_settings_admin_only(client: TestClient, web_project: Path) -> None:
    (web_project / "config" / "users.json").write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "u",
                        "password": "secret",
                        "role": "user",
                        "teams": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    client.get("/login")
    client.post("/login", data={"username": "u", "password": "secret"})
    assert client.get("/admin/settings/system").status_code == 403


def test_system_and_models_pages(client: TestClient) -> None:
    _login(client)
    r = client.get("/admin/settings/system")
    assert r.status_code == 200
    assert "LLM" in r.text
    assert "Qdrant" in r.text
    r2 = client.get("/admin/settings/models")
    assert r2.status_code == 200
    assert "planning" in r2.text or "task_models" in r2.text.lower()


def test_save_polling(client: TestClient, web_project: Path) -> None:
    _login(client)
    r = client.post(
        "/admin/settings/system/polling",
        data={
            "interval_seconds": "7",
            "inbox_watch_seconds": "0.5",
            "worker_mode": "process",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    cfg = json.loads((web_project / "config" / "system.json").read_text(encoding="utf-8"))
    assert cfg["system"]["polling"]["interval_seconds"] == 7
