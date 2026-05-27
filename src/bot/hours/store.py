"""SQLite für Öffnungszeiten-Diffs und Publish-Log."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bot.approval.status import ApprovalError, transition_approve, transition_reject


class HoursStoreError(Exception):
    pass


@dataclass
class HoursDiffRecord:
    id: str
    diff_json: dict[str, Any]
    status: str
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime
    published_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "diff": self.diff_json,
            "status": self.status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


class HoursStore:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.db_path = self.root / "data" / team_id / "hours.sqlite"
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
                CREATE TABLE IF NOT EXISTS diffs (
                    id TEXT PRIMARY KEY,
                    diff_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'awaiting_approval',
                    approved_by TEXT,
                    approved_at TEXT,
                    created_at TEXT NOT NULL,
                    published_at TEXT
                )
                """
            )

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def create_diff(self, diff: dict[str, Any]) -> HoursDiffRecord:
        diff_id = str(uuid.uuid4())
        now = self._now()
        status = "awaiting_approval" if diff.get("has_diff") else "no_changes"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO diffs (id, diff_json, status, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (diff_id, json.dumps(diff), status, now.isoformat()),
            )
        record = self.get_diff(diff_id)
        assert record is not None
        return record

    def get_diff(self, diff_id: str) -> HoursDiffRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM diffs WHERE id = ?", (diff_id,)).fetchone()
        return self._row(row) if row else None

    def list_diffs(self, limit: int = 20) -> list[HoursDiffRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM diffs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row(r) for r in rows]

    def approve(self, diff_id: str, approved_by: str) -> HoursDiffRecord:
        record = self.get_diff(diff_id)
        if not record:
            raise HoursStoreError(f"Diff nicht gefunden: {diff_id}")
        try:
            new_status = transition_approve(record.status)
        except ApprovalError as exc:
            raise HoursStoreError(str(exc)) from exc

        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE diffs SET status = ?, approved_by = ?, approved_at = ?
                WHERE id = ?
                """,
                (new_status, approved_by, now.isoformat(), diff_id),
            )
        updated = self.get_diff(diff_id)
        assert updated is not None
        return updated

    def reject(self, diff_id: str) -> HoursDiffRecord:
        record = self.get_diff(diff_id)
        if not record:
            raise HoursStoreError(f"Diff nicht gefunden: {diff_id}")
        try:
            new_status = transition_reject(record.status)
        except ApprovalError as exc:
            raise HoursStoreError(str(exc)) from exc

        with self._connect() as conn:
            conn.execute("UPDATE diffs SET status = ? WHERE id = ?", (new_status, diff_id))
        updated = self.get_diff(diff_id)
        assert updated is not None
        return updated

    def mark_published(self, diff_id: str) -> HoursDiffRecord:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE diffs SET status = 'published', published_at = ?
                WHERE id = ?
                """,
                (now.isoformat(), diff_id),
            )
        updated = self.get_diff(diff_id)
        if not updated:
            raise HoursStoreError(f"Diff nicht gefunden: {diff_id}")
        return updated

    def _row(self, row: sqlite3.Row) -> HoursDiffRecord:
        approved_at = row["approved_at"]
        published_at = row["published_at"]
        return HoursDiffRecord(
            id=row["id"],
            diff_json=json.loads(row["diff_json"]),
            status=row["status"],
            approved_by=row["approved_by"],
            approved_at=datetime.fromisoformat(approved_at) if approved_at else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            published_at=datetime.fromisoformat(published_at) if published_at else None,
        )
