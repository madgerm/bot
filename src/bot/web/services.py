"""Daten für Dashboard und Team-Ansicht."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bot.config import ConfigLoadError, load_runtime_config
from bot.messages import Message, MessageService


@dataclass
class AgentStatus:
    agent_id: str
    role: str
    enabled: bool
    pending: int
    processing: int
    done: int
    failed: int
    recent: list[Message]


@dataclass
class TeamDashboard:
    team_id: str
    team_name: str
    orchestrator_id: str
    enabled: bool
    agents: list[AgentStatus]


def build_team_dashboard(root: Path, team_id: str) -> TeamDashboard:
    config = load_runtime_config(root)
    if team_id not in config.teams:
        raise ConfigLoadError(f"Unbekanntes Team '{team_id}'")

    bundle = config.teams[team_id]
    service = MessageService(root)
    agents: list[AgentStatus] = []

    for agent_id, agent_cfg in sorted(bundle.agents.items()):
        pending = service.list_inbox(team_id, agent_id, status="pending")
        processing = service.list_inbox(team_id, agent_id, status="processing")
        done = service.list_inbox(team_id, agent_id, status="done")
        failed = service.list_inbox(team_id, agent_id, status="failed")
        recent = service.list_inbox(team_id, agent_id)[-5:]

        agents.append(
            AgentStatus(
                agent_id=agent_id,
                role=agent_cfg.agent.role,
                enabled=agent_cfg.agent.enabled,
                pending=len(pending),
                processing=len(processing),
                done=len(done),
                failed=len(failed),
                recent=recent,
            )
        )

    return TeamDashboard(
        team_id=team_id,
        team_name=bundle.team.team.name,
        orchestrator_id=bundle.team.team.orchestrator_id,
        enabled=bundle.team.team.enabled,
        agents=agents,
    )


def list_accessible_teams(root: Path, team_ids: list[str] | None, *, is_admin: bool) -> list[dict]:
    config = load_runtime_config(root)
    teams = []
    for tid, bundle in sorted(config.teams.items()):
        if not is_admin and team_ids is not None and tid not in team_ids:
            continue
        teams.append(
            {
                "id": tid,
                "name": bundle.team.team.name,
                "enabled": bundle.team.team.enabled,
                "agent_count": len(bundle.agents),
            }
        )
    return teams
