"""Seite laden und Öffnungszeiten per Agent extrahieren."""

from __future__ import annotations

from typing import Any

from bot.hours.config import WebsitePageConfig
from bot.hours.extract import extract_hours_from_markdown
from bot.hours.page_fetch import fetch_page_markdown
from bot.llm import LlmStack


def fetch_hours_from_page(
    cfg: WebsitePageConfig,
    llm_stack: LlmStack,
) -> tuple[dict[str, Any], dict[str, Any]]:
    page = fetch_page_markdown(cfg)
    hours, method = extract_hours_from_markdown(page["markdown"], llm_stack)
    report = {
        "source_url": page.get("url", cfg.url),
        "page_title": page.get("title", ""),
        "crawl_engine": page.get("engine", cfg.crawl_engine),
        "extraction_method": method,
        "content_preview": (page.get("markdown") or "")[:500],
        "agent_note": hours.get("note"),
    }
    return hours, report
