"""Integration: Message → run --once → done."""

from pathlib import Path

from bot.messages import MessageService


def test_message_pipeline_until_done(runtime_project: Path) -> None:
    svc = MessageService(runtime_project)
    svc.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="orchestrator",
        subject="E2E",
        content="Integrationstest",
    )

    from bot.runtime import Supervisor

    supervisor = Supervisor(runtime_project)
    processed = supervisor.run_until_idle(team_ids=["alpha"], max_rounds=30)
    assert processed >= 1

    pending = svc.list_inbox("alpha", "worker-exec", status="pending")
    pending_review = svc.list_inbox("alpha", "worker-review", status="pending")
    assert not pending
    assert not pending_review
