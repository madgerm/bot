"""Direkt-PM: Verlauf im Panel und Antworten der Agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bot.chat import ChatStore

DIRECT_CHANNEL = "direct"


def direct_metadata(*, agent_id: str, **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"channel": DIRECT_CHANNEL, "direct_peer": agent_id}
    base.update(extra)
    return base


def direct_messages_for_agent(
    root: Path, team_id: str, agent_id: str, *, limit: int = 80
) -> list:
    rows = [
        m
        for m in ChatStore(root, team_id).list_messages(limit=limit * 3)
        if m.metadata.get("channel") == DIRECT_CHANNEL
        and (
            m.metadata.get("direct_peer") == agent_id
            or m.agent_id == agent_id
        )
    ]
    return sorted(rows, key=lambda m: m.created_at)[-limit:]


def format_direct_context(root: Path, team_id: str, agent_id: str, *, limit: int = 30) -> str:
    rows = direct_messages_for_agent(root, team_id, agent_id, limit=limit)
    if not rows:
        return "(kein Verlauf)"
    lines: list[str] = []
    for msg in rows:
        if msg.role == "user":
            who = msg.metadata.get("username") or "Nutzer"
        else:
            who = msg.agent_id or msg.role
        lines.append(f"{who}: {msg.content}")
    return "\n".join(lines)


def record_direct_assistant(
    root: Path,
    team_id: str,
    agent_id: str,
    content: str,
    *,
    internal_message_id: str | None = None,
) -> None:
    meta = direct_metadata(agent_id=agent_id)
    if internal_message_id:
        meta["internal_message_id"] = internal_message_id
    ChatStore(root, team_id).add(
        role="assistant",
        content=content.strip(),
        agent_id=agent_id,
        metadata=meta,
    )
