"""SQLite-Speicher für Prüffragen und Team-Laufzustand."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from bot.verification.models import (
    CheckMethod,
    QuestionStatus,
    Verdict,
    VerificationQuestion,
)


class VerificationStore:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.db_path = self.root / "data" / team_id / "verification.sqlite"
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
                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY,
                    seq INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    question TEXT NOT NULL,
                    expectation TEXT NOT NULL DEFAULT '',
                    check_method TEXT NOT NULL DEFAULT 'code',
                    success_criteria TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    verdict TEXT,
                    evidence TEXT NOT NULL DEFAULT '',
                    review_notes TEXT NOT NULL DEFAULT '',
                    fix_notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vq_status ON questions(status)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def _row(self, row: sqlite3.Row) -> VerificationQuestion:
        return VerificationQuestion(
            id=row["id"],
            team_id=self.team_id,
            seq=row["seq"],
            title=row["title"],
            question=row["question"],
            expectation=row["expectation"],
            check_method=row["check_method"],  # type: ignore[arg-type]
            success_criteria=row["success_criteria"],
            status=row["status"],  # type: ignore[arg-type]
            verdict=row["verdict"],  # type: ignore[arg-type]
            evidence=row["evidence"],
            review_notes=row["review_notes"],
            fix_notes=row["fix_notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_questions(self, *, status: QuestionStatus | None = None) -> list[VerificationQuestion]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM questions WHERE status = ? ORDER BY seq",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM questions ORDER BY seq").fetchall()
        return [self._row(r) for r in rows]

    def get_question(self, question_id: str) -> VerificationQuestion | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM questions WHERE id = ?", (question_id,)
            ).fetchone()
        return self._row(row) if row else None

    def add_question(
        self,
        *,
        seq: int,
        title: str,
        question: str,
        expectation: str = "",
        check_method: CheckMethod = "code",
        success_criteria: str = "",
    ) -> VerificationQuestion:
        now = datetime.now(UTC)
        qid = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO questions (
                    id, seq, title, question, expectation, check_method,
                    success_criteria, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (
                    qid,
                    seq,
                    title,
                    question,
                    expectation,
                    check_method,
                    success_criteria,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        q = self.get_question(qid)
        assert q is not None
        self._sync_files()
        return q

    def update_question(
        self,
        question_id: str,
        **fields: str | None,
    ) -> VerificationQuestion | None:
        allowed = {
            "title",
            "question",
            "expectation",
            "check_method",
            "success_criteria",
            "status",
            "verdict",
            "evidence",
            "review_notes",
            "fix_notes",
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return self.get_question(question_id)
        updates["updated_at"] = datetime.now(UTC).isoformat()
        cols = ", ".join(f"{k} = ?" for k in updates)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE questions SET {cols} WHERE id = ?",
                (*updates.values(), question_id),
            )
        self._sync_files()
        return self.get_question(question_id)

    def clear_questions(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM questions")
            conn.execute("DELETE FROM state")
        self._sync_files()
        return cur.rowcount

    def next_open_question(self) -> VerificationQuestion | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM questions
                WHERE status IN ('open', 'fixing')
                ORDER BY seq LIMIT 1
                """
            ).fetchone()
        return self._row(row) if row else None

    def set_state(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO state (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_state(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM state WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def summary(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM questions GROUP BY status"
            ).fetchall()
        out: dict[str, int] = {}
        for r in rows:
            out[r["status"]] = r["c"]
        return out

    def _sync_files(self) -> None:
        from bot.verification.files import sync_verification_files

        sync_verification_files(self.root, self.team_id, self.list_questions())
