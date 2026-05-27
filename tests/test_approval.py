import pytest

from bot.approval.status import (
    ApprovalError,
    assert_can_send,
    transition_approve,
    transition_submit_for_approval,
)


def test_approve_flow() -> None:
    assert transition_submit_for_approval("draft") == "awaiting_approval"
    assert transition_approve("awaiting_approval") == "approved"
    assert_can_send("approved")


def test_send_without_approval() -> None:
    with pytest.raises(ApprovalError):
        assert_can_send("awaiting_approval")
