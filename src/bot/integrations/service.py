"""Telegram/Matrix → Webhook/Message-Pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from bot.integrations.config import IntegrationsConfig, load_integrations_config, resolve_ref
from bot.webhooks import WebhookService, WebhookServiceError


class IntegrationServiceError(Exception):
    pass


class IntegrationService:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.cfg = load_integrations_config(root, team_id)

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> IntegrationService:
        return cls(Path(root), team_id)

    def handle_telegram_update(self, update: dict[str, Any]) -> dict[str, Any]:
        if not self.cfg or not self.cfg.telegram.enabled:
            raise IntegrationServiceError("Telegram deaktiviert")
        message = update.get("message") or update.get("edited_message")
        if not message:
            return {"status": "ignored"}
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        agent_id = self.cfg.telegram.default_agent_id
        wh = WebhookService(self.root)
        try:
            result = wh.ingest(
                team_id=self.team_id,
                to_agent=agent_id,
                subject=f"Telegram {chat_id}",
                content=text,
                from_agent="telegram",
                metadata={"chat_id": chat_id},
            )
        except WebhookServiceError as exc:
            raise IntegrationServiceError(str(exc)) from exc
        return {"status": "ok", "message_id": result.get("id")}

    def send_telegram(self, chat_id: str | int, text: str) -> None:
        if not self.cfg or not self.cfg.telegram.enabled:
            raise IntegrationServiceError("Telegram deaktiviert")
        token = resolve_ref(self.cfg.telegram.bot_token_ref)
        if not token:
            raise IntegrationServiceError("TELEGRAM_BOT_TOKEN fehlt")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=30.0)
        resp.raise_for_status()

    def send_matrix(self, room_id: str, text: str) -> None:
        if not self.cfg or not self.cfg.matrix.enabled:
            raise IntegrationServiceError("Matrix deaktiviert")
        token = resolve_ref(self.cfg.matrix.access_token_ref)
        if not token:
            raise IntegrationServiceError("MATRIX_ACCESS_TOKEN fehlt")
        homeserver = self.cfg.matrix.homeserver.rstrip("/")
        url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message"
        txn_id = "bot-" + str(hash(text))[:8]
        resp = httpx.put(
            f"{url}/{txn_id}",
            json={"msgtype": "m.text", "body": text},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        resp.raise_for_status()

    def handle_matrix_event(self, event: dict[str, Any]) -> dict[str, Any]:
        if not self.cfg or not self.cfg.matrix.enabled:
            raise IntegrationServiceError("Matrix deaktiviert")
        if event.get("type") != "m.room.message":
            return {"status": "ignored"}
        content = event.get("content", {})
        body = content.get("body", "")
        agent_id = self.cfg.matrix.default_agent_id
        wh = WebhookService(self.root)
        result = wh.ingest(
            team_id=self.team_id,
            to_agent=agent_id,
            subject="Matrix",
            content=body,
            from_agent="matrix",
        )
        return {"status": "ok", "message_id": result.get("id")}
