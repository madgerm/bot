"""Health- und Queue-Metriken."""

from pathlib import Path

from bot.health import collect_health, inbox_queue_stats
from bot.messages import MessageService


def test_inbox_queue_stats_empty(runtime_project: Path) -> None:
    stats = inbox_queue_stats(runtime_project)
    assert stats["pending_total"] == 0
    assert len(stats["agents"]) == 3


def test_inbox_queue_counts_pending(runtime_project: Path) -> None:
    svc = MessageService(runtime_project)
    svc.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="worker-exec",
        subject="T",
        content="C",
    )
    stats = inbox_queue_stats(runtime_project)
    assert stats["pending_total"] >= 1


def test_collect_health(runtime_project: Path) -> None:
    payload = collect_health(runtime_project, running=True, teams_active=1, agents_active=3)
    assert payload["status"] == "ok"
    assert payload["supervisor"]["running"] is True
    assert "queues" in payload
