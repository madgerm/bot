import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from bot.browser.config import resolve_playwright_config


def test_resolve_playwright_global(runtime_project: Path) -> None:
    system_path = runtime_project / "config" / "system.json"
    data = json.loads(system_path.read_text(encoding="utf-8"))
    data["playwright_global"] = {"mode": "local", "headless": True}
    system_path.write_text(json.dumps(data), encoding="utf-8")

    cfg = resolve_playwright_config(runtime_project, "alpha")
    assert cfg.mode == "local"


def test_resolve_playwright_team_override(runtime_project: Path) -> None:
    (runtime_project / "teams" / "alpha" / "playwright.json").write_text(
        json.dumps({"playwright": {"source": "custom", "mode": "remote", "ws_endpoints": ["ws://x"]}}),
        encoding="utf-8",
    )
    cfg = resolve_playwright_config(runtime_project, "alpha")
    assert cfg.mode == "remote"
    assert cfg.ws_endpoints == ["ws://x"]


@patch("bot.browser.service.BrowserService._ensure_playwright")
def test_browser_open_mock(mock_pw, runtime_project: Path) -> None:
    from bot.browser import BrowserService

    mock_page = MagicMock()
    mock_page.title.return_value = "Example"
    mock_page.url = "https://example.com"

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.contexts = []
    mock_browser.new_context.return_value = mock_context

    mock_instance = MagicMock()
    mock_instance.chromium.launch.return_value = mock_browser
    mock_pw.return_value = mock_instance

    service = BrowserService.for_team(runtime_project, "alpha")
    result = service.open_url("https://example.com")
    assert result["title"] == "Example"
    service.close()
