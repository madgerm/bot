"""Web: /teams/<id>/settings."""

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


def test_team_settings_pages(client: TestClient) -> None:
    _login(client)
    assert client.get("/teams/alpha/settings").status_code == 200
    assert client.get("/teams/alpha/settings/agents").status_code == 200
    assert client.get("/teams/alpha/settings/agents/worker-exec").status_code == 200


def test_agents_redirects_to_settings(client: TestClient) -> None:
    _login(client)
    r = client.get("/teams/alpha/agents", follow_redirects=False)
    assert r.status_code == 302
    assert "/settings/agents" in r.headers.get("location", "")


def test_save_general(client: TestClient, web_project: Path) -> None:
    _login(client)
    r = client.post(
        "/teams/alpha/settings/general",
        data={
            "name": "Alpha geändert",
            "preset": "coding",
            "orchestrator_id": "orchestrator",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    cfg = json.loads((web_project / "teams" / "alpha" / "team.json").read_text())
    assert cfg["team"]["name"] == "Alpha geändert"
    assert cfg["team"]["preset"] == "coding"
