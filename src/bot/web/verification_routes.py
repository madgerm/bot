"""Panel: Prüffragen-Übersicht (Fragen-Teams)."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from bot.config.writers.team_admin import load_team_config
from bot.verification.store import VerificationStore
from bot.verification.workflow import is_verification_team


def register_verification_routes(
    app, templates: Jinja2Templates, root_path: Path
) -> None:
    from bot.web.auth import CurrentUser, require_team_access

    @app.get("/teams/{team_id}/verification", response_class=HTMLResponse)
    async def team_verification_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        cfg = load_team_config(root_path, team_id)
        store = VerificationStore(root_path, team_id)
        questions = store.list_questions()
        return templates.TemplateResponse(
            request,
            "team_verification.html",
            {
                "user": user,
                "team_id": team_id,
                "team_name": cfg.team.name,
                "workflow": cfg.team.workflow,
                "is_verification": is_verification_team(root_path, team_id),
                "questions": questions,
                "summary": store.summary(),
                "phase": store.get_state("phase", "idle"),
            },
        )
