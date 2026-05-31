"""Team anlegen (Dashboard) und umbenennen (Team-Seite)."""

from __future__ import annotations

from pathlib import Path

from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.config.writers.hosts_admin import HostsAdminError, append_team_to_local_host
from bot.config.writers.team_admin import TeamAdminError, create_team, save_team_name
from bot.web.auth import CurrentUser, require_admin
from bot.web.team_access import require_team_write, team_access_level


def register_team_manage_routes(
    app, templates: Jinja2Templates, root_path: Path
) -> None:
    from bot.web.auth import require_team_access

    @app.get("/dashboard/teams/new", response_class=HTMLResponse)
    async def dashboard_team_new(request: Request, user: CurrentUser):
        require_admin(user)
        return templates.TemplateResponse(
            request,
            "team_new.html",
            {"user": user},
        )

    @app.post("/dashboard/teams/create")
    async def dashboard_team_create(
        request: Request,
        user: CurrentUser,
        team_id: str = Form(...),
        name: str = Form(...),
        preset: str = Form("generic"),
        workflow: str = Form("tasks"),
    ):
        require_admin(user)
        preset_val = preset if preset in ("generic", "demo", "coding", "story") else "generic"
        workflow_val = workflow if workflow in ("tasks", "verification") else "tasks"
        try:
            create_team(
                root_path,
                team_id,
                actor=user.username,
                name=name,
                preset=preset_val,  # type: ignore[arg-type]
                workflow=workflow_val,  # type: ignore[arg-type]
            )
            append_team_to_local_host(root_path, team_id.strip().lower(), actor=user.username)
        except (TeamAdminError, HostsAdminError) as exc:
            return templates.TemplateResponse(
                request,
                "team_new.html",
                {"user": user, "error": str(exc), "team_id": team_id, "name": name},
                status_code=400,
            )
        tid = team_id.strip().lower()
        return RedirectResponse(f"/teams/{tid}", status_code=302)

    @app.post("/teams/{team_id}/rename")
    async def team_rename(
        request: Request,
        team_id: str,
        user: CurrentUser,
        name: str = Form(...),
    ):
        require_team_write(team_id, user)
        try:
            save_team_name(root_path, team_id, actor=user.username, name=name)
        except TeamAdminError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}?renamed=1", status_code=302)
