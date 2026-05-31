"""Persistente LLM-Warteschlange (Runner) — überlebt Verbindungsabbrüche."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path


class ChannelQueueError(Exception):
    pass


class LlmChannelQueue:
    """SQLite-Queue: Agents (bot run) schreiben, Relay (team serve) + Panel liefern."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        self._dir = self._root / "data" / "_channel"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._db = self._dir / "llm_queue.sqlite"
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS llm_requests (
                        id TEXT PRIMARY KEY,
                        model TEXT NOT NULL,
                        messages_json TEXT NOT NULL,
                        fallbacks_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        response TEXT,
                        error TEXT,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_llm_status ON llm_requests(status)"
                )
                conn.commit()
            finally:
                conn.close()

    def enqueue(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        fallbacks: list[str] | None,
    ) -> str:
        req_id = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO llm_requests
                    (id, model, messages_json, fallbacks_json, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        req_id,
                        model,
                        json.dumps(messages, ensure_ascii=False),
                        json.dumps(fallbacks or [], ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return req_id

    def list_pending(self, limit: int = 50) -> list[dict]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT * FROM llm_requests
                    WHERE status IN ('pending', 'sent')
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [self._row_to_payload(row) for row in rows]
            finally:
                conn.close()

    def mark_sent(self, req_id: str) -> None:
        self._set_status(req_id, "sent")

    def complete(self, req_id: str, content: str) -> None:
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE llm_requests
                    SET status='completed', response=?, error=NULL, updated_at=?
                    WHERE id=?
                    """,
                    (content, now, req_id),
                )
                conn.commit()
            finally:
                conn.close()

    def fail(self, req_id: str, error: str) -> None:
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE llm_requests
                    SET status='failed', error=?, updated_at=?
                    WHERE id=?
                    """,
                    (error, now, req_id),
                )
                conn.commit()
            finally:
                conn.close()

    def wait_for_result(self, req_id: str, *, timeout_seconds: float) -> str:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            row = self._get(req_id)
            if row is None:
                raise ChannelQueueError(f"Unbekannte Anfrage {req_id}")
            status = row["status"]
            if status == "completed":
                if not row["response"]:
                    raise ChannelQueueError("Leere LLM-Antwort in Queue")
                return str(row["response"])
            if status == "failed":
                raise ChannelQueueError(row["error"] or "LLM fehlgeschlagen")
            time.sleep(0.25)
        raise ChannelQueueError(
            f"Timeout ({timeout_seconds}s) — Panel-Kanal nicht verbunden oder Ollama zu langsam?"
        )

    def _get(self, req_id: str) -> sqlite3.Row | None:
        with self._lock:
            conn = self._connect()
            try:
                return conn.execute(
                    "SELECT * FROM llm_requests WHERE id=?", (req_id,)
                ).fetchone()
            finally:
                conn.close()

    def _set_status(self, req_id: str, status: str) -> None:
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE llm_requests SET status=?, updated_at=? WHERE id=?",
                    (status, now, req_id),
                )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _row_to_payload(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "model": row["model"],
            "messages": json.loads(row["messages_json"]),
            "fallbacks": json.loads(row["fallbacks_json"]),
        }
