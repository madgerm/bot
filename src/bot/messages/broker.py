"""Redis-Broker für Multi-Machine Message-Delivery."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from bot.config import load_runtime_config
from bot.config.models import BrokerConfig
from bot.messages.models import Message


class BrokerError(Exception):
    pass


def _resolve_secret(secret_ref: str | None) -> str | None:
    if not secret_ref:
        return None
    return os.environ.get(secret_ref)


class MessageBroker:
    """Redis-Listen-basierter Broker (optional)."""

    def __init__(self, cfg: BrokerConfig) -> None:
        self.cfg = cfg
        self._client: Any = None

    @classmethod
    def from_root(cls, root: Path | str) -> MessageBroker | None:
        config = load_runtime_config(Path(root))
        comm = config.system.system.communication
        if comm.mode != "broker" or not comm.broker:
            return None
        return cls(comm.broker)

    def _connect(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import redis
        except ImportError as exc:
            raise BrokerError(
                "redis-Paket fehlt — pip install 'bot[broker]'"
            ) from exc
        password = _resolve_secret(self.cfg.secret_ref)
        self._client = redis.from_url(self.cfg.url, password=password, decode_responses=True)
        return self._client

    def queue_key(self, team_id: str, agent_id: str) -> str:
        return f"{self.cfg.queue_prefix}:{team_id}:{agent_id}:inbox"

    def publish(self, team_id: str, agent_id: str, message: Message) -> None:
        client = self._connect()
        key = self.queue_key(team_id, agent_id)
        client.rpush(key, message.model_dump_json())

    def consume(self, team_id: str, agent_id: str, timeout: int = 1) -> Message | None:
        client = self._connect()
        key = self.queue_key(team_id, agent_id)
        item = client.blpop(key, timeout=timeout)
        if not item:
            return None
        _, payload = item
        return Message.model_validate_json(payload)

    def drain_to_mailbox(
        self, root: Path, team_id: str, agent_id: str, inbox_template: str, limit: int = 50
    ) -> int:
        """Broker-Nachrichten in lokale Inbox schreiben (Hybrid-Betrieb)."""
        from bot.messages.mailbox import Mailbox

        mailbox = Mailbox(root, team_id, agent_id, inbox_template)
        mailbox.ensure_dirs()
        count = 0
        for _ in range(limit):
            msg = self.consume(team_id, agent_id, timeout=0)
            if msg is None:
                break
            mailbox.receive(msg)
            count += 1
        return count
