"""Panel-Chat ↔ Orchestrator-Inbox."""

from __future__ import annotations

from pathlib import Path

from bot.config import load_runtime_config
from bot.messages import MessageError, open_message_service
from bot.messages.models import Message


def orchestrator_id(root: Path, team_id: str) -> str:
    cfg = load_runtime_config(root)
    if team_id not in cfg.teams:
        raise MessageError(f"Team '{team_id}' nicht gefunden")
    return cfg.teams[team_id].team.team.orchestrator_id


def enqueue_panel_chat(
    root: Path,
    team_id: str,
    *,
    username: str,
    content: str,
    message_type: str = "chat.user",
    subject: str | None = None,
) -> Message:
    """Leitet eine Panel-Nachricht an den Orchestrator weiter (bot run erforderlich)."""
    orch = orchestrator_id(root, team_id)
    svc = open_message_service(root)
    subj = subject or f"Chat ({username})"
    body = content.strip()
    if message_type == "chat.user" and not body.startswith("["):
        body = f"[{username}]\n{body}"
    return svc.send(
        team_id=team_id,
        from_agent=orch,
        to_agent=orch,
        subject=subj,
        content=body,
        type=message_type,
        task_category="planning",
    )


def format_chat_context(root: Path, team_id: str, *, limit: int = 30) -> str:
    from bot.chat import ChatStore

    rows = ChatStore(root, team_id).list_messages(limit=limit)
    if not rows:
        return "(kein Verlauf)"
    lines: list[str] = []
    for msg in reversed(rows):
        who = msg.agent_id or msg.role
        lines.append(f"{who}: {msg.content}")
    return "\n".join(lines)
