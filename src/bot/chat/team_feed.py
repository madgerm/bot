"""Kombinierter Chat-Feed: Panel + Agent-Inbox/Outbox (eingerückt)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from bot.chat.store import ChatMessage, ChatStore
from bot.config import load_runtime_config
from bot.messages.mailbox import Mailbox
from bot.messages.models import Message


@dataclass
class FeedLine:
    id: str
    kind: str  # panel | internal
    indent: int
    created_at: datetime
    label: str
    content: str
    metadata: dict[str, Any]
    panel_message_id: str | None = None
    awaiting_approval: bool = False

    @property
    def css_indent(self) -> str:
        if self.indent <= 0:
            return ""
        return "ml-" + str(min(self.indent * 6, 12))


def _skip_internal(msg: Message, orch_id: str) -> bool:
    """Panel-Orchestrator-Self-Messages nicht doppelt anzeigen."""
    if msg.type in ("chat.user", "chat.approve") and msg.from_agent == orch_id and msg.to_agent == orch_id:
        return True
    return False


def collect_agent_messages(root: Path, team_id: str) -> list[Message]:
    cfg = load_runtime_config(root)
    if team_id not in cfg.teams:
        return []
    template = cfg.system.system.communication.inbox_base
    seen: set[str] = set()
    rows: list[Message] = []
    for agent_id in cfg.teams[team_id].agents:
        mailbox = Mailbox(root, team_id, agent_id, template)
        for msg in mailbox.list_messages():
            if msg.id in seen:
                continue
            seen.add(msg.id)
            rows.append(msg)
    return sorted(rows, key=lambda m: m.created_at)


def _internal_indent(msg: Message, orch_id: str) -> int:
    if msg.from_agent == orch_id or msg.to_agent == orch_id:
        return 1
    return 2


def _line_from_internal(msg: Message, orch_id: str) -> FeedLine:
    indent = _internal_indent(msg, orch_id)
    status = msg.status
    label = f"{msg.from_agent} → {msg.to_agent} · {msg.type} · {status}"
    body = f"{msg.subject}\n\n{msg.content}"
    if len(body) > 8000:
        body = body[:8000] + "\n…"
    return FeedLine(
        id=f"internal-{msg.id}",
        kind="internal",
        indent=indent,
        created_at=msg.created_at,
        label=label,
        content=body,
        metadata={
            "from_agent": msg.from_agent,
            "to_agent": msg.to_agent,
            "msg_type": msg.type,
            "status": status,
        },
    )


def _is_direct_panel_message(msg: ChatMessage, direct_agent: str) -> bool:
    if msg.metadata.get("channel") != "direct":
        return False
    if msg.metadata.get("direct_peer") == direct_agent:
        return True
    return msg.agent_id == direct_agent


def _line_from_panel(msg: ChatMessage) -> FeedLine:
    who = msg.agent_id or msg.role
    if msg.metadata.get("channel") == "direct":
        if msg.role == "assistant":
            who = msg.agent_id or "Agent"
        elif msg.metadata.get("username"):
            who = str(msg.metadata["username"])
        elif msg.metadata.get("direct_peer"):
            who = f"Du → {msg.metadata['direct_peer']}"
    elif msg.metadata.get("username"):
        who = str(msg.metadata["username"])
    elif msg.metadata.get("direct_peer"):
        who = f"Du → {msg.metadata['direct_peer']}"
    label = f"{who} · {msg.role}"
    if msg.metadata.get("channel") == "internal":
        label = msg.metadata.get("from_agent", "") + " → " + msg.metadata.get("to_agent", "")
    return FeedLine(
        id=msg.id,
        kind="panel" if msg.metadata.get("channel") != "internal" else "internal",
        indent=int(msg.metadata.get("indent", 0)),
        created_at=msg.created_at,
        label=label,
        content=msg.content,
        metadata=dict(msg.metadata),
        panel_message_id=msg.id if msg.metadata.get("channel") != "internal" else None,
        awaiting_approval=bool(msg.metadata.get("awaiting_approval")),
    )


def build_team_feed(
    root: Path,
    team_id: str,
    orch_id: str,
    *,
    direct_agent: str | None = None,
    include_internal: bool = True,
    limit: int = 400,
) -> list[FeedLine]:
    """Panel-Verlauf mit eingerückten Agent-Messages zwischen den Panel-Events."""
    store = ChatStore(root, team_id)
    if direct_agent:
        panel_msgs = [
            m
            for m in store.list_messages(limit=limit)
            if _is_direct_panel_message(m, direct_agent)
        ]
        internal: list[Message] = []
    else:
        panel_msgs = [
            m
            for m in store.list_messages(limit=limit)
            if m.metadata.get("channel") != "internal"
            and not m.metadata.get("direct_peer")
        ]
        internal = (
            [
                m
                for m in collect_agent_messages(root, team_id)
                if not _skip_internal(m, orch_id)
            ]
            if include_internal
            else []
        )

    panel_msgs = sorted(panel_msgs, key=lambda m: m.created_at)
    internal = sorted(internal, key=lambda m: m.created_at)

    if direct_agent or not include_internal:
        return [_line_from_panel(m) for m in panel_msgs][-limit:]

    lines: list[FeedLine] = []
    int_idx = 0
    for i, panel in enumerate(panel_msgs):
        lines.append(_line_from_panel(panel))
        t_start = panel.created_at
        t_end = panel_msgs[i + 1].created_at if i + 1 < len(panel_msgs) else None
        while int_idx < len(internal):
            im = internal[int_idx]
            if im.created_at < t_start:
                int_idx += 1
                continue
            if t_end is not None and im.created_at >= t_end:
                break
            lines.append(_line_from_internal(im, orch_id))
            int_idx += 1

    while int_idx < len(internal):
        lines.append(_line_from_internal(internal[int_idx], orch_id))
        int_idx += 1

    return lines[-limit:]
