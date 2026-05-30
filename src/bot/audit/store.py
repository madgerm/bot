"""Zentrales Audit-Log (SQLite) für Panel-Aktionen."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class AuditEntry:
    id: str
    category: str
    action: str
    actor: str
    team_id: str | None
    details: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "action": self.action,
            "actor": self.actor,
            "team_id": self.team_id,
            "details": self.details,
            "created_at": self.created_at,
        }


class AuditStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.path = self.root / "data" / "audit.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    team_id TEXT,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC)"
            )
            conn.commit()

    def log(
        self,
        *,
        category: str,
        action: str,
        actor: str,
        team_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            id=str(uuid4()),
            category=category,
            action=action,
            actor=actor,
            team_id=team_id,
            details=details or {},
            created_at=datetime.now(UTC).isoformat(),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (id, category, action, actor, team_id, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.category,
                    entry.action,
                    entry.actor,
                    entry.team_id,
                    json.dumps(entry.details, ensure_ascii=False),
                    entry.created_at,
                ),
            )
            conn.commit()
        return entry

    def list_entries(
        self,
        *,
        limit: int = 100,
        team_id: str | None = None,
        category: str | None = None,
    ) -> list[AuditEntry]:
        query = "SELECT * FROM audit_log WHERE 1=1"
        params: list[Any] = []
        if team_id:
            query += " AND team_id = ?"
            params.append(team_id)
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        entries: list[AuditEntry] = []
        for row in rows:
            entries.append(
                AuditEntry(
                    id=row["id"],
                    category=row["category"],
                    action=row["action"],
                    actor=row["actor"],
                    team_id=row["team_id"],
                    details=json.loads(row["details"]),
                    created_at=row["created_at"],
                )
            )
        return entries
