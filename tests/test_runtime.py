import pytest

from bot.messages import MessageService
from bot.runtime import Supervisor


def test_supervisor_pipeline(runtime_project) -> None:
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


def test_run_once_cli(runtime_project) -> None:
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
