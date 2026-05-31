"""Spiegelt Agent-Inbox-Verkehr in chat.sqlite (Team-Feed)."""

from __future__ import annotations

from pathlib import Path

from bot.chat import ChatStore
from bot.config import load_runtime_config
from bot.messages.models import Message


def mirror_agent_message_to_chat(root: Path, team_id: str, msg: Message) -> None:
    if msg.type in ("chat.user", "chat.approve"):
        return
    if msg.type == "chat.direct":
        return

    try:
        orch_id = load_runtime_config(root).teams[team_id].team.team.orchestrator_id
    except Exception:
        orch_id = ""

    indent = 1 if msg.from_agent == orch_id or msg.to_agent == orch_id else 2
    preview = msg.content.strip()
    if len(preview) > 4000:
        preview = preview[:4000] + "\n…"
    body = f"{msg.from_agent} → {msg.to_agent}\nBetreff: {msg.subject}\n\n{preview}"

    store = ChatStore(root, team_id)
    chat_id = f"internal-{msg.id}"
    existing = store.list_messages(limit=500)
    if any(m.id == chat_id for m in existing):
        return

    store.add(
        role="system",
        content=body,
        agent_id=msg.from_agent,
        message_id=chat_id,
        metadata={
            "channel": "internal",
            "indent": indent,
            "from_agent": msg.from_agent,
            "to_agent": msg.to_agent,
            "msg_type": msg.type,
            "status": msg.status,
            "internal_message_id": msg.id,
        },
    )
