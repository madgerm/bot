"""Agent-spezifische Tools und Qdrant-Collections."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bot.config.models import AgentBlock
from bot.runtime.agent_tools import resolve_allowed_tools, validate_qdrant_collection


def test_tools_allow_restricts_worker() -> None:
    agent = AgentBlock(id="w", role="worker", tools_allow=["read_file", "list_files"])
    allowed = resolve_allowed_tools("worker", agent)
    assert allowed == frozenset({"read_file", "list_files"})


def test_tools_deny_subtracts() -> None:
    agent = AgentBlock(
        id="w",
        role="worker",
        tools_allow=["read_file", "write_file", "git_status"],
        tools_deny=["git_status"],
    )
    allowed = resolve_allowed_tools("worker", agent)
    assert "git_status" not in allowed
    assert "read_file" in allowed


def test_qdrant_collections_filter() -> None:
    agent = AgentBlock(id="w", role="worker", qdrant_collections=["project"])
    assert validate_qdrant_collection(agent, "project") == "project"
    with pytest.raises(ValueError, match="nicht erlaubt"):
        validate_qdrant_collection(agent, "background")


@pytest.fixture
def panel_client(runtime_project: Path) -> TestClient:
    from fastapi.testclient import TestClient

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
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return TestClient(create_app(runtime_project))


def test_save_agent_tools_via_panel(runtime_project: Path, panel_client: TestClient) -> None:
    panel_client.get("/login")
    panel_client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    r = panel_client.post(
        "/teams/alpha/settings/agents/worker-exec/save",
        data={
            "role": "worker",
            "enabled": "on",
            "tool_read_file": "on",
            "tool_list_files": "on",
            "know_project": "on",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    data = json.loads(
        (runtime_project / "teams" / "alpha" / "agents" / "worker-exec" / "agent.json").read_text()
    )
    assert set(data["agent"]["tools_allow"]) == {"read_file", "list_files"}
    assert data["agent"]["qdrant_collections"] == ["project"]
