"""Team anlegen und umbenennen."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.config.writers.hosts_admin import append_team_to_local_host, load_hosts_admin
from bot.config.writers.team_admin import (
    TeamAdminError,
    create_team,
    load_team_config,
    save_team_name,
)


def test_create_team(runtime_project: Path) -> None:
    create_team(
        runtime_project,
        "mein-team",
        actor="admin",
        name="Mein Team",
        preset="generic",
    )
    cfg = load_team_config(runtime_project, "mein-team")
    assert cfg.team.name == "Mein Team"
    assert (runtime_project / "teams/mein-team/agents/orchestrator/agent.json").is_file()


def test_create_team_duplicate(runtime_project: Path) -> None:
    with pytest.raises(TeamAdminError, match="existiert bereits"):
        create_team(runtime_project, "alpha", actor="a", name="X")


def test_save_team_name(runtime_project: Path) -> None:
    save_team_name(runtime_project, "alpha", actor="admin", name="Neuer Name")
    assert load_team_config(runtime_project, "alpha").team.name == "Neuer Name"


def test_append_team_to_local_host(runtime_project: Path) -> None:
    (runtime_project / "config" / "team_hosts.json").write_text(
        '{"hosts":[{"id":"local","label":"L","mode":"local","teams":["alpha"]}]}',
        encoding="utf-8",
    )
    append_team_to_local_host(runtime_project, "neu", actor="admin")
    cfg = load_hosts_admin(runtime_project)
    local = next(h for h in cfg.hosts if h.id == "local")
    assert "neu" in local.teams
