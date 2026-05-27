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
                "team_id": team_id,
                "connection": client.connection_display(),
                "host_label": client.label,
            },
        )

    @app.get("/teams/{team_id}/chat", response_class=HTMLResponse)
    async def team_chat_page(
        request: Request,
        team_id: str,
        user: CurrentUser,
        agent: str | None = None,
        q: str | None = None,
    ):
        require_team_access(team_id, user)
        from bot.chat import ChatStore

        store = ChatStore(root_path, team_id)
        messages = store.list_messages(agent_id=agent, search=q, limit=100)
        return templates.TemplateResponse(
            request,
            "team_chat.html",
            {
                "user": user,
                "team_id": team_id,
                "messages": messages,
                "filter_agent": agent,
                "filter_q": q,
            },
        )

    @app.post("/teams/{team_id}/chat/send")
    async def team_chat_send(
        request: Request,
        team_id: str,
        user: CurrentUser,
        content: str = Form(...),
        role: str = Form("user"),
        agent_id: str | None = Form(None),
    ):
        require_team_access(team_id, user)
        from bot.chat import ChatStore

        store = ChatStore(root_path, team_id)
        store.add(role=role, content=content, agent_id=agent_id or None)  # type: ignore[arg-type]
        return RedirectResponse(f"/teams/{team_id}/chat", status_code=302)

    @app.post("/teams/{team_id}/chat/clear")
    async def team_chat_clear(
        request: Request,
        team_id: str,
        user: CurrentUser,
        confirm: str = Form(""),
    ):
        require_team_access(team_id, user)
        if confirm != "CLEAR":
            raise HTTPException(status_code=400, detail="Bestätigung fehlt (CLEAR)")
        from bot.chat import ChatStore

        ChatStore(root_path, team_id).clear_all()
        return RedirectResponse(f"/teams/{team_id}/chat", status_code=302)

    @app.get("/teams/{team_id}/knowledge", response_class=HTMLResponse)
    async def team_knowledge_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        collections: dict[str, str] = {}
        qdrant_error: str | None = None
        try:
            from bot.qdrant.collections import load_registry

            collections = load_registry(root_path, team_id)
        except Exception as exc:
            qdrant_error = str(exc)
        return templates.TemplateResponse(
            request,
            "team_knowledge.html",
            {
                "user": user,
                "team_id": team_id,
                "collections": collections,
                "qdrant_error": qdrant_error,
                "results": None,
                "query": "",
            },
        )

    @app.post("/teams/{team_id}/knowledge/search", response_class=HTMLResponse)
    async def team_knowledge_search(
        request: Request,
        team_id: str,
        user: CurrentUser,
        query: str = Form(...),
        collection: str = Form("project"),
    ):
        require_team_access(team_id, user)
        from bot.qdrant import QdrantService, QdrantServiceError
        from bot.qdrant.collections import load_registry

        results = None
        qdrant_error: str | None = None
        try:
            service = QdrantService.from_root(root_path)
            results = service.search(team_id, collection, query, limit=8)
            collections = load_registry(root_path, team_id)
        except Exception as exc:
            if isinstance(exc, QdrantServiceError):
                qdrant_error = str(exc)
            else:
                qdrant_error = str(exc)
            collections = {}
        return templates.TemplateResponse(
            request,
            "team_knowledge.html",
            {
                "user": user,
                "team_id": team_id,
                "collections": collections,
                "qdrant_error": qdrant_error,
                "results": results,
                "query": query,
                "collection": collection,
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
