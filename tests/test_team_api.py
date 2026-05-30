import json
import os

import pytest
from fastapi.testclient import TestClient

from bot.team_api import create_team_api_app
from bot.team_api.auth import generate_api_token


@pytest.fixture
def api_client(runtime_project, monkeypatch: pytest.MonkeyPatch):
    token = generate_api_token()
    monkeypatch.setenv("BOT_TEAM_API_TOKEN", token)
    app = create_team_api_app(runtime_project)
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def test_team_api_health(api_client: TestClient) -> None:
    data = api_client.get("/api/v1/health").json()
    assert data["status"] == "ok"
    assert "queues" in data


def test_team_api_dashboard(api_client: TestClient) -> None:
    teams = api_client.get("/api/v1/teams").json()["teams"]
    assert teams
    team_id = teams[0]["id"]
    dash = api_client.get(f"/api/v1/teams/{team_id}/dashboard").json()
    assert dash["team_id"] == team_id
    assert dash["agents"]


def test_remote_host_client(runtime_project, monkeypatch: pytest.MonkeyPatch) -> None:
    token = generate_api_token()
    monkeypatch.setenv("BOT_TEAM_API_TOKEN", token)

    api_app = create_team_api_app(runtime_project)
    api = TestClient(api_app)

    hosts_path = runtime_project / "config" / "team_hosts.json"
    hosts_path.write_text(
        json.dumps(
            {
                "hosts": [
                    {
                        "id": "local",
                        "label": "Lokal",
                        "mode": "local",
                        "teams": [],
                    },
                    {
                        "id": "remote",
                        "label": "Remote-Test",
                        "mode": "remote",
                        "base_url": "http://testserver",
                        "token_env": "BOT_TEAM_API_TOKEN",
                        "teams": ["alpha"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    from bot.hosts import HostRegistry, RemoteTeamHost

    registry = HostRegistry(runtime_project)
    client = registry.client_for_team("alpha")

    def fake_request(self, method: str, path: str):
        response = api.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()

    monkeypatch.setattr(RemoteTeamHost, "_request", fake_request)

    dashboard = client.get_dashboard("alpha")
    assert dashboard.team_id == "alpha"
