"""Lädt und validiert Konfigurationsdateien aus dem Projektroot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from bot.config.models import (
    AgentConfig,
    RuntimeConfig,
    SystemConfig,
    TaskModelsConfig,
    TeamBundle,
    TeamConfig,
)


class ConfigLoadError(Exception):
    """Fehler beim Laden oder Validieren der Konfiguration."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigLoadError(f"Datei nicht gefunden: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigLoadError(f"Ungültiges JSON in {path}: {exc}") from exc


def load_system_config(config_dir: Path) -> SystemConfig:
    path = config_dir / "system.json"
    try:
        return SystemConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigLoadError(f"system.json ungültig ({path}): {exc}") from exc


def load_task_models(config_dir: Path) -> TaskModelsConfig | None:
    path = config_dir / "task_models.json"
    if not path.is_file():
        return None
    try:
        return TaskModelsConfig.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ConfigLoadError(f"task_models.json ungültig ({path}): {exc}") from exc


def _load_team(team_dir: Path) -> TeamBundle:
    team_path = team_dir / "team.json"
    try:
        team = TeamConfig.model_validate(_read_json(team_path))
    except ValidationError as exc:
        raise ConfigLoadError(f"team.json ungültig ({team_path}): {exc}") from exc

    agents_dir = team_dir / "agents"
    agents: dict[str, AgentConfig] = {}
    if agents_dir.is_dir():
        for agent_dir in sorted(agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            agent_path = agent_dir / "agent.json"
            if not agent_path.is_file():
                continue
            try:
                agent_cfg = AgentConfig.model_validate(_read_json(agent_path))
            except ValidationError as exc:
                raise ConfigLoadError(
                    f"agent.json ungültig ({agent_path}): {exc}"
                ) from exc
            agent_id = agent_cfg.agent.id
            if agent_id in agents:
                raise ConfigLoadError(
                    f"Doppelte Agent-ID '{agent_id}' in Team '{team_dir.name}'"
                )
            agents[agent_id] = agent_cfg

    _validate_team_bundle(team_dir.name, team, agents)
    return TeamBundle(team=team, agents=agents)


def _validate_team_bundle(
    folder_slug: str,
    team: TeamConfig,
    agents: dict[str, AgentConfig],
) -> None:
    team_id = team.team.id
    if folder_slug != team_id:
        raise ConfigLoadError(
            f"Team-Ordner '{folder_slug}' passt nicht zu team.id '{team_id}'"
        )

    orch_id = team.team.orchestrator_id
    if orch_id not in agents:
        raise ConfigLoadError(
            f"Orchestrator '{orch_id}' fehlt in Team '{team_id}' "
            f"(vorhanden: {', '.join(sorted(agents)) or 'keine'})"
        )

    if agents[orch_id].agent.role != "orchestrator":
        raise ConfigLoadError(
            f"Agent '{orch_id}' ist als Orchestrator konfiguriert, "
            f"hat aber role='{agents[orch_id].agent.role}'"
        )


def discover_teams(teams_dir: Path) -> dict[str, TeamBundle]:
    if not teams_dir.is_dir():
        return {}

    teams: dict[str, TeamBundle] = {}
    for entry in sorted(teams_dir.iterdir()):
        if not entry.is_dir():
            continue
        if not (entry / "team.json").is_file():
            continue
        bundle = _load_team(entry)
        team_id = bundle.team.team.id
        if team_id in teams:
            raise ConfigLoadError(f"Doppelte Team-ID '{team_id}'")
        teams[team_id] = bundle
    return teams


def load_runtime_config(root: Path | str) -> RuntimeConfig:
    """Lädt system.json, optionale task_models.json und alle Teams."""
    root_path = Path(root).resolve()
    config_dir = root_path / "config"
    teams_dir = root_path / "teams"

    system = load_system_config(config_dir)
    task_models = load_task_models(config_dir)
    teams = discover_teams(teams_dir)

    return RuntimeConfig(system=system, task_models=task_models, teams=teams)
