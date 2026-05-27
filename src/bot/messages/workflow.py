"""Erlaubte Status-Übergänge."""

from __future__ import annotations

from bot.messages.models import MessageStatus

ALLOWED_TRANSITIONS: dict[MessageStatus, set[MessageStatus]] = {
    "pending": {"processing"},
    "processing": {"done", "failed", "pending"},
    "failed": {"pending"},
    "done": set(),
}


class InvalidTransitionError(ValueError):
    """Status-Übergang ist nicht erlaubt."""


def assert_transition(current: MessageStatus, new: MessageStatus) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise InvalidTransitionError(
            f"Übergang '{current}' → '{new}' ist nicht erlaubt "
            f"(erlaubt: {', '.join(sorted(allowed)) or 'keine'})"
        )
