"""Clients für lokalen oder entfernten Team-Runner."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

from bot.config import load_runtime_config
from bot.dashboard import AgentStatus, TeamDashboard, build_team_dashboard
from bot.messages.models import Message


class TeamHostError(Exception):
    """Fehler bei der Verbindung zum Team-Runner."""


class TeamHostClient(ABC):
    @property
    @abstractmethod
    def host_id(self) -> str: ...

    @property
    @abstractmethod
    def label(self) -> str: ...

    @property
    @abstractmethod
    def mode(self) -> str: ...

    @abstractmethod
    def connection_display(self) -> str: ...

    @abstractmethod
    def list_teams(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_dashboard(self, team_id: str) -> TeamDashboard: ...

    @abstractmethod
    def system_name(self) -> str: ...


class LocalTeamHost(TeamHostClient):
    def __init__(self, *, host_id: str, label: str, root: Path) -> None:
        self._id = host_id
        self._label = label
        self._root = root.resolve()

    @property
    def host_id(self) -> str:
        return self._id

    @property
    def label(self) -> str:
        return self._label

    @property
    def mode(self) -> str:
        return "local"

    def connection_display(self) -> str:
        return f"lokal: {self._root}"

    def list_teams(self) -> list[dict[str, Any]]:
        config = load_runtime_config(self._root)
        return [
            {
                "id": tid,
                "name": bundle.team.team.name,
                "enabled": bundle.team.team.enabled,
                "agent_count": len(bundle.agents),
                "host_id": self._id,
                "host_label": self._label,
                "connection": self.connection_display(),
            }
            for tid, bundle in sorted(config.teams.items())
        ]

    def get_dashboard(self, team_id: str) -> TeamDashboard:
        return build_team_dashboard(self._root, team_id)

    def system_name(self) -> str:
        return load_runtime_config(self._root).system.system.name


class RemoteTeamHost(TeamHostClient):
    def __init__(
        self,
        *,
        host_id: str,
        label: str,
        base_url: str,
        token_env: str,
    ) -> None:
        self._id = host_id
        self._label = label
        self._base_url = base_url.rstrip("/")
        self._token_env = token_env

    @property
    def host_id(self) -> str:
        return self._id

    @property
    def label(self) -> str:
        return self._label

    @property
    def mode(self) -> str:
        return "remote"

    def _token(self) -> str:
        token = os.environ.get(self._token_env)
        if not token:
            raise TeamHostError(
                f"Umgebungsvariable '{self._token_env}' ist nicht gesetzt "
                f"(Remote-Host '{self._id}')"
            )
        return token

    def connection_display(self) -> str:
        return self._base_url

    def _request(self, method: str, path: str) -> Any:
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._token()}"}
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.request(method, url, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise TeamHostError(f"Remote-Anfrage fehlgeschlagen ({url}): {exc}") from exc

    def list_teams(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/api/v1/teams")
        teams = data.get("teams", [])
        for team in teams:
            team["host_id"] = self._id
            team["host_label"] = self._label
            team["connection"] = self.connection_display()
        return teams

    def get_dashboard(self, team_id: str) -> TeamDashboard:
        data = self._request("GET", f"/api/v1/teams/{team_id}/dashboard")
        agents = []
        for agent in data["agents"]:
            recent = [Message.model_validate(m) for m in agent.get("recent", [])]
            agents.append(
                AgentStatus(
                    agent_id=agent["agent_id"],
                    role=agent["role"],
                    enabled=agent["enabled"],
                    pending=agent["pending"],
                    processing=agent["processing"],
                    done=agent["done"],
                    failed=agent["failed"],
                    recent=recent,
                )
            )
        return TeamDashboard(
            team_id=data["team_id"],
            team_name=data["team_name"],
            orchestrator_id=data["orchestrator_id"],
            enabled=data["enabled"],
            agents=agents,
        )

    def system_name(self) -> str:
        data = self._request("GET", "/api/v1/info")
        return data.get("system_name", "remote")
