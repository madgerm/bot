"""Serialisierung für Team-API-Responses."""

from __future__ import annotations

from bot.dashboard import TeamDashboard


def dashboard_to_dict(dashboard: TeamDashboard) -> dict:
    return {
        "team_id": dashboard.team_id,
        "team_name": dashboard.team_name,
        "orchestrator_id": dashboard.orchestrator_id,
        "enabled": dashboard.enabled,
        "agents": [
            {
                "agent_id": agent.agent_id,
                "role": agent.role,
                "enabled": agent.enabled,
                "pending": agent.pending,
                "processing": agent.processing,
                "done": agent.done,
                "failed": agent.failed,
                "recent": [m.model_dump(mode="json") for m in agent.recent],
            }
            for agent in dashboard.agents
        ],
    }
