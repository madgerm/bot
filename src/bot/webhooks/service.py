"""Webhook-Empfang: validiert Secret, legt Message in Inbox ab."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Any

from bot.config import load_runtime_config
from bot.messages import MessageService, MessageError


class WebhookServiceError(Exception):
    pass


def _resolve_secret(secret_ref: str) -> str | None:
    return os.environ.get(secret_ref)


class WebhookService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._config = load_runtime_config(self.root)
        wh = self._config.system.webhooks_global
        self._enabled = wh.enabled if wh else True
        self._secret_ref = wh.secret_ref if wh else "BOT_WEBHOOK_SECRET"

    def verify_token(self, token: str | None) -> bool:
        expected = _resolve_secret(self._secret_ref)
        if not expected:
            return False
        if not token:
            return False
        return hmac.compare_digest(token, expected)

    def verify_signature(self, body: bytes, signature: str | None) -> bool:
        expected = _resolve_secret(self._secret_ref)
        if not expected or not signature:
            return False
        digest = hmac.new(expected.encode(), body, hashlib.sha256).hexdigest()
        provided = signature.removeprefix("sha256=")
        return hmac.compare_digest(digest, provided)

    def ingest(
        self,
        *,
        team_id: str,
        to_agent: str,
        subject: str,
        content: str,
        from_agent: str = "webhook",
        type: str = "task",
        task_category: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._enabled:
            raise WebhookServiceError("Webhooks sind deaktiviert")
        cfg = self._config.teams.get(team_id)
        if not cfg:
            raise WebhookServiceError(f"Team '{team_id}' nicht gefunden")
        sender = from_agent
        if sender not in cfg.agents:
            sender = cfg.team.team.orchestrator_id
        svc = MessageService(self.root)
        try:
            msg = svc.send(
                team_id=team_id,
                from_agent=sender,
                to_agent=to_agent,
                subject=subject,
                content=content,
                type=type,
                task_category=task_category,
            )
        except MessageError as exc:
            raise WebhookServiceError(str(exc)) from exc
        result = msg.model_dump()
        if metadata:
            result["webhook_metadata"] = metadata
        return result
