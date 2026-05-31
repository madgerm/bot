"""Lesen/Schreiben von teams/<id>/team.json (Panel)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from bot.config.models import PipelineConfig, TeamConfig
from bot.config.writers import (
    ConfigWriterError,
    atomic_write_json,
    load_json_file,
    relative_config_path,
)
from bot.config.writers.audit import log_config_change


class TeamAdminError(ConfigWriterError):
    pass


def team_json_path(root: Path, team_id: str) -> Path:
    return root / "teams" / team_id / "team.json"


def load_team_config(root: Path, team_id: str) -> TeamConfig:
    path = team_json_path(root, team_id)
    try:
        data = load_json_file(path)
        return TeamConfig.model_validate(data)
    except ValidationError as exc:
        raise TeamAdminError(str(exc)) from exc


def save_team_config(
    root: Path,
    team_id: str,
    cfg: TeamConfig,
    *,
    actor: str,
    section: str,
) -> None:
    if cfg.team.id != team_id:
        raise TeamAdminError("team.id muss dem Ordnernamen entsprechen")
    agent_ids = set(list_agent_ids(root, team_id))
    if cfg.team.orchestrator_id not in agent_ids:
        raise TeamAdminError(
            f"Orchestrator '{cfg.team.orchestrator_id}' existiert nicht im Team"
        )
    if cfg.pipeline:
        for label, aid in (
            ("execute", cfg.pipeline.execute),
            ("review", cfg.pipeline.review),
            ("document", cfg.pipeline.document),
        ):
            if aid and aid not in agent_ids:
                raise TeamAdminError(f"Pipeline {label}: Agent '{aid}' fehlt")

    path = team_json_path(root, team_id)
    atomic_write_json(path, cfg.model_dump(mode="json", exclude_none=True))
    log_config_change(
        root,
        actor=actor,
        config_path=relative_config_path(root, path),
        action=f"team_{section}",
        team_id=team_id,
        details={"section": section},
    )


def save_team_general(
    root: Path,
    team_id: str,
    *,
    actor: str,
    name: str,
    enabled: bool,
    preset: Literal["generic", "demo", "coding", "story"],
    orchestrator_id: str,
    workflow: Literal["tasks", "verification"] = "tasks",
) -> TeamConfig:
    cfg = load_team_config(root, team_id)
    team = cfg.team.model_copy(
        update={
            "name": name.strip(),
            "enabled": enabled,
            "preset": preset,
            "orchestrator_id": orchestrator_id.strip(),
            "workflow": workflow,
        }
    )
    new_cfg = cfg.model_copy(update={"team": team})
    save_team_config(root, team_id, new_cfg, actor=actor, section="general")
    return new_cfg


def save_team_pipeline(
    root: Path,
    team_id: str,
    *,
    actor: str,
    execute: str,
    review: str,
    document: str,
) -> TeamConfig:
    cfg = load_team_config(root, team_id)
    pipe = PipelineConfig(
        execute=execute.strip() or None,
        review=review.strip() or None,
        document=document.strip() or None,
    )
    new_cfg = cfg.model_copy(update={"pipeline": pipe})
    save_team_config(root, team_id, new_cfg, actor=actor, section="pipeline")
    return new_cfg


_TEAM_ID_RE = __import__("re").compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")


def validate_team_id(team_id: str) -> str:
    tid = team_id.strip().lower()
    if not tid or not _TEAM_ID_RE.match(tid):
        raise TeamAdminError(
            "Team-ID: 1–63 Zeichen, Buchstaben/Ziffern, - und _ (kein Leerzeichen)"
        )
    return tid


def create_team(
    root: Path,
    team_id: str,
    *,
    actor: str,
    name: str,
    preset: Literal["generic", "demo", "coding", "story"] = "generic",
    workflow: Literal["tasks", "verification"] = "tasks",
) -> TeamConfig:
    """Neues Team in teams/<id>/ anlegen (Standard-Agents)."""
    from bot.config.models import TeamBlock
    from bot.agents_mgmt import AgentManager

    tid = validate_team_id(team_id)
    team_dir = root / "teams" / tid
    if team_dir.exists():
        raise TeamAdminError(f"Team '{tid}' existiert bereits")

    display_name = name.strip() or tid
    team_dir.mkdir(parents=True)
    orch_id = "orchestrator"
    cfg = TeamConfig(
        team=TeamBlock(
            id=tid,
            name=display_name,
            orchestrator_id=orch_id,
            enabled=True,
            preset=preset,
            workflow=workflow,
        ),
        pipeline=None,
    )
    atomic_write_json(
        team_json_path(root, tid),
        cfg.model_dump(mode="json", exclude_none=True),
    )

    mgr = AgentManager(root)
    mgr.create_agent(tid, agent_id=orch_id, role="orchestrator", display_name="Orchestrator")
    mgr.create_agent(tid, agent_id="worker-exec", role="worker", display_name="Ausführung")
    mgr.create_agent(tid, agent_id="worker-review", role="reviewer", display_name="Review")

    log_config_change(
        root,
        actor=actor,
        config_path=relative_config_path(root, team_json_path(root, tid)),
        action="team_create",
        team_id=tid,
        details={"name": display_name, "preset": preset},
    )
    return cfg


def save_team_name(root: Path, team_id: str, *, actor: str, name: str) -> TeamConfig:
    """Nur Anzeigename ändern (team.json)."""
    cfg = load_team_config(root, team_id)
    team = cfg.team.model_copy(update={"name": name.strip() or team_id})
    new_cfg = cfg.model_copy(update={"team": team})
    save_team_config(root, team_id, new_cfg, actor=actor, section="rename")
    return new_cfg


def list_agent_ids(root: Path, team_id: str) -> list[str]:
    agents_dir = root / "teams" / team_id / "agents"
    if not agents_dir.is_dir():
        return []
    return sorted(
        p.name for p in agents_dir.iterdir() if p.is_dir() and (p / "agent.json").is_file()
    )
