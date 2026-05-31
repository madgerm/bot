"""bot up — kombinierter Start."""

from __future__ import annotations

from pathlib import Path

from bot.cli_up import _ensure_session_secret


def test_ensure_session_secret_sets_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BOT_SESSION_SECRET", raising=False)
    _ensure_session_secret(tmp_path)
    assert len((tmp_path := __import__("os").environ.get("BOT_SESSION_SECRET", ""))) >= 32
