"""Direktnachricht von Panel-Nutzer an einen Agent."""

from __future__ import annotations

from pathlib import Path

from bot.chat import ChatStore
from bot.chat.orchestrator_bridge import orchestrator_id
from bot.messages import MessageError, open_message_service
from bot.messages.models import Message


def send_direct_to_agent(
    root: Path,
    team_id: str,
    *,
    username: str,
    target_agent: str,
    content: str,
) -> Message:
    orch = orchestrator_id(root, team_id)
    svc = open_message_service(root)
    body = f"[Direkt-PM von {username}]\n{content.strip()}"
    msg = svc.send(
        team_id=team_id,
        from_agent=orch,
        to_agent=target_agent,
        subject=f"PM: {username}",
        content=body,
        type="chat.direct",
        task_category="planning",
    )
    ChatStore(root, team_id).add(
        role="user",
        content=content.strip(),
        agent_id=target_agent,
        metadata={
            "username": username,
            "direct_peer": target_agent,
            "channel": "direct",
            "internal_message_id": msg.id,
        },
    )
    return msg


def list_direct_agents(root: Path, team_id: str) -> list[dict[str, str]]:
    from bot.config import load_runtime_config

    cfg = load_runtime_config(root)
    if team_id not in cfg.teams:
        return []
    orch = cfg.teams[team_id].team.team.orchestrator_id
    rows = []
    for aid, bundle in cfg.teams[team_id].agents.items():
        if aid == orch:
            continue
        block = bundle.agent
        rows.append(
            {
                "id": aid,
                "role": block.role,
                "display_name": block.display_name or aid,
            }
        )
    return sorted(rows, key=lambda r: r["id"])
