"""Router: Prüfmethode → Agent und Prompt-Hinweis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bot.config.loader import discover_teams
from bot.runtime.pipeline import resolve_pipeline
from bot.verification.models import CheckMethod


@dataclass(frozen=True)
class RouteDecision:
    agent_id: str
    check_method: CheckMethod
    method_hint: str
    task_category: str


_METHOD_HINTS: dict[CheckMethod, str] = {
    "browser": (
        "Browser-Prüfung (Playwright): Seite öffnen, Formulare, Klicks, sichtbare "
        "Fehler. Nutze browser_open und beschreibe jeden Schritt."
    ),
    "code": (
        "Code-Prüfung: relevante Dateien, Routen, Controller, Models suchen. "
        "Nutze read_file, list_files, git_status."
    ),
    "db": (
        "Datenbank-Prüfung: Tabellen, Spalten, Migrationen in Code/Config suchen. "
        "Nutze read_file und list_files (kein direkter DB-Zugriff)."
    ),
    "api": (
        "API-Prüfung: Endpoints, HTTP-Routen, Request/Response in Code suchen. "
        "Optional browser_open für erreichbare URLs."
    ),
    "mixed": (
        "Kombinierte Prüfung: Browser + Code (+ ggf. API-Hinweise in Code)."
    ),
}


def route_verification_check(
    root: Path,
    team_id: str,
    check_method: CheckMethod,
) -> RouteDecision:
    teams = discover_teams(root / "teams")
    bundle = teams[team_id]
    pipe = resolve_pipeline(bundle)
    method = check_method if check_method in _METHOD_HINTS else "code"
    agent_id = pipe.execute_id
    category = {
        "browser": "review",
        "code": "coding",
        "db": "coding",
        "api": "coding",
        "mixed": "coding",
    }.get(method, "coding")
    return RouteDecision(
        agent_id=agent_id,
        check_method=method,
        method_hint=_METHOD_HINTS[method],
        task_category=category,
    )
