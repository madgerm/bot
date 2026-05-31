"""Web: Team-Dienste Settings."""

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
    client.post("/login", data={"username": "admin", "password": "secret"}, follow_redirects=False)


def test_service_settings_pages(client: TestClient) -> None:
    _login(client)
    for path in (
        "/teams/alpha/settings/crawl",
        "/teams/alpha/settings/email",
        "/teams/alpha/settings/hours",
        "/teams/alpha/settings/integrations",
        "/teams/alpha/settings/git",
        "/teams/alpha/settings/playwright",
    ):
        assert client.get(path).status_code == 200


def test_save_git_via_panel(client: TestClient, web_project: Path) -> None:
    _login(client)
    r = client.post(
        "/teams/alpha/settings/git",
        data={
            "git_enabled": "on",
            "repo_path": "data/alpha/workspace",
            "remote_name": "origin",
            "default_branch": "feature/ui",
            "user_name": "bot",
            "user_email": "bot@local",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    data = json.loads((web_project / "teams" / "alpha" / "git.json").read_text())
    assert data["git"]["default_branch"] == "feature/ui"
