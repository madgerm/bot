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


def test_login_and_dashboard(client: TestClient) -> None:
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code in (401, 302, 307)

    r = client.post("/login", data={"username": "admin", "password": "secret"}, follow_redirects=False)
    assert r.status_code == 302

    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "test-runtime" in r.text or "Alpha" in r.text


def test_team_page_scoped(client: TestClient) -> None:
    client.post("/login", data={"username": "viewer", "password": "secret"})
    r = client.get("/teams/alpha")
    assert r.status_code == 200
    assert "orchestrator" in r.text


def test_team_forbidden_for_unknown(client: TestClient) -> None:
    client.post("/login", data={"username": "viewer", "password": "secret"})
    r = client.get("/teams/other")
    assert r.status_code == 403


def test_admin_requires_admin(client: TestClient) -> None:
    client.post("/login", data={"username": "viewer", "password": "secret"})
    assert client.get("/admin").status_code == 403

    client.post("/logout")
    client.post("/login", data={"username": "admin", "password": "secret"})
    assert client.get("/admin").status_code == 200
    assert "admin" in r.text if (r := client.get("/admin")) else False


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
