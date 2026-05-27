"""SQLite-Chat pro Team (data/<team>/chat.sqlite)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

ChatRole = Literal["user", "assistant", "system", "tool"]


class ChatStoreError(Exception):
    pass


@dataclass
class ChatMessage:
    id: str
    team_id: str
    agent_id: str | None
    role: ChatRole
    content: str
    created_at: datetime
    thread_id: str | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "team_id": self.team_id,
            "agent_id": self.agent_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "thread_id": self.thread_id,
            "metadata": self.metadata,
        }


class ChatStore:
    SCHEMA_VERSION = 1

    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.db_path = self.root / "data" / team_id / "chat.sqlite"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    thread_id TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_agent ON messages(agent_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
                ("version", str(self.SCHEMA_VERSION)),
            )
            conn.commit()

    def add(
        self,
        *,
        role: ChatRole,
        content: str,
        agent_id: str | None = None,
        thread_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        message_id: str | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            id=message_id or str(uuid.uuid4()),
            team_id=self.team_id,
            agent_id=agent_id,
            role=role,
            content=content,
            created_at=datetime.now(UTC),
            thread_id=thread_id,
            metadata=metadata or {},
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (id, agent_id, role, content, created_at, thread_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg.id,
                    msg.agent_id,
                    msg.role,
                    msg.content,
                    msg.created_at.isoformat(),
                    msg.thread_id,
                    json.dumps(msg.metadata, ensure_ascii=False),
                ),
            )
            conn.commit()
        return msg

    def list_messages(
        self,
        *,
        agent_id: str | None = None,
        thread_id: str | None = None,
        search: str | None = None,
        limit: int = 50,
    ) -> list[ChatMessage]:
        query = "SELECT * FROM messages WHERE 1=1"
        params: list[Any] = []
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if thread_id:
            query += " AND thread_id = ?"
            params.append(thread_id)
        if search:
            query += " AND content LIKE ?"
            params.append(f"%{search}%")
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        messages: list[ChatMessage] = []
        for row in rows:
            messages.append(self._row_to_message(row))
        return list(reversed(messages))

    def delete_message(self, message_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear_all(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM messages")
            conn.commit()
            return cur.rowcount

    def _row_to_message(self, row: sqlite3.Row) -> ChatMessage:
        return ChatMessage(
            id=row["id"],
            team_id=self.team_id,
            agent_id=row["agent_id"],
            role=row["role"],  # type: ignore[arg-type]
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            thread_id=row["thread_id"],
            metadata=json.loads(row["metadata"] or "{}"),
        )
