"""Health- und Queue-Metriken für Panel und Team-API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bot.config import ConfigLoadError, load_runtime_config
from bot.messages.mailbox import Mailbox


def inbox_queue_stats(root: Path | str) -> dict[str, Any]:
    """Zählt pending/processing Messages pro Agent-Inbox."""
    root_path = Path(root).resolve()
    try:
        config = load_runtime_config(root_path)
    except ConfigLoadError as exc:
        return {"error": str(exc), "agents": [], "pending_total": 0, "processing_total": 0}

    inbox_template = config.system.system.communication.inbox_base
    agents: list[dict[str, Any]] = []
    pending_total = 0
    processing_total = 0
    failed_total = 0

    for team_id, bundle in config.teams.items():
        if not bundle.team.team.enabled:
            continue
        for agent_id, agent_cfg in bundle.agents.items():
            if not agent_cfg.agent.enabled:
                continue
            mailbox = Mailbox(root_path, team_id, agent_id, inbox_template)
            pending = len(mailbox.list_messages(status="pending"))
            processing = len(mailbox.list_messages(status="processing"))
            failed = len(mailbox.list_messages(status="failed"))
            pending_total += pending
            processing_total += processing
            failed_total += failed
            agents.append(
                {
                    "team_id": team_id,
                    "agent_id": agent_id,
                    "pending": pending,
                    "processing": processing,
                    "failed": failed,
                }
            )

    return {
        "agents": agents,
        "pending_total": pending_total,
        "processing_total": processing_total,
        "failed_total": failed_total,
    }


def collect_health(
    root: Path | str,
    *,
    running: bool | None = None,
    teams_active: int | None = None,
    agents_active: int | None = None,
) -> dict[str, Any]:
    """Aggregiert Status für /health Endpoints."""
    root_path = Path(root).resolve()
    queues = inbox_queue_stats(root_path)
    payload: dict[str, Any] = {
        "status": "ok" if "error" not in queues else "degraded",
        "queues": queues,
    }
    if running is not None:
        payload["supervisor"] = {
            "running": running,
            "teams": teams_active,
            "agents": agents_active,
        }
    try:
        config = load_runtime_config(root_path)
        payload["system"] = config.system.system.name
        payload["llm_enabled"] = config.system.system.llm.enabled
    except ConfigLoadError:
        pass
    return payload
