"""Agent-CRUD auf dem Dateisystem."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from bot.config.loader import load_runtime_config
from bot.config.models import AgentBlock, AgentConfig
from bot.config.writers import atomic_write_json


class AgentManagerError(Exception):
    pass


class AgentManager:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def get_agent_block(self, team_id: str, agent_id: str) -> AgentBlock:
        path = self._agent_json(team_id, agent_id)
        cfg = AgentConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))
        return cfg.agent

    def list_agents(self, team_id: str) -> list[dict]:
        cfg = load_runtime_config(self.root)
        if team_id not in cfg.teams:
            raise AgentManagerError(f"Team '{team_id}' nicht gefunden")
        result = []
        for agent_id, agent_cfg in cfg.teams[team_id].agents.items():
            block = agent_cfg.agent
            result.append(
                {
                    "id": agent_id,
                    "role": block.role,
                    "enabled": block.enabled,
                    "interval_seconds": block.interval_seconds,
                    "display_name": block.display_name,
                    "task_categories": block.task_categories,
                    "system_prompt_extra": block.system_prompt_extra,
                    "tools_allow": block.tools_allow,
                    "tools_deny": block.tools_deny,
                    "qdrant_collections": block.qdrant_collections,
                }
            )
        return sorted(result, key=lambda x: x["id"])

    def create_agent(
        self,
        team_id: str,
        *,
        agent_id: str,
        role: str = "worker",
        enabled: bool = True,
        interval_seconds: float | None = None,
        display_name: str | None = None,
    ) -> dict:
        team_dir = self.root / "teams" / team_id
        if not team_dir.is_dir():
            raise AgentManagerError(f"Team-Verzeichnis fehlt: {team_dir}")
        agent_dir = team_dir / "agents" / agent_id
        if agent_dir.exists():
            raise AgentManagerError(f"Agent '{agent_id}' existiert bereits")
        agent_dir.mkdir(parents=True)
        (agent_dir / "inbox").mkdir()
        (agent_dir / "outbox").mkdir()
        block = AgentBlock(
            id=agent_id,
            role=role,  # type: ignore[arg-type]
            enabled=enabled,
            interval_seconds=interval_seconds,
            display_name=display_name,
        )
        cfg = AgentConfig(agent=block)
        path = agent_dir / "agent.json"
        atomic_write_json(path, cfg.model_dump())
        return {"id": agent_id, "path": str(path)}

    def update_agent(
        self,
        team_id: str,
        agent_id: str,
        *,
        role: str | None = None,
        enabled: bool | None = None,
        interval_seconds: float | None = None,
        display_name: str | None = None,
        task_categories: list[str] | None = None,
        system_prompt_extra: str | None = None,
        tools_allow: list[str] | None = None,
        tools_deny: list[str] | None = None,
        qdrant_collections: list[str] | None = None,
        clear_interval: bool = False,
        clear_display_name: bool = False,
        clear_prompt_extra: bool = False,
    ) -> dict:
        path = self._agent_json(team_id, agent_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        agent = data.get("agent", {})
        if role is not None:
            agent["role"] = role
        if enabled is not None:
            agent["enabled"] = enabled
        if clear_interval:
            agent["interval_seconds"] = None
        elif interval_seconds is not None:
            agent["interval_seconds"] = interval_seconds
        if clear_display_name:
            agent["display_name"] = None
        elif display_name is not None:
            agent["display_name"] = display_name or None
        if task_categories is not None:
            agent["task_categories"] = task_categories
        if clear_prompt_extra:
            agent["system_prompt_extra"] = None
        elif system_prompt_extra is not None:
            agent["system_prompt_extra"] = system_prompt_extra or None
        if tools_allow is not None:
            agent["tools_allow"] = tools_allow
        if tools_deny is not None:
            agent["tools_deny"] = tools_deny
        if qdrant_collections is not None:
            agent["qdrant_collections"] = qdrant_collections
        cfg = AgentConfig.model_validate({"agent": agent})
        atomic_write_json(path, cfg.model_dump())
        return {"id": agent_id, "updated": True}

    def delete_agent(self, team_id: str, agent_id: str) -> None:
        cfg = load_runtime_config(self.root)
        if team_id not in cfg.teams:
            raise AgentManagerError(f"Team '{team_id}' nicht gefunden")
        bundle = cfg.teams[team_id]
        if agent_id == bundle.team.team.orchestrator_id:
            raise AgentManagerError("Orchestrator kann nicht gelöscht werden")
        agent_dir = self.root / "teams" / team_id / "agents" / agent_id
        if not agent_dir.is_dir():
            raise AgentManagerError(f"Agent '{agent_id}' nicht gefunden")
        shutil.rmtree(agent_dir)

    def _agent_json(self, team_id: str, agent_id: str) -> Path:
        path = self.root / "teams" / team_id / "agents" / agent_id / "agent.json"
        if not path.is_file():
            raise AgentManagerError(f"Agent '{agent_id}' nicht gefunden")
        return path
