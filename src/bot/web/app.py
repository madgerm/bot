"""FastAPI Web-Panel."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from bot.config import ConfigLoadError, load_runtime_config
from bot.web.auth import (
    SESSION_ROLE_KEY,
    SESSION_TEAMS_KEY,
    SESSION_USER_KEY,
    CurrentUser,
    authenticate,
    get_optional_user,
    load_users_config,
    require_admin,
    require_team_access,
    session_secret,
)
from bot.hosts import HostRegistry, TeamHostError
from bot.web.services import build_team_dashboard

TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(root: Path | str) -> FastAPI:
    root_path = Path(root).resolve()
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app = FastAPI(title="Bot Panel", docs_url="/api/docs", redoc_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret(),
        session_cookie="bot_session",
        https_only=False,
        same_site="lax",
    )
    app.state.root = root_path
    try:
        app.state.hosts = HostRegistry(root_path)
    except TeamHostError as exc:
        raise RuntimeError(str(exc)) from exc

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        user = get_optional_user(request)
        if user:
            return RedirectResponse("/dashboard", status_code=302)
        return RedirectResponse("/login", status_code=302)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, error: str | None = None):
        if get_optional_user(request):
            return RedirectResponse("/dashboard", status_code=302)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"user": None, "error": error},
        )

    @app.post("/login")
    async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        user = authenticate(root_path, username.strip(), password)
        if user is None:
            return templates.TemplateResponse(
                request,
                "login.html",
                {"user": None, "error": "Ungültige Anmeldedaten"},
                status_code=401,
            )
        request.session[SESSION_USER_KEY] = user.username
        request.session[SESSION_ROLE_KEY] = user.role
        request.session[SESSION_TEAMS_KEY] = user.teams
        return RedirectResponse("/dashboard", status_code=302)

    @app.post("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=302)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request, user: CurrentUser):
        registry: HostRegistry = app.state.hosts
        try:
            teams = registry.list_teams_for_user(
                user.teams,
                is_admin=user.role == "admin",
            )
            system_name = registry.system_name()
        except (ConfigLoadError, TeamHostError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "system_name": system_name,
                "teams": teams,
            },
        )

    @app.get("/teams/{team_id}", response_class=HTMLResponse)
    async def team_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        registry: HostRegistry = app.state.hosts
        client = registry.client_for_team(team_id)
        try:
            dashboard = client.get_dashboard(team_id)
        except (ConfigLoadError, TeamHostError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return templates.TemplateResponse(
            request,
            "team.html",
            {
                "user": user,
                "dashboard": dashboard,
                "connection": client.connection_display(),
                "host_label": client.label,
            },
        )

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_page(request: Request, user: CurrentUser):
        require_admin(user)
        users_cfg = load_users_config(root_path)
        registry: HostRegistry = app.state.hosts
        try:
            teams = registry.list_teams_for_user(None, is_admin=True)
        except (ConfigLoadError, TeamHostError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        safe_users = [
            {"username": u.username, "role": u.role, "teams": u.teams}
            for u in users_cfg.users
        ]
        return templates.TemplateResponse(
            request,
            "admin.html",
            {
                "user": user,
                "users": safe_users,
                "teams": teams,
                "hosts": registry.list_hosts(),
            },
        )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
