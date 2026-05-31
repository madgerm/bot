"""Tests für E-Mail-Plan MVP (Poll, Revise)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.mail.service import MailService
from bot.mail.store import MailStore
from tests.test_mail import _email_cfg


def test_poll_skips_existing_imap_uid(
    runtime_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    team = "alpha"
    store = MailStore(runtime_project, team)
    store.add_thread(
        subject="Hi",
        from_addr="a@b.de",
        body_text="body",
        imap_uid="uid-1",
    )

    class _Item:
        uid = "uid-1"
        subject = "Hi"
        from_addr = "a@b.de"
        body_text = "body"

    import bot.mail.service as svc_mod

    monkeypatch.setattr(svc_mod, "fetch_unseen", lambda cfg, limit=20: [_Item()])
    svc = MailService(runtime_project, team, _email_cfg())
    assert svc.poll() == []


def test_revise_draft(runtime_project: Path) -> None:
    team = "alpha"
    (runtime_project / "teams" / team / "email.json").write_text(
        json.dumps({"email": _email_cfg().model_dump(mode="json")}),
        encoding="utf-8",
    )
    store = MailStore(runtime_project, team)
    thread = store.add_thread(
        subject="Q",
        from_addr="c@d.de",
        body_text="Frage",
    )
    draft = store.create_draft(
        thread_id=thread.id,
        subject="Re: Q",
        body_text="Antwort v1",
        to_addrs=["c@d.de"],
        submit=True,
    )
    svc = MailService(runtime_project, team, _email_cfg())
    revised = svc.revise_draft(draft.id, feedback="Bitte kürzer", revised_by="max")
    assert "kürzer" in revised.body_text
    old = store.get_draft(draft.id)
    assert old is not None
    assert old.status == "rejected"
