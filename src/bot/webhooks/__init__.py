"""Eingehende Webhooks → Agent-Messages."""

from bot.webhooks.service import WebhookService, WebhookServiceError

__all__ = ["WebhookService", "WebhookServiceError"]
