"""Webseite als Text/Markdown für Öffnungszeiten-Extraktion laden."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from bot.hours.config import HoursConfigError, WebsitePageConfig


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = False
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3", "tr", "td", "th"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = data.strip()
            if text:
                self._chunks.append(text + " ")

    def text(self) -> str:
        raw = "".join(self._chunks)
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def _html_to_markdown(body: str) -> str:
    if body.lstrip().startswith("<"):
        parser = _TextExtractor()
        parser.feed(body)
        return parser.text()
    return body.strip()


def _fetch_file_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    path = Path(unquote(parsed.path))
    if not path.is_file():
        raise HoursConfigError(f"Lokale Datei nicht gefunden: {path}")
    raw = path.read_text(encoding="utf-8", errors="replace")
    markdown = _html_to_markdown(raw) or raw.strip()
    if not markdown:
        raise HoursConfigError(f"Kein lesbarer Inhalt in {path}")
    return {"url": url, "title": path.name, "markdown": markdown, "engine": "file"}


def _fetch_httpx(url: str) -> dict[str, Any]:
    if url.startswith("file://"):
        return _fetch_file_url(url)
    try:
        response = httpx.get(
            url,
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "bot-hours-checker/1.0"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HoursConfigError(f"Seite nicht ladbar ({url}): {exc}") from exc
    markdown = _html_to_markdown(response.text)
    if not markdown:
        raise HoursConfigError(f"Kein lesbarer Inhalt auf {url}")
    return {
        "url": str(response.url),
        "title": "",
        "markdown": markdown,
        "engine": "httpx",
    }


def _fetch_crawl4ai(url: str) -> dict[str, Any]:
    from bot.crawl.service import crawl_url_sync

    result = crawl_url_sync(url)
    markdown = (result.get("markdown") or "").strip()
    if not markdown:
        raise HoursConfigError(f"Crawl lieferte keinen Text für {url}")
    return {
        "url": result.get("url", url),
        "title": result.get("title", ""),
        "markdown": markdown,
        "engine": "crawl4ai",
    }


def fetch_page_markdown(cfg: WebsitePageConfig) -> dict[str, Any]:
    engine = cfg.crawl_engine
    if engine == "crawl4ai":
        return _fetch_crawl4ai(cfg.url)
    if engine == "httpx":
        return _fetch_httpx(cfg.url)
    try:
        return _fetch_crawl4ai(cfg.url)
    except HoursConfigError:
        return _fetch_httpx(cfg.url)
