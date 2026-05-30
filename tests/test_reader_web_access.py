"""Reader-Rolle: Lesen erlaubt, sensible POST-Aktionen blockiert."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bot.web import create_app


@pytest.fixture
def reader_web_project(web_project: Path) -> Path:
    data = json.loads((web_project / "config" / "users.json").read_text(encoding="utf-8"))
    data["users"].append(
        {
            "username": "reader",
            "password": "secret",
            "role": "user",
            "teams": ["alpha"],
            "team_access": [{"team_id": "alpha", "access": "reader"}],
        }
    )
    (web_project / "config" / "users.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    return web_project


@pytest.fixture
def reader_client(reader_web_project: Path) -> TestClient:
    client = TestClient(create_app(reader_web_project))
    client.get("/login")
    r = client.post(
        "/login",
        data={"username": "reader", "password": "secret"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    return client


def test_reader_can_view_mail_and_hours(reader_client: TestClient) -> None:
    assert reader_client.get("/teams/alpha/mail").status_code == 200
    assert reader_client.get("/teams/alpha/hours").status_code == 200


@pytest.mark.parametrize(
    "path,data",
    [
        (
            "/teams/alpha/mail/thread-1/draft",
            {"body_text": "x", "to_addrs": "", "subject": ""},
        ),
        ("/teams/alpha/mail/draft/d1/approve", {}),
        (
            "/teams/alpha/mail/draft/d1/send",
            {"confirm": "SEND"},
        ),
        ("/teams/alpha/hours/check", {}),
        ("/teams/alpha/hours/diff/d1/approve", {}),
        (
            "/teams/alpha/hours/diff/d1/publish",
            {"confirm": "PUBLISH"},
        ),
    ],
)
def test_reader_cannot_post_mail_or_hours(
    reader_client: TestClient, path: str, data: dict[str, str]
) -> None:
    r = reader_client.post(path, data=data, follow_redirects=False)
    assert r.status_code == 403
    assert "Leserechte" in r.json()["detail"]
