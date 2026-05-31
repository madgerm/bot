"""Team-Hosts Admin Writer."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.config.writers.hosts_admin import (
    HostsAdminError,
    TeamApiAdminConfig,
    create_host,
    delete_host,
    load_hosts_admin,
    load_team_api_admin,
    probe_host_connection,
    save_team_api_admin,
    update_host,
)
from bot.hosts.models import TeamHostEntry


def test_save_team_api_and_hosts_roundtrip(runtime_project: Path) -> None:
    save_team_api_admin(
        runtime_project,
        TeamApiAdminConfig(token_env="BOT_TEST_TOKEN", teams=["alpha"]),
        actor="admin",
    )
    loaded = load_team_api_admin(runtime_project)
    assert loaded.token_env == "BOT_TEST_TOKEN"
    assert loaded.teams == ["alpha"]

    entry = TeamHostEntry(
        id="remote-a",
        label="Remote A",
        mode="remote",
        teams=["alpha"],
        base_url="http://runner.local:8443",
        token_env="BOT_TEST_TOKEN",
    )
    create_host(runtime_project, entry, actor="admin")
    cfg = load_hosts_admin(runtime_project)
    assert any(h.id == "remote-a" for h in cfg.hosts)

    updated = entry.model_copy(update={"label": "Remote B"})
    update_host(runtime_project, "remote-a", updated, actor="admin")
    assert load_hosts_admin(runtime_project).hosts[1].label == "Remote B"


def test_delete_host_requires_one_left(runtime_project: Path) -> None:
    cfg = load_hosts_admin(runtime_project)
    only = cfg.hosts[0]
    with pytest.raises(HostsAdminError, match="Mindestens ein Host"):
        delete_host(runtime_project, only.id, actor="admin")


def test_local_connection_ok(runtime_project: Path) -> None:
    cfg = load_hosts_admin(runtime_project)
    local = cfg.hosts[0]
    result = probe_host_connection(runtime_project, local)
    assert result["ok"] is True


def test_remote_connection_needs_token(
    runtime_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = TeamHostEntry(
        id="r1",
        label="R",
        mode="remote",
        teams=[],
        base_url="http://127.0.0.1:9",
        token_env="MISSING_ENV_XYZ",
    )
    monkeypatch.delenv("MISSING_ENV_XYZ", raising=False)
    result = probe_host_connection(runtime_project, entry)
    assert result["ok"] is False
    assert "nicht gesetzt" in result["summary"]


def test_remote_health_via_monkeypatch(
    runtime_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from bot.team_api import create_team_api_app
    from bot.team_api.auth import generate_api_token

    token = generate_api_token()
    monkeypatch.setenv("BOT_TEAM_API_TOKEN", token)
    api = TestClient(create_team_api_app(runtime_project))

    entry = TeamHostEntry(
        id="r2",
        label="R2",
        mode="remote",
        teams=["alpha"],
        base_url="http://testserver",
        token_env="BOT_TEAM_API_TOKEN",
    )

    import httpx

    class _FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str, headers: dict | None = None):
            assert headers and headers["Authorization"] == f"Bearer {token}"
            r = api.get("/api/v1/health", headers=headers)
            return _FakeResponse(r.json())

    monkeypatch.setattr(httpx, "Client", _FakeClient)
    result = probe_host_connection(runtime_project, entry)
    assert result["ok"] is True
