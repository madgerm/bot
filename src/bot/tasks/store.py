"""Task-Board SQLite (data/<team>/tasks.sqlite)."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

TaskStatus = Literal["todo", "in_progress", "done", "cancelled"]


class TaskStoreError(Exception):
    pass


@dataclass
class TaskRecord:
    id: str
    team_id: str
    title: str
    description: str
    status: TaskStatus
    assignee_agent: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "team_id": self.team_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "assignee_agent": self.assignee_agent,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class TaskStore:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.db_path = self.root / "data" / team_id / "tasks.sqlite"
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
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'todo',
                    assignee_agent TEXT,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
            )

    def _row_to_record(self, row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            team_id=self.team_id,
            title=row["title"],
            description=row["description"],
            status=row["status"],  # type: ignore[arg-type]
            assignee_agent=row["assignee_agent"],
            created_by=row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def create(
        self,
        *,
        title: str,
        description: str = "",
        assignee_agent: str | None = None,
        created_by: str | None = None,
        status: TaskStatus = "todo",
    ) -> TaskRecord:
        now = datetime.now(UTC)
        task_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, title, description, status, assignee_agent,
                                   created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    title,
                    description,
                    status,
                    assignee_agent,
                    created_by,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.get(task_id)  # type: ignore[return-value]

    def get(self, task_id: str) -> TaskRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def list_tasks(
        self, *, status: TaskStatus | None = None, limit: int = 100
    ) -> list[TaskRecord]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def update(
        self,
        task_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        status: TaskStatus | None = None,
        assignee_agent: str | None = None,
    ) -> TaskRecord:
        existing = self.get(task_id)
        if not existing:
            raise TaskStoreError(f"Task '{task_id}' nicht gefunden")
        now = datetime.now(UTC)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks SET
                    title = COALESCE(?, title),
                    description = COALESCE(?, description),
                    status = COALESCE(?, status),
                    assignee_agent = COALESCE(?, assignee_agent),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    title,
                    description,
                    status,
                    assignee_agent,
                    now.isoformat(),
                    task_id,
                ),
            )
        return self.get(task_id)  # type: ignore[return-value]

    def delete(self, task_id: str) -> None:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            if cur.rowcount == 0:
                raise TaskStoreError(f"Task '{task_id}' nicht gefunden")
