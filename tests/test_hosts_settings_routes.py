"""HTTP-Routen /admin/settings/hosts und /status."""

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
    r = client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    assert r.status_code == 302


def test_hosts_list_requires_admin(client: TestClient) -> None:
    assert client.get("/admin/settings/hosts").status_code == 401
    _login(client)
    r = client.get("/admin/settings/hosts")
    assert r.status_code == 200
    assert "team_hosts.json" in r.text
    assert "/admin/settings/hosts/wizard" in r.text


def test_create_remote_host(client: TestClient, web_project: Path) -> None:
    _login(client)
    r = client.post(
        "/admin/settings/hosts/new",
        data={
            "host_id": "sat-1",
            "label": "Satellit",
            "mode": "remote",
            "base_url": "http://10.0.0.5:8443",
            "token_env": "BOT_TEAM_API_TOKEN",
            "team_alpha": "on",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    hosts = json.loads((web_project / "config" / "team_hosts.json").read_text())
    ids = [h["id"] for h in hosts["hosts"]]
    assert "sat-1" in ids


def test_wizard_generates_token(client: TestClient) -> None:
    _login(client)
    r = client.post(
        "/admin/settings/hosts/wizard",
        data={
            "setup": "remote",
            "host_id": "wiz-1",
            "label": "Wizard Host",
            "base_url": "http://192.168.1.1:8443",
            "token_env": "BOT_WIZ_TOKEN",
            "team_alpha": "on",
        },
    )
    assert r.status_code == 200, r.text[:500]
    assert "BOT_WIZ_TOKEN=" in r.text
    assert "Konfiguration gespeichert" in r.text


def test_status_page(client: TestClient) -> None:
    _login(client)
    r = client.get("/admin/settings/status")
    assert r.status_code == 200
    assert "status-live" in r.text
    assert "/admin/settings/status/fragment" in r.text
    assert "LLM" in r.text
