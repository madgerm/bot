import json
from pathlib import Path

import pytest


@pytest.fixture
def runtime_project(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "system.json").write_text(
        json.dumps(
            {
                "system": {
                    "name": "test-runtime",
                    "polling": {"interval_seconds": 1},
                    "llm": {"enabled": False},
                    "communication": {
                        "inbox_base": "teams/{team_id}/agents/{agent_id}/inbox"
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "task_models.json").write_text(
        json.dumps(
            {
                "task_models": {
                    "planning": {"default": "stub/plan", "alternatives": []},
                    "coding": {"default": "stub/code", "alternatives": ["stub/code-alt"]},
                    "review": {"default": "stub/review", "alternatives": []},
                }
            }
        ),
        encoding="utf-8",
    )

    team_dir = tmp_path / "teams" / "alpha"
    team_dir.mkdir(parents=True)
    (team_dir / "team.json").write_text(
        json.dumps(
            {
                "team": {
                    "id": "alpha",
                    "name": "Alpha",
                    "orchestrator_id": "orchestrator",
                }
            }
        ),
        encoding="utf-8",
    )
    for agent_id, role in (
        ("orchestrator", "orchestrator"),
        ("worker-exec", "worker"),
        ("worker-review", "reviewer"),
    ):
        agent_dir = team_dir / "agents" / agent_id
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.json").write_text(
            json.dumps({"agent": {"id": agent_id, "role": role, "enabled": True}}),
            encoding="utf-8",
        )
    return tmp_path
