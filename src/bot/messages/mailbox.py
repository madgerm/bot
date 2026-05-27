"""File-basierte Inbox/Outbox mit Status-Workflow."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from bot.messages.models import Message, MessageStatus
from bot.messages.paths import agent_inbox, agent_outbox
from bot.messages.workflow import InvalidTransitionError, assert_transition

PROCESSED_DIR = "processed"
FAILED_DIR = "failed"


class MessageError(Exception):
    """Fehler bei Nachrichtenoperationen."""


class Mailbox:
    """Inbox/Outbox eines einzelnen Agents."""

    def __init__(
        self,
        root: Path,
        team_id: str,
        agent_id: str,
        inbox_template: str,
    ) -> None:
        self._root = root.resolve()
        self.team_id = team_id
        self.agent_id = agent_id
        self.inbox = agent_inbox(self._root, team_id, agent_id, inbox_template)
        self.outbox = agent_outbox(self._root, team_id, agent_id, inbox_template)

    def ensure_dirs(self) -> None:
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.outbox.mkdir(parents=True, exist_ok=True)
        (self.inbox / PROCESSED_DIR).mkdir(parents=True, exist_ok=True)
        (self.inbox / FAILED_DIR).mkdir(parents=True, exist_ok=True)

    def _message_path(self, message_id: str, *, processed: bool = False, failed: bool = False) -> Path:
        if processed:
            return self.inbox / PROCESSED_DIR / f"{message_id}.json"
        if failed:
            return self.inbox / FAILED_DIR / f"{message_id}.json"
        return self.inbox / f"{message_id}.json"

    def _find_path(self, message_id: str) -> Path | None:
        for path in (
            self._message_path(message_id),
            self._message_path(message_id, processed=True),
            self._message_path(message_id, failed=True),
        ):
            if path.is_file():
                return path
        return None

    def _read(self, path: Path) -> Message:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Message.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise MessageError(f"Ungültige Message in {path}: {exc}") from exc

    def _write(self, path: Path, message: Message) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(message.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)

    def _with_lock(self, path: Path, fn):
        if not path.is_file():
            return None
        with open(path, "r+", encoding="utf-8") as handle:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except ImportError:
                pass
            handle.seek(0)
            raw = handle.read()
            try:
                data = json.loads(raw) if raw.strip() else {}
                message = Message.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise MessageError(f"Ungültige Message in {path}: {exc}") from exc
            updated = fn(message)
            if updated is None:
                return None
            handle.seek(0)
            handle.truncate()
            payload = json.dumps(updated.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
            handle.write(payload)
            handle.flush()
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except ImportError:
                pass
            return updated

    def list_messages(self, status: MessageStatus | None = None) -> list[Message]:
        messages: list[Message] = []
        for directory in (self.inbox, self.inbox / PROCESSED_DIR, self.inbox / FAILED_DIR):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                if path.name.endswith(".tmp"):
                    continue
                msg = self._read(path)
                if status is None or msg.status == status:
                    messages.append(msg)
        return sorted(messages, key=lambda m: m.created_at)

    def get(self, message_id: str) -> Message | None:
        path = self._find_path(message_id)
        if path is None:
            return None
        return self._read(path)

    def exists_done(self, message_id: str) -> bool:
        path = self._message_path(message_id, processed=True)
        if not path.is_file():
            return False
        msg = self._read(path)
        return msg.status == "done"

    def receive(self, message: Message) -> Message:
        """Legt eine Message in der Inbox ab (idempotent bei erledigten Duplikaten)."""
        self.ensure_dirs()
        if message.to_agent != self.agent_id or message.team_id != self.team_id:
            raise MessageError(
                f"Message {message.id} gehört nicht zu {self.team_id}/{self.agent_id}"
            )

        if self.exists_done(message.id):
            raise MessageError(
                f"Message {message.id} ist bereits erledigt — kein erneutes Einreihen"
            )

        inbox_path = self._message_path(message.id)
        if inbox_path.is_file():
            existing = self._read(inbox_path)
            if existing.status == "done":
                raise MessageError(f"Message {message.id} ist bereits erledigt")
            return existing

        failed_path = self._message_path(message.id, failed=True)
        if failed_path.is_file():
            existing = self._read(failed_path)
            if existing.status != "failed":
                raise MessageError(f"Inkonsistenter Zustand für {message.id}")
            return existing

        self._write(inbox_path, message)
        return message

    def write_outbox_copy(self, message: Message) -> None:
        self.ensure_dirs()
        self._write(self.outbox / f"{message.id}.json", message)

    def transition(
        self,
        message_id: str,
        new_status: MessageStatus,
        *,
        error: str | None = None,
    ) -> Message:
        path = self._find_path(message_id)
        if path is None:
            raise MessageError(f"Message {message_id} nicht gefunden")

        msg = self._read(path)
        assert_transition(msg.status, new_status)
        now = datetime.now(UTC)
        updated = msg.model_copy(
            update={
                "status": new_status,
                "updated_at": now,
                "error": error if new_status == "failed" else msg.error,
            }
        )
        if new_status != "failed":
            updated = updated.model_copy(update={"error": None})

        if new_status == "done":
            target = self._message_path(message_id, processed=True)
        elif new_status == "failed":
            target = self._message_path(message_id, failed=True)
        else:
            target = self._message_path(message_id)

        self._write(target, updated)
        if path != target and path.is_file():
            path.unlink()
        return updated

    def retry_failed(self, message_id: str) -> Message:
        path = self._message_path(message_id, failed=True)
        if not path.is_file():
            raise MessageError(f"Fehlgeschlagene Message {message_id} nicht gefunden")
        msg = self._read(path)
        if msg.status != "failed":
            raise MessageError(f"Message {message_id} ist nicht fehlgeschlagen")
        if msg.retry_count >= msg.max_retries:
            raise MessageError(
                f"Message {message_id} hat max_retries ({msg.max_retries}) erreicht"
            )

        retried = msg.model_copy(
            update={
                "status": "pending",
                "retry_count": msg.retry_count + 1,
                "error": None,
            }
        )
        inbox_path = self._message_path(message_id)
        self._write(inbox_path, retried)
        path.unlink()
        return retried

    def claim_next(self) -> Message | None:
        pending = self.list_messages(status="pending")
        for candidate in pending:
            path = self._message_path(candidate.id)

            def _claim(msg: Message) -> Message | None:
                if msg.status != "pending":
                    return None
                now = datetime.now(UTC)
                return msg.model_copy(update={"status": "processing", "updated_at": now})

            if not path.is_file():
                continue
            try:
                claimed = self._with_lock(path, _claim)
            except InvalidTransitionError:
                continue
            if claimed is not None:
                return claimed
        return None
