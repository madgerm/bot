"""FastAPI Web-Panel."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from bot.config import ConfigLoadError
from bot.health import collect_health
from bot.hosts import HostRegistry, TeamHostError
from bot.web.audit_middleware import PanelAuditMiddleware
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
from bot.web.csrf import CsrfMiddleware, csrf_enabled, ensure_csrf_token
from bot.web.rate_limit import client_key, login_rate_limiter, webhook_rate_limiter
from bot.web.team_access import require_team_write
from bot.web.template_helpers import register_template_globals, with_team_page

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def _team_chat_feed(
    root: Path,
    team_id: str,
    *,
    direct_agent: str | None,
    include_internal: bool,
    q: str | None,
):
    from bot.chat.team_feed import build_team_feed
    from bot.config.writers.team_admin import load_team_config

    orch_id = load_team_config(root, team_id).team.orchestrator_id
    feed = build_team_feed(
        root,
        team_id,
        orch_id,
        direct_agent=direct_agent,
        include_internal=include_internal,
    )
    if q and not direct_agent:
        q_lower = q.lower()
        feed = [
            ln
            for ln in feed
            if q_lower in ln.content.lower() or q_lower in ln.label.lower()
        ]
    return feed


def _team_chat_fragment_url(
    team_id: str,
    *,
    direct_agent: str | None,
    filter_q: str | None,
    show_internal: bool,
) -> str:
    from urllib.parse import urlencode

    params: dict[str, str] = {"show_internal": "1" if show_internal else "0"}
    if direct_agent:
        params["direct"] = direct_agent
    if filter_q:
        params["q"] = filter_q
    return f"/teams/{team_id}/chat/fragment?{urlencode(params)}"


def create_app(root: Path | str) -> FastAPI:
    root_path = Path(root).resolve()
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    def _csrf_for_request(request: Request) -> str:
        if not csrf_enabled():
            return ""
        return ensure_csrf_token(request)

    templates.env.globals["csrf_token_for"] = _csrf_for_request
    register_template_globals(templates, root_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from bot.channel.panel_connector import PanelChannelManager

        channel_mgr = PanelChannelManager(root_path)
        channel_mgr.start()
        app.state.channel_mgr = channel_mgr
        yield
        await channel_mgr.stop()

    app = FastAPI(title="Bot Panel", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(PanelAuditMiddleware, root=root_path)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret(),
        session_cookie="bot_session",
        https_only=False,
        same_site="lax",
    )
    app.state.login_limiter = login_rate_limiter()
    app.state.webhook_limiter = webhook_rate_limiter()
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
            {
                "user": None,
                "error": error,
                "csrf_token": ensure_csrf_token(request),
            },
        )

    @app.post("/login")
    async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        app.state.login_limiter.check(client_key(request, "login"))
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
        request.session["team_access"] = dict(user.team_access)
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
            with_team_page(
                root_path,
                team_id,
                {
                    "user": user,
                    "dashboard": dashboard,
                    "connection": client.connection_display(),
                    "host_label": client.label,
                },
                page="Übersicht",
            ),
        )

    def _team_chat_context(
        team_id: str,
        user: CurrentUser,
        *,
        direct: str | None,
        q: str | None,
        show_internal: str | None,
        agent: str | None = None,
    ) -> dict:
        from bot.chat.direct_agent import list_direct_agents
        from bot.config.writers.team_admin import load_team_config
        from bot.web.team_access import team_access_level

        require_team_access(team_id, user)
        cfg = load_team_config(root_path, team_id)
        orch_id = cfg.team.orchestrator_id
        direct_agent = (direct or "").strip() or None
        include_internal = show_internal != "0"
        feed = _team_chat_feed(
            root_path,
            team_id,
            direct_agent=direct_agent,
            include_internal=include_internal,
            q=q,
        )
        access = team_access_level(user, team_id)
        from bot.verification.workflow import is_verification_team

        return {
            "user": user,
            "team_id": team_id,
            "team_workflow": cfg.team.workflow,
            "is_verification_team": is_verification_team(root_path, team_id),
            "feed": feed,
            "filter_agent": agent,
            "filter_q": q,
            "can_write": access in ("admin", "operator"),
            "awaiting_approval": any(ln.awaiting_approval for ln in feed),
            "direct_agent": direct_agent,
            "orchestrator_id": orch_id,
            "agents_for_pm": list_direct_agents(root_path, team_id),
            "show_internal": include_internal,
            "feed_fragment_url": _team_chat_fragment_url(
                team_id,
                direct_agent=direct_agent,
                filter_q=q,
                show_internal=include_internal,
            ),
        }

    @app.get("/teams/{team_id}/chat", response_class=HTMLResponse)
    async def team_chat_page(
        request: Request,
        team_id: str,
        user: CurrentUser,
        agent: str | None = None,
        q: str | None = None,
        direct: str | None = None,
        show_internal: str | None = None,
    ):
        ctx = _team_chat_context(
            team_id, user, direct=direct, q=q, show_internal=show_internal, agent=agent
        )
        page = f"Direkt · {ctx['direct_agent']}" if ctx.get("direct_agent") else "Chat"
        return templates.TemplateResponse(
            request,
            "team_chat.html",
            with_team_page(root_path, team_id, ctx, page=page),
        )

    @app.get("/teams/{team_id}/chat/fragment", response_class=HTMLResponse)
    async def team_chat_feed_fragment(
        request: Request,
        team_id: str,
        user: CurrentUser,
        q: str | None = None,
        direct: str | None = None,
        show_internal: str | None = None,
    ):
        ctx = _team_chat_context(team_id, user, direct=direct, q=q, show_internal=show_internal)
        return templates.TemplateResponse(request, "team_chat_feed_fragment.html", ctx)

    @app.post("/teams/{team_id}/chat/send")
    async def team_chat_send(
        request: Request,
        team_id: str,
        user: CurrentUser,
        content: str = Form(...),
        role: str = Form("user"),
        agent_id: str | None = Form(None),
        direct: str = Form(""),
    ):
        from bot.web.team_access import require_team_write

        require_team_write(team_id, user)
        from bot.chat import ChatStore
        from bot.chat.direct_agent import send_direct_to_agent
        from bot.chat.orchestrator_bridge import enqueue_panel_chat
        from bot.config.writers.team_admin import load_team_config
        from bot.messages import MessageError

        direct_peer = direct.strip() or None
        if direct_peer:
            try:
                send_direct_to_agent(
                    root_path,
                    team_id,
                    username=user.username,
                    target_agent=direct_peer,
                    content=content,
                )
            except MessageError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return RedirectResponse(
                f"/teams/{team_id}/chat?direct={direct_peer}", status_code=302
            )

        store = ChatStore(root_path, team_id)
        orch_id = load_team_config(root_path, team_id).team.orchestrator_id
        chat_role = role if role in ("user", "assistant", "system", "tool") else "user"
        store.add(
            role=chat_role,  # type: ignore[arg-type]
            content=content,
            agent_id=agent_id or (orch_id if chat_role == "user" else None),
            metadata={"username": user.username} if chat_role == "user" else {},
        )
        if chat_role == "user":
            try:
                enqueue_panel_chat(
                    root_path,
                    team_id,
                    username=user.username,
                    content=content,
                    message_type="chat.user",
                )
            except MessageError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/chat", status_code=302)

    @app.post("/teams/{team_id}/chat/approve")
    async def team_chat_approve(request: Request, team_id: str, user: CurrentUser):
        from bot.web.team_access import require_team_write

        require_team_write(team_id, user)
        from bot.chat import ChatStore
        from bot.chat.orchestrator_bridge import enqueue_panel_chat
        from bot.config.writers.team_admin import load_team_config
        from bot.messages import MessageError

        orch_id = load_team_config(root_path, team_id).team.orchestrator_id
        store = ChatStore(root_path, team_id)
        store.add(
            role="user",
            content="Freigegeben — bitte an das Team delegieren.",
            agent_id=orch_id,
            metadata={"username": user.username, "approval": True},
        )
        try:
            enqueue_panel_chat(
                root_path,
                team_id,
                username=user.username,
                content="Freigegeben (so ist top)",
                message_type="chat.approve",
                subject="Chat-Freigabe",
            )
        except MessageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/chat?show_internal=1", status_code=302)

    @app.post("/teams/{team_id}/chat/delete")
    async def team_chat_delete(
        request: Request,
        team_id: str,
        user: CurrentUser,
        message_id: str = Form(...),
    ):
        from bot.web.team_access import require_team_write

        require_team_write(team_id, user)
        from bot.chat import ChatStore

        ChatStore(root_path, team_id).delete_message(message_id, actor=user.username)
        return RedirectResponse(f"/teams/{team_id}/chat", status_code=302)

    @app.post("/teams/{team_id}/chat/clear")
    async def team_chat_clear(
        request: Request,
        team_id: str,
        user: CurrentUser,
        confirm: str = Form(""),
    ):
        from bot.web.team_access import require_team_write

        require_team_write(team_id, user)
        if confirm != "CLEAR":
            raise HTTPException(status_code=400, detail="Bestätigung fehlt (CLEAR)")
        from bot.chat import ChatStore

        ChatStore(root_path, team_id).clear_all(actor=user.username)
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

    @app.get("/teams/{team_id}/mail", response_class=HTMLResponse)
    async def team_mail_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        from bot.mail.store import MailStore

        store = MailStore(root_path, team_id)
        threads = store.list_threads(limit=50)
        drafts = store.list_drafts(status="awaiting_approval", limit=20)
        mail_error: str | None = None
        return templates.TemplateResponse(
            request,
            "team_mail.html",
            {
                "user": user,
                "team_id": team_id,
                "threads": threads,
                "drafts": drafts,
                "mail_error": mail_error,
            },
        )

    @app.get("/teams/{team_id}/mail/{thread_id}", response_class=HTMLResponse)
    async def team_mail_thread_page(
        request: Request, team_id: str, thread_id: str, user: CurrentUser
    ):
        require_team_access(team_id, user)
        from bot.mail.store import MailStore

        store = MailStore(root_path, team_id)
        thread = store.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread nicht gefunden")
        incoming = store.get_incoming(thread_id)
        drafts = store.list_drafts(thread_id=thread_id)
        return templates.TemplateResponse(
            request,
            "team_mail_thread.html",
            {
                "user": user,
                "team_id": team_id,
                "thread": thread,
                "incoming": incoming,
                "drafts": drafts,
            },
        )

    @app.post("/teams/{team_id}/mail/{thread_id}/draft")
    async def team_mail_create_draft(
        request: Request,
        team_id: str,
        thread_id: str,
        user: CurrentUser,
        body_text: str = Form(...),
        to_addrs: str = Form(""),
        subject: str = Form(""),
    ):
        require_team_write(team_id, user)
        from bot.mail import MailService, MailServiceError

        recipients = [a.strip() for a in to_addrs.split(",") if a.strip()] or None
        try:
            service = MailService.for_team(root_path, team_id)
            service.create_reply_draft(
                thread_id,
                body_text=body_text,
                to_addrs=recipients,
                subject=subject or None,
                created_by=user.username,
            )
        except MailServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/mail/{thread_id}", status_code=302)

    @app.post("/teams/{team_id}/mail/draft/{draft_id}/approve")
    async def team_mail_approve(
        request: Request,
        team_id: str,
        draft_id: str,
        user: CurrentUser,
    ):
        require_team_write(team_id, user)
        from bot.mail import MailService, MailServiceError

        try:
            MailService.for_team(root_path, team_id).approve(draft_id, user.username)
        except MailServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(request.headers.get("referer", f"/teams/{team_id}/mail"), status_code=302)

    @app.post("/teams/{team_id}/mail/draft/{draft_id}/send")
    async def team_mail_send(
        request: Request,
        team_id: str,
        draft_id: str,
        user: CurrentUser,
        confirm: str = Form(""),
    ):
        require_team_write(team_id, user)
        if confirm != "SEND":
            raise HTTPException(status_code=400, detail="Bestätigung SEND fehlt")
        from bot.mail import MailService, MailServiceError

        try:
            MailService.for_team(root_path, team_id).send_approved(draft_id)
        except MailServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(request.headers.get("referer", f"/teams/{team_id}/mail"), status_code=302)

    @app.get("/teams/{team_id}/hours", response_class=HTMLResponse)
    async def team_hours_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        hours_error: str | None = None
        master = None
        diffs = []
        try:
            from bot.hours import HoursService

            service = HoursService.for_team(root_path, team_id)
            master = service.get_master()
            diffs = service.store.list_diffs(limit=10)
        except Exception as exc:
            hours_error = str(exc)
        import json as _json

        master_json = (
            _json.dumps(master.normalized(), indent=2, ensure_ascii=False)
            if master
            else None
        )
        return templates.TemplateResponse(
            request,
            "team_hours.html",
            {
                "user": user,
                "team_id": team_id,
                "master_json": master_json,
                "diffs": diffs,
                "hours_error": hours_error,
            },
        )

    @app.post("/teams/{team_id}/hours/check")
    async def team_hours_check(request: Request, team_id: str, user: CurrentUser):
        require_team_write(team_id, user)
        from bot.hours import HoursService, HoursServiceError

        try:
            from bot.config import ConfigStore
            from bot.llm import build_llm_stack

            stack = build_llm_stack(ConfigStore(root_path).get())
            HoursService.for_team(root_path, team_id).check(llm_stack=stack)
        except HoursServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/hours", status_code=302)

    @app.post("/teams/{team_id}/hours/diff/{diff_id}/approve")
    async def team_hours_approve(
        request: Request, team_id: str, diff_id: str, user: CurrentUser
    ):
        require_team_write(team_id, user)
        from bot.hours import HoursService, HoursServiceError

        try:
            HoursService.for_team(root_path, team_id).approve(diff_id, user.username)
        except HoursServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/hours", status_code=302)

    @app.post("/teams/{team_id}/hours/diff/{diff_id}/publish")
    async def team_hours_publish(
        request: Request,
        team_id: str,
        diff_id: str,
        user: CurrentUser,
        confirm: str = Form(""),
    ):
        require_team_write(team_id, user)
        if confirm != "PUBLISH":
            raise HTTPException(status_code=400, detail="Bestätigung PUBLISH fehlt")
        from bot.hours import HoursService, HoursServiceError

        try:
            HoursService.for_team(root_path, team_id).publish(diff_id)
        except HoursServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/hours", status_code=302)

    @app.get("/admin/media", response_class=HTMLResponse)
    async def admin_media_page(request: Request, user: CurrentUser, saved: str | None = None):
        require_admin(user)
        from bot.config.media_admin import MediaAdminError, load_media_global
        from bot.media import MediaService

        try:
            media = load_media_global(root_path)
        except MediaAdminError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        registry: HostRegistry = app.state.hosts
        teams = registry.list_teams_for_user(None, is_admin=True)
        team_rows = []
        for t in teams:
            tid = t["id"]
            try:
                status = MediaService.for_team(root_path, tid).channel_status()
            except Exception:
                status = {
                    ch: {"mode": "stub", "source": "?", "detail": "—"}
                    for ch in ("vision", "stt", "tts", "image_generation")
                }
            team_rows.append({"team_id": tid, "status": status})
        return templates.TemplateResponse(
            request,
            "admin_media.html",
            {
                "user": user,
                "media": media,
                "team_rows": team_rows,
                "saved": saved == "1",
            },
        )

    @app.post("/admin/media/global")
    async def admin_media_global_save(
        request: Request,
        user: CurrentUser,
        vision_model: str = Form("gpt-4o-mini"),
        stt_endpoint: str = Form(""),
        tts_endpoint: str = Form(""),
        tts_voice_id: str = Form("de_DE_neural"),
        image_type: str = Form("webhook"),
        image_url: str = Form(""),
    ):
        require_admin(user)
        from bot.config.media_admin import (
            MediaAdminError,
            media_global_from_form,
            save_media_global,
        )

        try:
            media = media_global_from_form(
                stt_endpoint=stt_endpoint,
                tts_endpoint=tts_endpoint,
                tts_voice_id=tts_voice_id,
                image_type=image_type,
                image_url=image_url,
                vision_model=vision_model,
            )
            save_media_global(root_path, media)
        except MediaAdminError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse("/admin/media?saved=1", status_code=302)

    @app.post("/admin/media/team/{team_id}")
    async def admin_media_team_save(
        request: Request,
        team_id: str,
        user: CurrentUser,
        image_url: str = Form(""),
    ):
        require_admin(user)
        from bot.config.media_admin import save_team_media_file
        from bot.config.models import ImageGenerationConfig
        from bot.media.config import MediaChannelConfig, TeamMediaConfig

        media = TeamMediaConfig(
            vision=MediaChannelConfig(source="global"),
            stt=MediaChannelConfig(source="global"),
            tts=MediaChannelConfig(source="global"),
            image_generation=ImageGenerationConfig(
                source="custom",
                type="webhook",
                url=image_url or None,
            ),
        )
        save_team_media_file(root_path, team_id, media)
        return RedirectResponse("/admin/media?saved=1", status_code=302)

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_page(request: Request, user: CurrentUser):
        require_admin(user)
        from bot.audit import AuditStore

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
        from bot.media import MediaService

        media_status: dict[str, dict[str, str]] = {}
        if teams:
            try:
                media_status = MediaService.for_team(
                    root_path, teams[0]["id"]
                ).channel_status()
            except Exception:
                pass
        audit_log = AuditStore(root_path).list_entries(limit=40)
        return templates.TemplateResponse(
            request,
            "admin.html",
            {
                "user": user,
                "users": safe_users,
                "teams": teams,
                "hosts": registry.list_hosts(),
                "audit_log": audit_log,
                "media_status": media_status,
                "media_status_team": teams[0]["id"] if teams else None,
            },
        )

    @app.get("/health")
    async def health():
        return collect_health(root_path)

    # Phase 3: Webhooks API
    from bot.webhooks import WebhookService, WebhookServiceError

    @app.post("/api/v1/webhooks/{team_id}/{agent_id}")
    async def webhook_ingest(
        request: Request,
        team_id: str,
        agent_id: str,
    ):
        import json as _json

        app.state.webhook_limiter.check(client_key(request, f"webhook:{team_id}"))
        body = await request.body()
        wh = WebhookService(root_path)
        token = request.headers.get("X-Webhook-Token")
        sig = request.headers.get("X-Webhook-Signature")
        if not wh.verify_token(token) and not wh.verify_signature(body, sig):
            raise HTTPException(status_code=401, detail="Webhook nicht autorisiert")
        try:
            payload = _json.loads(body)
        except _json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Ungültiges JSON") from exc
        try:
            result = wh.ingest(
                team_id=team_id,
                to_agent=agent_id,
                subject=payload.get("subject", "Webhook"),
                content=payload.get("content", ""),
                from_agent=payload.get("from_agent", "webhook"),
                type=payload.get("type", "task"),
                task_category=payload.get("task_category"),
                metadata=payload.get("metadata"),
            )
        except WebhookServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result

    @app.post("/api/v1/integrations/{team_id}/telegram")
    async def telegram_webhook(request: Request, team_id: str):
        from bot.integrations import IntegrationService, IntegrationServiceError

        update = await request.json()
        try:
            return IntegrationService.for_team(root_path, team_id).handle_telegram_update(
                update
            )
        except IntegrationServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/integrations/{team_id}/matrix")
    async def matrix_webhook(request: Request, team_id: str):
        from bot.integrations import IntegrationService, IntegrationServiceError

        event = await request.json()
        try:
            return IntegrationService.for_team(root_path, team_id).handle_matrix_event(
                event
            )
        except IntegrationServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    from bot.web.llm_proxy_routes import register_llm_proxy_routes
    from bot.web.routes_phase3 import register_phase3_routes
    from bot.web.settings_routes import register_settings_routes

    register_llm_proxy_routes(app, root_path)
    register_phase3_routes(app, templates, root_path)
    register_settings_routes(app, templates, root_path)
    from bot.web.team_settings_routes import register_team_settings_routes

    register_team_settings_routes(app, templates, root_path)
    from bot.web.verification_routes import register_verification_routes

    register_verification_routes(app, templates, root_path)

    return app
