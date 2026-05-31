"""Tests für E-Mail-Status-Probes (Panel)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.config.writers.mail_status import (
    collect_mail_status,
    probe_team_mail_config,
    probe_team_mail_connections,
    teams_with_email_config,
)


def _write_email(runtime_project: Path, team_id: str = "alpha") -> None:
    path = runtime_project / "teams" / team_id / "email.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "email": {
                    "enabled": True,
                    "imap": {
                        "host": "imap.test",
                        "port": 993,
                        "username": "u@test",
                        "secret_ref": "TEST_IMAP",
                    },
                    "smtp": {
                        "host": "smtp.test",
                        "port": 587,
                        "username": "u@test",
                        "secret_ref": "TEST_SMTP",
                    },
                }
            }
        ),
        encoding="utf-8",
    )


def test_teams_with_email_config(runtime_project: Path) -> None:
    assert teams_with_email_config(runtime_project) == []
    _write_email(runtime_project)
    assert teams_with_email_config(runtime_project) == ["alpha"]


def test_probe_team_mail_config_secrets(
    runtime_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_email(runtime_project)
    monkeypatch.setenv("TEST_IMAP", "x")
    monkeypatch.setenv("TEST_SMTP", "y")
    row = probe_team_mail_config(runtime_project, "alpha")
    assert row["ok"] is True
    assert "imap.test" in row["summary"]


def test_probe_team_mail_connections(
    runtime_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_email(runtime_project)
    monkeypatch.setenv("TEST_IMAP", "x")
    monkeypatch.setenv("TEST_SMTP", "y")

    class _Svc:
        def test_connections(self) -> dict[str, str]:
            return {"imap": "ok", "smtp": "ok"}

    class _MailService:
        @classmethod
        def for_team(cls, root: Path, team_id: str) -> _Svc:
            return _Svc()

    monkeypatch.setattr("bot.mail.service.MailService", _MailService)
    row = probe_team_mail_connections(runtime_project, "alpha")
    assert row["ok"] is True
    assert "IMAP: ok" in row["probe_summary"]


def test_collect_mail_status_empty(runtime_project: Path) -> None:
    out = collect_mail_status(runtime_project)
    assert out["teams"] == []
    assert out["ok"] is None
