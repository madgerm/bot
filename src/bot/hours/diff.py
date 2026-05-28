"""Vergleich von Öffnungszeiten-Snapshots."""

from __future__ import annotations

from typing import Any


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in sorted(data.items()):
        if key in {"note", "_note"}:
            continue
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_flatten(value, path))
        elif isinstance(value, list):
            out[path] = json_dumps_list(value)
        else:
            out[path] = str(value)
    return out


def json_dumps_list(value: list[Any]) -> str:
    import json

    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def compute_diff(
    master: dict[str, Any],
    website: dict[str, Any],
    google: dict[str, Any] | None = None,
    *,
    agent_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    flat_master = _flatten(master)
    flat_web = _flatten(website)
    flat_google = _flatten(google) if google else {}

    changes: list[dict[str, str]] = []
    all_keys = sorted(set(flat_master) | set(flat_web) | set(flat_google))

    for key in all_keys:
        m = flat_master.get(key)
        w = flat_web.get(key)
        g = flat_google.get(key) if flat_google else None
        if m != w:
            changes.append(
                {
                    "field": key,
                    "master": m or "",
                    "website": w or "",
                    "kind": "master_vs_website",
                }
            )
        if flat_google and m != g:
            changes.append(
                {
                    "field": key,
                    "master": m or "",
                    "google": g or "",
                    "kind": "master_vs_google",
                }
            )
        if flat_google and w != g:
            changes.append(
                {
                    "field": key,
                    "website": w or "",
                    "google": g or "",
                    "kind": "website_vs_google",
                }
            )

    result: dict[str, Any] = {
        "has_diff": bool(changes),
        "change_count": len(changes),
        "changes": changes,
        "check_mode": "agent_page" if agent_report else "snapshot",
    }
    if agent_report:
        result["agent_report"] = agent_report
    return result
