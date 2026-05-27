"""Message-JSON-Schema (schema_version 1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = "1"

MessageStatus = Literal["pending", "processing", "done", "failed"]
MessagePriority = Literal["low", "normal", "high"]


class Message(BaseModel):
    id: str
    schema_version: str = SCHEMA_VERSION
    team_id: str
    from_agent: str
    to_agent: str
    type: str = "task"
    task_category: str | None = None
    subject: str
    content: str
    status: MessageStatus = "pending"
    priority: MessagePriority = "normal"
    model_override: str | None = None
    attachments: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    error: str | None = None

    @field_validator("id")
    @classmethod
    def uuid_like(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 8:
            raise ValueError("message.id muss eine gültige UUID sein")
        return normalized

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(
                f"Nicht unterstützte schema_version '{value}' (erwartet: {SCHEMA_VERSION})"
            )
        return value


def new_message(
    *,
    team_id: str,
    from_agent: str,
    to_agent: str,
    subject: str,
    content: str,
    type: str = "task",
    task_category: str | None = None,
    priority: MessagePriority = "normal",
    model_override: str | None = None,
    attachments: list[str] | None = None,
    max_retries: int = 3,
) -> Message:
    now = datetime.now(UTC)
    return Message(
        id=str(uuid4()),
        team_id=team_id,
        from_agent=from_agent,
        to_agent=to_agent,
        type=type,
        task_category=task_category,
        subject=subject,
        content=content,
        priority=priority,
        model_override=model_override,
        attachments=attachments or [],
        created_at=now,
        updated_at=now,
        max_retries=max_retries,
    )
