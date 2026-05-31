"""Lädt team_hosts.json und liefert Clients pro Team."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from bot.config import ConfigLoadError, load_runtime_config
from bot.hosts.client import LocalTeamHost, RemoteTeamHost, TeamHostClient, TeamHostError
from bot.hosts.models import TeamHostEntry, TeamHostsConfig


def load_team_hosts_config(panel_root: Path) -> TeamHostsConfig:
    path = panel_root / "config" / "team_hosts.json"
    if not path.is_file():
        return TeamHostsConfig(
            hosts=[
                TeamHostEntry(
                    id="local",
                    label="Lokal (Standard)",
                    mode="local",
                    teams=[],
                )
            ]
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return TeamHostsConfig.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise TeamHostError(f"team_hosts.json ungültig: {exc}") from exc


@dataclass
class TeamHostEntryRef:
    entry: TeamHostEntry
    client: TeamHostClient


class HostRegistry:
    """Verbindet das Web-Panel mit einem oder mehreren Team-Runnern."""

    def __init__(self, panel_root: Path) -> None:
        self.panel_root = panel_root.resolve()
        self.config = load_team_hosts_config(self.panel_root)
        self._team_to_host: dict[str, TeamHostEntryRef] = {}
        for entry in self.config.hosts:
            client = self._build_client(entry)
            for team_id in entry.teams:
                self._team_to_host[team_id] = TeamHostEntryRef(entry=entry, client=client)

    def _build_client(self, entry: TeamHostEntry) -> TeamHostClient:
        if entry.mode == "local":
            return LocalTeamHost(
                host_id=entry.id,
                label=entry.label,
                root=self.panel_root,
            )
        assert entry.base_url and entry.token_env
        return RemoteTeamHost(
            host_id=entry.id,
            label=entry.label,
            base_url=entry.base_url,
            token_env=entry.token_env,
        )

    def client_for_team(self, team_id: str) -> TeamHostClient:
        ref = self._team_to_host.get(team_id)
        if ref is None:
            return LocalTeamHost(
                host_id="local",
                label="Lokal (Fallback)",
                root=self.panel_root,
            )
        return ref.client

    def list_hosts(self) -> list[dict]:
        return [
            {
                "id": h.id,
                "label": h.label,
                "mode": h.mode,
                "teams": h.teams,
                "base_url": h.base_url,
                "token_env": h.token_env,
                "channel": h.channel,
            }
            for h in self.config.hosts
        ]

    def list_teams_for_user(
        self, user_team_ids: list[str] | None, *, is_admin: bool
    ) -> list[dict]:
        teams: list[dict] = []
        if self._team_to_host:
            for team_id, ref in sorted(self._team_to_host.items()):
                if not is_admin and user_team_ids is not None and team_id not in user_team_ids:
                    continue
                try:
                    for item in ref.client.list_teams():
                        if item["id"] == team_id:
                            teams.append(item)
                            break
                except (TeamHostError, ConfigLoadError) as exc:
                    teams.append(
                        {
                            "id": team_id,
                            "name": f"Fehler: {team_id}",
                            "enabled": False,
                            "agent_count": 0,
                            "host_id": ref.entry.id,
                            "host_label": ref.entry.label,
                            "connection": ref.client.connection_display(),
                            "error": str(exc),
                        }
                    )
            return teams

        client = LocalTeamHost(host_id="local", label="Lokal", root=self.panel_root)
        all_teams = client.list_teams()
        if is_admin:
            return all_teams
        return [t for t in all_teams if user_team_ids is None or t["id"] in user_team_ids]

    def system_name(self) -> str:
        if self.config.hosts:
            return self._build_client(self.config.hosts[0]).system_name()
        return load_runtime_config(self.panel_root).system.system.name
