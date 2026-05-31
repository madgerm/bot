"""Browser über Panel-Kanal (Satellit)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bot.channel.panel_rpc import execute_panel_rpc


def test_panel_rpc_browser_open(tmp_path: Path) -> None:
    mock_info = {
        "url": "https://example.com",
        "title": "Example",
        "body_text": "Hello",
        "mode": "local",
    }
    with patch("bot.browser.service.BrowserService") as cls:
        inst = cls.for_team.return_value
        inst.open_url_with_body.return_value = mock_info
        out = execute_panel_rpc(
            tmp_path,
            "browser.open",
            {"team_id": "demo", "url": "https://example.com"},
        )
    assert out["body_text"] == "Hello"
    cls.for_team.assert_called_once()
