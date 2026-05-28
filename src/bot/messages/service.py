"""Nachrichtenversand mit Config-Validierung."""

from __future__ import annotations

from pathlib import Path

from bot.config import ConfigLoadError, load_runtime_config
from bot.messages.mailbox import Mailbox, MessageError
from bot.messages.models import Message, MessageStatus, new_message


class MessageService:
    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        self._config = load_runtime_config(self._root)
        self._inbox_template = self._config.system.system.communication.inbox_base

    @property
    def root(self) -> Path:
        return self._root

    def _mailbox(self, team_id: str, agent_id: str) -> Mailbox:
        self._validate_agent(team_id, agent_id)
        return Mailbox(self._root, team_id, agent_id, self._inbox_template)

    def _validate_agent(self, team_id: str, agent_id: str) -> None:
        if team_id not in self._config.teams:
            raise MessageError(f"Unbekanntes Team '{team_id}'")
        if agent_id not in self._config.teams[team_id].agents:
            raise MessageError(
                f"Unbekannter Agent '{agent_id}' in Team '{team_id}'"
            )

    def send(
        self,
        *,
        team_id: str,
        from_agent: str,
        to_agent: str,
        subject: str,
        content: str,
        type: str = "task",
        task_category: str | None = None,
        priority: str = "normal",
        model_override: str | None = None,
    ) -> Message:
        self._validate_agent(team_id, from_agent)
        self._validate_agent(team_id, to_agent)

        message = new_message(
            team_id=team_id,
            from_agent=from_agent,
            to_agent=to_agent,
            subject=subject,
            content=content,
            type=type,
            task_category=task_category,
            priority=priority,  # type: ignore[arg-type]
            model_override=model_override,
        )

        recipient = self._mailbox(team_id, to_agent)
        sender = self._mailbox(team_id, from_agent)
        recipient.ensure_dirs()
        sender.ensure_dirs()

        stored = recipient.receive(message)
        sender.write_outbox_copy(stored)
        return stored

    def list_inbox(
        self, team_id: str, agent_id: str, status: MessageStatus | None = None
    ) -> list[Message]:
        return self._mailbox(team_id, agent_id).list_messages(status=status)

    def claim(self, team_id: str, agent_id: str) -> Message | None:
        mailbox = self._mailbox(team_id, agent_id)
        mailbox.ensure_dirs()
        return mailbox.claim_next()

    def complete(self, team_id: str, agent_id: str, message_id: str) -> Message:
        return self._mailbox(team_id, agent_id).transition(message_id, "done")

    def fail(self, team_id: str, agent_id: str, message_id: str, error: str) -> Message:
        return self._mailbox(team_id, agent_id).transition(
            message_id, "failed", error=error
        )

    def retry(self, team_id: str, agent_id: str, message_id: str) -> Message:
        return self._mailbox(team_id, agent_id).retry_failed(message_id)


def open_message_service(root: Path | str) -> MessageService:
    try:
        return MessageService(root)
    except ConfigLoadError as exc:
        raise MessageError(str(exc)) from exc
