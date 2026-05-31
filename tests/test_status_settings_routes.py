"""HTMX-Status-Fragmente (/admin/settings/status)."""

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


def test_status_page_htmx_shell(client: TestClient) -> None:
    _login(client)
    r = client.get("/admin/settings/status")
    assert r.status_code == 200
    assert "hx-get=\"/admin/settings/status/fragment\"" in r.text
    assert "status-live" in r.text


def test_status_fragment_hosts(client: TestClient) -> None:
    _login(client)
    r = client.get(
        "/admin/settings/status/fragment/hosts",
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "status-hosts" in r.text
    assert "Erneut testen" in r.text


def test_status_fragment_single_host(client: TestClient) -> None:
    _login(client)
    r = client.get(
        "/admin/settings/status/fragment/hosts/local",
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert 'id="host-local"' in r.text


def test_status_fragment_full(client: TestClient) -> None:
    _login(client)
    r = client.get(
        "/admin/settings/status/fragment",
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "status-llm" in r.text
    assert "status-qdrant" in r.text


def test_status_fragment_requires_admin(client: TestClient) -> None:
    assert client.get("/admin/settings/status/fragment").status_code == 401
