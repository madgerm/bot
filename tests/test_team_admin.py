"""Team- und Agent-Konfiguration (Panel)."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.agents_mgmt import AgentManager
from bot.config.writers.team_admin import (
    TeamAdminError,
    load_team_config,
    save_team_general,
    save_team_pipeline,
)


@pytest.fixture
def team_root(runtime_project: Path) -> Path:
    return runtime_project


def test_save_team_general(team_root: Path) -> None:
    save_team_general(
        team_root,
        "alpha",
        actor="admin",
        name="Alpha Team",
        enabled=True,
        preset="generic",
        orchestrator_id="orchestrator",
    )
    cfg = load_team_config(team_root, "alpha")
    assert cfg.team.name == "Alpha Team"


def test_save_pipeline_validates_agent(team_root: Path) -> None:
    with pytest.raises(TeamAdminError, match="fehlt"):
        save_team_pipeline(
            team_root,
            "alpha",
            actor="admin",
            execute="nonexistent-agent",
            review="worker-exec",
            document="",
        )


def test_agent_update_task_categories(team_root: Path) -> None:
    mgr = AgentManager(team_root)
    mgr.update_agent(
        "alpha",
        "worker-exec",
        task_categories=["coding", "review"],
        system_prompt_extra="Nur Backend.",
    )
    block = mgr.get_agent_block("alpha", "worker-exec")
    assert block.task_categories == ["coding", "review"]
    assert block.system_prompt_extra == "Nur Backend."
