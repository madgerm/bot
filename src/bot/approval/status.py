"""Gemeinsame Statusmaschine für Mail-Entwürfe und Öffnungszeiten-Diffs."""

from __future__ import annotations

from typing import Literal

DraftStatus = Literal[
    "draft",
    "awaiting_approval",
    "approved",
    "rejected",
    "sending",
    "sent",
    "failed",
    "published",
]

TERMINAL: frozenset[str] = frozenset({"sent", "rejected", "published", "failed"})


class ApprovalError(Exception):
    pass


def assert_can_approve(status: str) -> None:
    if status not in ("draft", "awaiting_approval"):
        raise ApprovalError(f"Freigabe nicht möglich (Status: {status})")


def assert_can_send(status: str) -> None:
    if status != "approved":
        raise ApprovalError(
            f"Versand/Publish nur nach Freigabe (Status: {status}, erwartet: approved)"
        )


def transition_submit_for_approval(status: str) -> str:
    if status not in ("draft", "awaiting_approval"):
        raise ApprovalError(f"Einreichen nicht möglich (Status: {status})")
    return "awaiting_approval"


def transition_approve(status: str) -> str:
    assert_can_approve(status)
    return "approved"


def transition_reject(status: str) -> str:
    if status in TERMINAL:
        raise ApprovalError(f"Ablehnen nicht möglich (Status: {status})")
    return "rejected"


def transition_sending(status: str) -> str:
    assert_can_send(status)
    return "sending"


def transition_sent(status: str) -> str:
    if status != "sending":
        raise ApprovalError(f"Abschluss nicht möglich (Status: {status})")
    return "sent"


def transition_published(status: str) -> str:
    assert_can_send(status)
    return "published"
