import json
from pathlib import Path

import pytest

from bot.messages import Mailbox, MessageError, MessageService, new_message
from bot.messages.workflow import InvalidTransitionError, assert_transition


@pytest.fixture
def mini_project(project_root: Path) -> Path:
    return project_root


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "system.json").write_text(
        json.dumps(
            {
                "system": {
                    "name": "test-runtime",
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
        ("worker-a", "worker"),
    ):
        agent_dir = team_dir / "agents" / agent_id
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.json").write_text(
            json.dumps({"agent": {"id": agent_id, "role": role}}),
            encoding="utf-8",
        )
    return tmp_path


def test_status_transitions() -> None:
    assert_transition("pending", "processing")
    with pytest.raises(InvalidTransitionError):
        assert_transition("pending", "done")
    with pytest.raises(InvalidTransitionError):
        assert_transition("done", "pending")


def test_send_and_claim(mini_project: Path) -> None:
    service = MessageService(mini_project)
    sent = service.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="worker-a",
        subject="Test",
        content="Hallo Worker",
    )
    assert sent.status == "pending"

    inbox = service.list_inbox("alpha", "worker-a", status="pending")
    assert len(inbox) == 1
    assert inbox[0].id == sent.id

    outbox = (mini_project / "teams/alpha/agents/orchestrator/outbox" / f"{sent.id}.json")
    assert outbox.is_file()

    claimed = service.claim("alpha", "worker-a")
    assert claimed is not None
    assert claimed.status == "processing"

    done = service.complete("alpha", "worker-a", sent.id)
    assert done.status == "done"
    processed = (
        mini_project
        / "teams/alpha/agents/worker-a/inbox/processed"
        / f"{sent.id}.json"
    )
    assert processed.is_file()


def test_idempotent_done_reject(mini_project: Path) -> None:
    service = MessageService(mini_project)
    sent = service.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="worker-a",
        subject="A",
        content="B",
    )
    service.claim("alpha", "worker-a")
    service.complete("alpha", "worker-a", sent.id)

    duplicate = new_message(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="worker-a",
        subject="A",
        content="B",
    )
    duplicate = duplicate.model_copy(update={"id": sent.id})
    mailbox = Mailbox(
        mini_project,
        "alpha",
        "worker-a",
        "teams/{team_id}/agents/{agent_id}/inbox",
    )
    with pytest.raises(MessageError, match="bereits erledigt"):
        mailbox.receive(duplicate)


def test_fail_and_retry(mini_project: Path) -> None:
    service = MessageService(mini_project)
    sent = service.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="worker-a",
        subject="X",
        content="Y",
    )
    service.claim("alpha", "worker-a")
    failed = service.fail("alpha", "worker-a", sent.id, error="timeout")
    assert failed.status == "failed"

    retried = service.retry("alpha", "worker-a", sent.id)
    assert retried.status == "pending"
    assert retried.retry_count == 1


def test_unknown_team_raises(mini_project: Path) -> None:
    service = MessageService(mini_project)
    with pytest.raises(MessageError, match="Unbekanntes Team"):
        service.send(
            team_id="missing",
            from_agent="orchestrator",
            to_agent="worker-a",
            subject="S",
            content="C",
        )
