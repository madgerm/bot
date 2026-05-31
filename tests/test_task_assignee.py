"""Task-Board Assignee-Dropdown und default_task_assignee."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def panel_client(runtime_project: Path) -> TestClient:
    from bot.web import create_app

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
    return TestClient(create_app(runtime_project))


def test_default_task_assignee_exclusive(
    runtime_project: Path, panel_client: TestClient
) -> None:
    panel_client.get("/login")
    panel_client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    panel_client.post(
        "/teams/alpha/settings/agents/worker-exec/save",
        data={"role": "worker", "enabled": "on", "default_task_assignee": "on"},
        follow_redirects=False,
    )
    orch_path = runtime_project / "teams" / "alpha" / "agents" / "orchestrator" / "agent.json"
    orch = json.loads(orch_path.read_text())
    assert orch["agent"].get("default_task_assignee") in (False, None)
    worker = json.loads(
        (
            runtime_project / "teams" / "alpha" / "agents" / "worker-exec" / "agent.json"
        ).read_text()
    )
    assert worker["agent"]["default_task_assignee"] is True


def test_tasks_page_assignee_select(panel_client: TestClient) -> None:
    panel_client.get("/login")
    panel_client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    r = panel_client.get("/teams/alpha/tasks")
    assert r.status_code == 200
    assert 'name="assignee_agent"' in r.text
    assert "<select" in r.text
    assert "worker-exec" in r.text or "orchestrator" in r.text
