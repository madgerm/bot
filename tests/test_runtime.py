import json
from pathlib import Path

import pytest

from bot.messages import MessageService
from bot.runtime import Supervisor


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
                    "communication": {
                        "inbox_base": "teams/{team_id}/agents/{agent_id}/inbox"
                    },
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


def test_supervisor_pipeline(runtime_project: Path) -> None:
    service = MessageService(runtime_project)
    sent = service.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="orchestrator",
        subject="Nutzer-Aufgabe",
        content="Baue Feature X",
    )
    assert sent.status == "pending"

    supervisor = Supervisor(runtime_project)
    processed = supervisor.run_until_idle(team_ids=["alpha"])
    assert processed >= 3

    orch_inbox = service.list_inbox("alpha", "orchestrator")
    assert any(m.type == "delegation_result" for m in orch_inbox)

    pending_exec = service.list_inbox("alpha", "worker-exec", status="pending")
    pending_review = service.list_inbox("alpha", "worker-review", status="pending")
    assert not pending_exec
    assert not pending_review


def test_run_once_cli(runtime_project: Path) -> None:
    from bot.cli import main

    service = MessageService(runtime_project)
    service.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="orchestrator",
        subject="CLI Pipeline",
        content="Test",
    )

    with pytest.raises(SystemExit) as exc:
        main(["run", "--root", str(runtime_project), "--team", "alpha", "--once"])
    assert exc.value.code == 0
