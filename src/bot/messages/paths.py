"""Pfad-Auflösung für Inbox/Outbox pro Agent."""

from __future__ import annotations

from pathlib import Path


def resolve_agent_path(template: str, *, root: Path, team_id: str, agent_id: str) -> Path:
    relative = template.format(team_id=team_id, agent_id=agent_id)
    return (root / relative).resolve()


def agent_inbox(root: Path, team_id: str, agent_id: str, inbox_template: str) -> Path:
    return resolve_agent_path(inbox_template, root=root, team_id=team_id, agent_id=agent_id)


def agent_outbox(root: Path, team_id: str, agent_id: str, inbox_template: str) -> Path:
    if "{agent_id}" not in inbox_template or "{team_id}" not in inbox_template:
        raise ValueError("inbox_base muss {team_id} und {agent_id} enthalten")
    outbox_template = inbox_template.replace("/inbox", "/outbox", 1)
    if outbox_template == inbox_template:
        outbox_template = inbox_template.rstrip("/") + "/../outbox"
    return resolve_agent_path(outbox_template, root=root, team_id=team_id, agent_id=agent_id)
