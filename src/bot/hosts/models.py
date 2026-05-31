"""Konfiguration für Team-Hosts (Web-Panel → Team-Runner)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TeamHostEntry(BaseModel):
    """Ein Team-Runner-Endpunkt (lokal oder remote)."""

    id: str
    label: str
    mode: Literal["local", "remote"]
    teams: list[str] = Field(default_factory=list)
    base_url: str | None = None
    token_env: str | None = Field(
        default=None,
        description="Name der Umgebungsvariable mit dem API-Token (nur remote)",
    )
    channel: bool = False
    """Panel baut WebSocket zum Runner auf (LLM-Queue, Runner muss Panel nicht anrufen)."""

    @model_validator(mode="after")
    def validate_remote(self) -> TeamHostEntry:
        if self.mode == "remote":
            if not self.base_url:
                raise ValueError(f"Host '{self.id}': remote braucht base_url")
            if not self.token_env:
                raise ValueError(f"Host '{self.id}': remote braucht token_env")
        return self


class TeamHostsConfig(BaseModel):
    hosts: list[TeamHostEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_team_mappings(self) -> TeamHostsConfig:
        seen: dict[str, str] = {}
        for host in self.hosts:
            for team_id in host.teams:
                if team_id in seen:
                    raise ValueError(
                        f"Team '{team_id}' ist mehrfach zugeordnet "
                        f"({seen[team_id]} und {host.id})"
                    )
                seen[team_id] = host.id
        return self
