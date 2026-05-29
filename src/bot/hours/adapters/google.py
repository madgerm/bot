"""Google — Snapshot-Datei oder Agent liest Maps-Seite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bot.hours.config import HoursTeamConfig, WebsitePageConfig
from bot.hours.page_check import fetch_hours_from_page
from bot.llm import LlmStack


def fetch_google_snapshot(
    root: Path,
    team_id: str,
    cfg: HoursTeamConfig,
    *,
    llm_stack: LlmStack | None = None,
) -> dict[str, Any] | None:
    gb = cfg.google_business
    if not gb.enabled:
        return None
    if gb.page_url and llm_stack is not None:
        page_cfg = WebsitePageConfig(url=gb.page_url, crawl_engine="auto")
        hours, _ = fetch_hours_from_page(page_cfg, llm_stack)
        return hours
    snapshot = root / "data" / team_id / "google_hours.snapshot.json"
    if snapshot.is_file():
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        return data.get("hours", data)
    return {}


def google_agent_report(
    cfg: HoursTeamConfig,
    llm_stack: LlmStack,
) -> dict[str, Any] | None:
    gb = cfg.google_business
    if not gb.enabled or not gb.page_url:
        return None
    page_cfg = WebsitePageConfig(url=gb.page_url, crawl_engine="auto")
    _hours, report = fetch_hours_from_page(page_cfg, llm_stack)
    report["source"] = "google_page"
    return report
