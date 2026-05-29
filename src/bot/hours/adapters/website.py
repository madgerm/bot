"""Website-Öffnungszeiten lesen/schreiben."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from bot.hours.config import (
    HoursConfigError,
    HoursTeamConfig,
    PublishTargetConfig,
    WebsiteFileConfig,
    WebsiteHttpConfig,
    WebsitePageConfig,
    publish_target,
    resolve_secret,
)
from bot.hours.master import master_path
from bot.hours.page_check import fetch_hours_from_page
from bot.llm import LlmStack


def fetch_website_snapshot(
    root: Path,
    cfg: HoursTeamConfig,
    *,
    llm_stack: LlmStack | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    website = cfg.website
    if isinstance(website, WebsitePageConfig):
        if llm_stack is None:
            raise HoursConfigError(
                "website.type=page benötigt LLM — bot hours check oder hours_checker-Agent."
            )
        hours, report = fetch_hours_from_page(website, llm_stack)
        return hours, report

    if isinstance(website, WebsiteFileConfig):
        path = master_path(root, website.path)
        if not path.is_file():
            return {}, None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("hours", data), None

    if isinstance(website, WebsiteHttpConfig):
        headers: dict[str, str] = {}
        token = resolve_secret(website.secret_ref)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = httpx.get(website.url, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data.get("hours", data), None
        except httpx.HTTPError as exc:
            raise HoursConfigError(f"Website HTTP: {exc}") from exc

    raise HoursConfigError(f"Unbekannter Website-Typ: {website}")


def publish_website_snapshot(
    root: Path, target: PublishTargetConfig, hours_data: dict[str, Any]
) -> None:
    payload = {"hours": hours_data}
    if isinstance(target, WebsiteFileConfig):
        path = master_path(root, target.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return
    if isinstance(target, WebsiteHttpConfig):
        headers: dict[str, str] = {"Content-Type": "application/json"}
        token = resolve_secret(target.secret_ref)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = httpx.put(target.url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HoursConfigError(f"Website publish HTTP: {exc}") from exc
        return
    raise HoursConfigError(f"Unbekannter Publish-Typ: {target}")


def publish_team_hours(root: Path, cfg: HoursTeamConfig, hours_data: dict[str, Any]) -> None:
    publish_website_snapshot(root, publish_target(cfg), hours_data)
