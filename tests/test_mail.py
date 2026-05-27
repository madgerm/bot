import json
from pathlib import Path
from unittest.mock import patch

import pytest

from bot.approval.status import ApprovalError
from bot.mail.config import validate_recipient
from bot.mail.config import EmailRules, EmailTeamConfig, ImapConfig, SmtpConfig
from bot.mail.service import MailService, MailServiceError
from bot.mail.store import MailStore


def _email_cfg() -> EmailTeamConfig:
    return EmailTeamConfig(
        imap=ImapConfig(
            host="imap.test",
            username="u@test.de",
            secret_ref="TEST_IMAP",
        ),
        smtp=SmtpConfig(
            host="smtp.test",
            username="u@test.de",
            secret_ref="TEST_SMTP",
        ),
        rules=EmailRules(allowed_recipient_domains=["test.de"]),
    )


def test_validate_recipient_domain() -> None:
    cfg = _email_cfg()
    validate_recipient(cfg, "a@test.de")
    with pytest.raises(Exception):
        validate_recipient(cfg, "a@other.com")


def test_mail_draft_approve_send(runtime_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_IMAP", "x")
    monkeypatch.setenv("TEST_SMTP", "x")

    team = "alpha"
    email_path = runtime_project / "teams" / team / "email.json"
    email_path.write_text(
        json.dumps(
            {
                "email": {
                    "imap": {
                        "host": "imap.test",
                        "username": "u@test.de",
                        "secret_ref": "TEST_IMAP",
                    },
                    "smtp": {
                        "host": "smtp.test",
                        "username": "u@test.de",
                        "secret_ref": "TEST_SMTP",
                    },
                    "rules": {"allowed_recipient_domains": ["test.de"]},
                }
            }
        ),
        encoding="utf-8",
    )

    service = MailService(runtime_project, team, _email_cfg())
    thread = service.import_fixture(
        subject="Anfrage",
        from_addr="kunde@test.de",
        body_text="Hallo",
        imap_uid="1",
    )
    draft = service.create_reply_draft(
        thread.id, body_text="Antwort", to_addrs=["kunde@test.de"]
    )
    assert draft.status == "awaiting_approval"

    with pytest.raises(MailServiceError):
        service.send_approved(draft.id)

    approved = service.approve(draft.id, "max")
    assert approved.status == "approved"

    with patch("bot.mail.service.send_message") as mock_send:
        sent = service.send_approved(draft.id)
        mock_send.assert_called_once()
    assert sent.status == "sent"


def test_mail_store_idempotent_uid(runtime_project: Path) -> None:
    store = MailStore(runtime_project, "alpha")
    t1 = store.add_thread(
        subject="A", from_addr="a@b.de", body_text="x", imap_uid="uid-1"
    )
    t2 = store.add_thread(
        subject="A", from_addr="a@b.de", body_text="x", imap_uid="uid-1"
    )
    assert t1.id == t2.id
