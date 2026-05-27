"""Nachrichten: Format, Inbox/Outbox und Status-Workflow."""

from bot.messages.mailbox import Mailbox, MessageError
from bot.messages.models import Message, MessageStatus, SCHEMA_VERSION, new_message
from bot.messages.service import MessageService, open_message_service

__all__ = [
    "Mailbox",
    "Message",
    "MessageError",
    "MessageService",
    "MessageStatus",
    "SCHEMA_VERSION",
    "new_message",
    "open_message_service",
]
