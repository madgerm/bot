"""SQLite-Speicher für E-Mail-Threads und Entwürfe."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bot.approval.status import (
    ApprovalError,
    transition_approve,
    transition_reject,
    transition_submit_for_approval,
)


class MailStoreError(Exception):
    pass


@dataclass
class EmailThread:
    id: str
    team_id: str
    subject: str
    from_addr: str
    received_at: datetime
    status: str
    imap_uid: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "team_id": self.team_id,
            "subject": self.subject,
            "from_addr": self.from_addr,
            "received_at": self.received_at.isoformat(),
            "status": self.status,
            "imap_uid": self.imap_uid,
        }


@dataclass
class EmailDraft:
    id: str
    thread_id: str
    version: int
    subject: str
    body_text: str
    to_addrs: list[str]
    status: str
    created_by: str | None
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "version": self.version,
            "subject": self.subject,
            "body_text": self.body_text,
            "to_addrs": self.to_addrs,
            "status": self.status,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class IncomingEmail:
    id: str
    thread_id: str
    body_text: str
    received_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "body_text": self.body_text,
            "received_at": self.received_at.isoformat(),
        }


class MailStore:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.db_path = self.root / "data" / team_id / "email.sqlite"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    from_addr TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    imap_uid TEXT UNIQUE
                );
                CREATE TABLE IF NOT EXISTS incoming (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    body_text TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    FOREIGN KEY (thread_id) REFERENCES threads(id)
                );
                CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    subject TEXT NOT NULL,
                    body_text TEXT NOT NULL,
                    to_addrs TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_by TEXT,
                    approved_by TEXT,
                    approved_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (thread_id) REFERENCES threads(id)
                );
                """
            )

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def add_thread(
        self,
        *,
        subject: str,
        from_addr: str,
        body_text: str,
        imap_uid: str | None = None,
        received_at: datetime | None = None,
    ) -> EmailThread:
        if imap_uid and self.thread_by_imap_uid(imap_uid):
            existing = self.thread_by_imap_uid(imap_uid)
            assert existing is not None
            return existing

        now = received_at or self._now()
        thread_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO threads (id, subject, from_addr, received_at, status, imap_uid)
                VALUES (?, ?, ?, ?, 'open', ?)
                """,
                (thread_id, subject, from_addr, now.isoformat(), imap_uid),
            )
            conn.execute(
                """
                INSERT INTO incoming (id, thread_id, body_text, received_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), thread_id, body_text, now.isoformat()),
            )
        return EmailThread(
            id=thread_id,
            team_id=self.team_id,
            subject=subject,
            from_addr=from_addr,
            received_at=now,
            status="open",
            imap_uid=imap_uid,
        )

    def thread_by_imap_uid(self, imap_uid: str) -> EmailThread | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM threads WHERE imap_uid = ?", (imap_uid,)
            ).fetchone()
        return self._row_thread(row) if row else None

    def get_thread(self, thread_id: str) -> EmailThread | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
        return self._row_thread(row) if row else None

    def list_threads(self, limit: int = 50) -> list[EmailThread]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM threads ORDER BY received_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_thread(r) for r in rows]

    def get_incoming(self, thread_id: str) -> IncomingEmail | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM incoming WHERE thread_id = ? ORDER BY received_at DESC LIMIT 1",
                (thread_id,),
            ).fetchone()
        if not row:
            return None
        return IncomingEmail(
            id=row["id"],
            thread_id=row["thread_id"],
            body_text=row["body_text"],
            received_at=datetime.fromisoformat(row["received_at"]),
        )

    def create_draft(
        self,
        *,
        thread_id: str,
        subject: str,
        body_text: str,
        to_addrs: list[str],
        created_by: str | None = None,
        submit: bool = True,
    ) -> EmailDraft:
        if not self.get_thread(thread_id):
            raise MailStoreError(f"Thread nicht gefunden: {thread_id}")

        now = self._now()
        draft_id = str(uuid.uuid4())
        status = (
            transition_submit_for_approval("draft") if submit else "draft"
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO drafts (
                    id, thread_id, version, subject, body_text, to_addrs,
                    status, created_by, created_at, updated_at
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    thread_id,
                    subject,
                    body_text,
                    json.dumps(to_addrs),
                    status,
                    created_by,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        draft = self.get_draft(draft_id)
        assert draft is not None
        return draft

    def get_draft(self, draft_id: str) -> EmailDraft | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        return self._row_draft(row) if row else None

    def list_drafts(
        self,
        *,
        status: str | None = None,
        thread_id: str | None = None,
        limit: int = 50,
    ) -> list[EmailDraft]:
        query = "SELECT * FROM drafts WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if thread_id:
            query += " AND thread_id = ?"
            params.append(thread_id)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_draft(r) for r in rows]

    def approve_draft(self, draft_id: str, approved_by: str) -> EmailDraft:
        draft = self.get_draft(draft_id)
        if not draft:
            raise MailStoreError(f"Entwurf nicht gefunden: {draft_id}")
        try:
            new_status = transition_approve(draft.status)
        except ApprovalError as exc:
            raise MailStoreError(str(exc)) from exc

        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE drafts SET status = ?, approved_by = ?, approved_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_status, approved_by, now.isoformat(), now.isoformat(), draft_id),
            )
        updated = self.get_draft(draft_id)
        assert updated is not None
        return updated

    def reject_draft(self, draft_id: str) -> EmailDraft:
        draft = self.get_draft(draft_id)
        if not draft:
            raise MailStoreError(f"Entwurf nicht gefunden: {draft_id}")
        try:
            new_status = transition_reject(draft.status)
        except ApprovalError as exc:
            raise MailStoreError(str(exc)) from exc

        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE drafts SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now.isoformat(), draft_id),
            )
        updated = self.get_draft(draft_id)
        assert updated is not None
        return updated

    def mark_draft_sent(self, draft_id: str) -> EmailDraft:
        draft = self.get_draft(draft_id)
        if not draft:
            raise MailStoreError(f"Entwurf nicht gefunden: {draft_id}")
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE drafts SET status = 'sent', updated_at = ? WHERE id = ?",
                (now.isoformat(), draft_id),
            )
        updated = self.get_draft(draft_id)
        assert updated is not None
        return updated

    def mark_draft_failed(self, draft_id: str) -> EmailDraft:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE drafts SET status = 'failed', updated_at = ? WHERE id = ?",
                (now.isoformat(), draft_id),
            )
        updated = self.get_draft(draft_id)
        if not updated:
            raise MailStoreError(f"Entwurf nicht gefunden: {draft_id}")
        return updated

    def _row_thread(self, row: sqlite3.Row) -> EmailThread:
        return EmailThread(
            id=row["id"],
            team_id=self.team_id,
            subject=row["subject"],
            from_addr=row["from_addr"],
            received_at=datetime.fromisoformat(row["received_at"]),
            status=row["status"],
            imap_uid=row["imap_uid"],
        )

    def _row_draft(self, row: sqlite3.Row) -> EmailDraft:
        approved_at = row["approved_at"]
        return EmailDraft(
            id=row["id"],
            thread_id=row["thread_id"],
            version=row["version"],
            subject=row["subject"],
            body_text=row["body_text"],
            to_addrs=json.loads(row["to_addrs"]),
            status=row["status"],
            created_by=row["created_by"],
            approved_by=row["approved_by"],
            approved_at=datetime.fromisoformat(approved_at) if approved_at else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
