"""Persistente RPC-Queue (Qdrant, Medien, …) — gleiches Prinzip wie LLM-Kanal."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class ChannelRpcQueueError(Exception):
    pass


class ChannelRpcQueue:
    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        self._dir = self._root / "data" / "_channel"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._db = self._dir / "rpc_queue.sqlite"
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
                    CREATE TABLE IF NOT EXISTS rpc_requests (
                        id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        response_json TEXT,
                        error TEXT,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rpc_status ON rpc_requests(status)"
                )
                conn.commit()
            finally:
                conn.close()

    def enqueue(self, kind: str, payload: dict[str, Any]) -> str:
        req_id = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO rpc_requests
                    (id, kind, payload_json, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'pending', ?, ?)
                    """,
                    (req_id, kind, json.dumps(payload, ensure_ascii=False), now, now),
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
                    SELECT * FROM rpc_requests
                    WHERE status IN ('pending', 'sent')
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [
                    {
                        "id": row["id"],
                        "kind": row["kind"],
                        "payload": json.loads(row["payload_json"]),
                    }
                    for row in rows
                ]
            finally:
                conn.close()

    def mark_sent(self, req_id: str) -> None:
        self._set_status(req_id, "sent")

    def complete(self, req_id: str, result: dict[str, Any]) -> None:
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    UPDATE rpc_requests
                    SET status='completed', response_json=?, error=NULL, updated_at=?
                    WHERE id=?
                    """,
                    (json.dumps(result, ensure_ascii=False), now, req_id),
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
                    UPDATE rpc_requests
                    SET status='failed', error=?, updated_at=?
                    WHERE id=?
                    """,
                    (error, now, req_id),
                )
                conn.commit()
            finally:
                conn.close()

    def wait_for_result(
        self, req_id: str, *, timeout_seconds: float
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            row = self._get(req_id)
            if row is None:
                raise ChannelRpcQueueError(f"Unbekannte RPC {req_id}")
            status = row["status"]
            if status == "completed":
                if not row["response_json"]:
                    raise ChannelRpcQueueError("Leere RPC-Antwort")
                return json.loads(row["response_json"])
            if status == "failed":
                raise ChannelRpcQueueError(row["error"] or "RPC fehlgeschlagen")
            time.sleep(0.25)
        raise ChannelRpcQueueError(
            f"Timeout ({timeout_seconds}s) — Panel-Kanal nicht verbunden?"
        )

    def _get(self, req_id: str) -> sqlite3.Row | None:
        with self._lock:
            conn = self._connect()
            try:
                return conn.execute(
                    "SELECT * FROM rpc_requests WHERE id=?", (req_id,)
                ).fetchone()
            finally:
                conn.close()

    def _set_status(self, req_id: str, status: str) -> None:
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE rpc_requests SET status=?, updated_at=? WHERE id=?",
                    (status, now, req_id),
                )
                conn.commit()
            finally:
                conn.close()
