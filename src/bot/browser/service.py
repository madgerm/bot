"""Playwright-Sessions: local launch oder remote connect."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bot.browser.config import resolve_playwright_config
from bot.config.models import PlaywrightGlobalConfig


class BrowserServiceError(Exception):
    pass


@dataclass
class BrowserSessionInfo:
    mode: str
    endpoint: str | None
    team_id: str


class BrowserService:
    def __init__(self, root: Path, team_id: str, cfg: PlaywrightGlobalConfig) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.cfg = cfg
        self._playwright = None
        self._browser = None
        self._page = None

    @classmethod
    def for_team(cls, root: Path, team_id: str) -> BrowserService:
        cfg = resolve_playwright_config(root, team_id)
        return cls(root, team_id, cfg)

    def _ensure_playwright(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserServiceError(
                "Playwright nicht installiert: pip install -e '.[playwright]' "
                "&& playwright install chromium"
            ) from exc
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        return self._playwright

    def connect(self) -> BrowserSessionInfo:
        pw = self._ensure_playwright()
        if self.cfg.mode == "remote":
            if not self.cfg.ws_endpoints:
                raise BrowserServiceError("remote-Modus braucht ws_endpoints in der Config")
            endpoint = self.cfg.ws_endpoints[0]
            self._browser = pw.chromium.connect_over_cdp(endpoint)
            return BrowserSessionInfo(mode="remote", endpoint=endpoint, team_id=self.team_id)

        self._browser = pw.chromium.launch(headless=self.cfg.headless)
        return BrowserSessionInfo(mode="local", endpoint=None, team_id=self.team_id)

    def open_url(self, url: str) -> dict[str, Any]:
        if self._browser is None:
            self.connect()
        if self._page is None:
            if self._browser.contexts:
                context = self._browser.contexts[0]
            else:
                context = self._browser.new_context()
            self._page = context.new_page()
        self._page.goto(url, timeout=int(self.cfg.timeout_seconds * 1000))
        title = self._page.title()
        return {
            "url": self._page.url,
            "title": title,
            "team_id": self.team_id,
            "mode": self.cfg.mode,
        }

    def open_url_with_body(self, url: str, *, max_chars: int = 8000) -> dict[str, Any]:
        """URL öffnen, Seitentext lesen, Browser wieder schließen (Panel/Satellit-RPC)."""
        try:
            info = self.open_url(url)
            body_text = ""
            if self._page is not None:
                body_text = self._page.inner_text("body")[:max_chars]
            info["body_text"] = body_text
            return info
        finally:
            self.close()

    def screenshot(self, path: Path) -> Path:
        if self._page is None:
            raise BrowserServiceError("Keine Seite geöffnet — zuerst open_url aufrufen")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._page.screenshot(path=str(path))
        return path

    def close(self) -> None:
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        self._page = None
