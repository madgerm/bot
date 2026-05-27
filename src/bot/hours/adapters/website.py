"""Website-Öffnungszeiten lesen/schreiben."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from bot.hours.config import HoursTeamConfig, WebsiteFileConfig, WebsiteHttpConfig, resolve_secret
from bot.hours.master import HoursConfigError, load_master, master_path, save_master


def fetch_website_snapshot(root: Path, cfg: HoursTeamConfig) -> dict[str, Any]:
    website = cfg.website
    if isinstance(website, WebsiteFileConfig):
        path = master_path(root, website.path)
        if not path.is_file():
            return {"hours": {}}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("hours", data)

    if isinstance(website, WebsiteHttpConfig):
        headers: dict[str, str] = {}
        token = resolve_secret(website.secret_ref)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = httpx.get(website.url, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data.get("hours", data)
        except httpx.HTTPError as exc:
            raise HoursConfigError(f"Website HTTP: {exc}") from exc

    raise HoursConfigError(f"Unbekannter Website-Typ: {website}")


def publish_website_snapshot(
    root: Path, cfg: HoursTeamConfig, hours_data: dict[str, Any]
) -> None:
    website = cfg.website
    payload = {"hours": hours_data}

    if isinstance(website, WebsiteFileConfig):
        path = master_path(root, website.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return

    if isinstance(website, WebsiteHttpConfig):
        headers: dict[str, str] = {"Content-Type": "application/json"}
        token = resolve_secret(website.secret_ref)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = httpx.put(website.url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HoursConfigError(f"Website publish HTTP: {exc}") from exc
        return

    raise HoursConfigError(f"Unbekannter Website-Typ: {website}")
