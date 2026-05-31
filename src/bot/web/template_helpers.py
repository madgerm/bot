"""Hilfen für Jinja2-Templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def team_display_name(root: Path, team_id: str) -> str:
    try:
        from bot.config.writers.team_admin import load_team_config

        return load_team_config(root, team_id).team.name
    except Exception:
        return team_id


def team_breadcrumbs(
    team_id: str,
    team_label: str,
    *trail: tuple[str, str | None],
) -> list[dict[str, str | None]]:
    """Brotkrumen: Dashboard → Team → optionale Unterseiten."""
    crumbs: list[dict[str, str | None]] = [
        {"label": "Teams", "href": "/dashboard"},
        {"label": team_label, "href": f"/teams/{team_id}/"},
    ]
    for label, href in trail:
        crumbs.append({"label": label, "href": href})
    return crumbs


def with_team_page(
    root: Path,
    team_id: str,
    ctx: dict[str, Any],
    *,
    page: str | None = None,
    page_href: str | None = None,
) -> dict[str, Any]:
    """Ergänzt Team-Kontext um Anzeigenamen und optionale Brotkrumen."""
    label = team_display_name(root, team_id)
    out = dict(ctx)
    out.setdefault("team_id", team_id)
    out.setdefault("team_name", label)
    if page is not None:
        out.setdefault(
            "breadcrumbs",
            team_breadcrumbs(team_id, label, (page, page_href)),
        )
    return out


def register_template_globals(templates, root: Path) -> None:
    templates.env.globals["team_display_name"] = lambda tid: team_display_name(root, tid)
