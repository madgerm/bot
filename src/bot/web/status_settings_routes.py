"""HTMX-Fragmente für /admin/settings/status (Live-Verbindungstests)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from bot.config.writers.hosts_admin import (
    HostsAdminError,
    collect_settings_status,
    load_hosts_admin,
    load_team_api_admin,
    probe_host_connection,
    probe_llm,
    probe_llm_http,
    probe_llm_live,
    probe_qdrant,
)
from bot.config.writers.system_admin import env_var_is_set
from bot.web.auth import CurrentUser, require_admin


def _host_row(root: Path, entry) -> dict:
    probe = probe_host_connection(root, entry)
    return {
        "id": entry.id,
        "label": entry.label,
        "mode": entry.mode,
        "teams": entry.teams,
        "channel": entry.channel,
        "connection": entry.base_url or f"lokal ({root})",
        **probe,
    }


def register_status_settings_routes(
    app,
    templates: Jinja2Templates,
    root_path: Path,
) -> None:
    def _fragment_ctx(status: dict, *, tested_at: str | None = None) -> dict:
        return {
            "status": status,
            "tested_at": tested_at or datetime.now(UTC).strftime("%H:%M:%S UTC"),
        }

    @app.get("/admin/settings/status/fragment", response_class=HTMLResponse)
    async def status_fragment_all(
        request: Request,
        user: CurrentUser,
        live_llm: bool = Query(False),
    ):
        require_admin(user)
        try:
            status = collect_settings_status(root_path, live_llm=live_llm)
        except HostsAdminError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return templates.TemplateResponse(
            request,
            "admin_settings_status_fragment.html",
            _fragment_ctx(status),
        )

    @app.get("/admin/settings/status/fragment/hosts", response_class=HTMLResponse)
    async def status_fragment_hosts(request: Request, user: CurrentUser):
        require_admin(user)
        try:
            cfg = load_hosts_admin(root_path)
            hosts = [_host_row(root_path, e) for e in cfg.hosts]
            channel_hosts = [
                h.id for h in cfg.hosts if h.mode == "remote" and h.channel
            ]
        except HostsAdminError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return templates.TemplateResponse(
            request,
            "admin_settings_status_hosts_fragment.html",
            {
                "hosts": hosts,
                "channel_hosts": channel_hosts,
                "tested_at": datetime.now(UTC).strftime("%H:%M:%S UTC"),
            },
        )

    @app.get(
        "/admin/settings/status/fragment/hosts/{host_id}",
        response_class=HTMLResponse,
    )
    async def status_fragment_host(
        request: Request, host_id: str, user: CurrentUser
    ):
        require_admin(user)
        try:
            cfg = load_hosts_admin(root_path)
        except HostsAdminError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        entry = next((h for h in cfg.hosts if h.id == host_id), None)
        if entry is None:
            raise HTTPException(status_code=404, detail="Host nicht gefunden")
        host = _host_row(root_path, entry)
        return templates.TemplateResponse(
            request,
            "admin_settings_status_host_card.html",
            {"h": host, "tested_at": datetime.now(UTC).strftime("%H:%M:%S UTC")},
        )

    @app.get("/admin/settings/status/fragment/llm", response_class=HTMLResponse)
    async def status_fragment_llm(
        request: Request,
        user: CurrentUser,
        live: bool = Query(False),
        ping: bool = Query(False),
    ):
        require_admin(user)
        try:
            if live:
                llm = probe_llm_live(root_path)
            elif ping:
                llm = probe_llm_http(root_path)
            else:
                llm = probe_llm(root_path)
        except Exception as exc:
            llm = {"ok": False, "summary": str(exc)}
        return templates.TemplateResponse(
            request,
            "admin_settings_status_llm_fragment.html",
            {
                "llm": llm,
                "live": live,
                "ping": ping,
                "tested_at": datetime.now(UTC).strftime("%H:%M:%S UTC"),
            },
        )

    @app.get("/admin/settings/status/fragment/qdrant", response_class=HTMLResponse)
    async def status_fragment_qdrant(request: Request, user: CurrentUser):
        require_admin(user)
        try:
            qdrant = probe_qdrant(root_path)
        except Exception as exc:
            qdrant = {"ok": False, "summary": str(exc)}
        return templates.TemplateResponse(
            request,
            "admin_settings_status_qdrant_fragment.html",
            {
                "qdrant": qdrant,
                "tested_at": datetime.now(UTC).strftime("%H:%M:%S UTC"),
            },
        )

    @app.get(
        "/admin/settings/status/fragment/team-api",
        response_class=HTMLResponse,
    )
    async def status_fragment_team_api(request: Request, user: CurrentUser):
        require_admin(user)
        try:
            api_cfg = load_team_api_admin(root_path)
        except HostsAdminError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        team_api = {
            "token_env": api_cfg.token_env,
            "token_set": env_var_is_set(api_cfg.token_env),
            "teams": api_cfg.teams,
        }
        return templates.TemplateResponse(
            request,
            "admin_settings_status_team_api_fragment.html",
            {
                "team_api": team_api,
                "tested_at": datetime.now(UTC).strftime("%H:%M:%S UTC"),
            },
        )

    @app.get("/admin/settings/status", response_class=HTMLResponse)
    async def settings_status_page_shell(request: Request, user: CurrentUser):
        """Status-Seite: Inhalt per HTMX nach Laden."""
        require_admin(user)
        return templates.TemplateResponse(
            request,
            "admin_settings_status.html",
            {
                "user": user,
                "settings_active": "status",
            },
        )
