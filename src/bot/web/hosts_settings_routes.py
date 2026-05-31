"""Team-Hosts, Wizard und Status (/admin/settings/hosts, /status)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.config.writers.hosts_admin import (
    HostsAdminError,
    TeamApiAdminConfig,
    create_host,
    delete_host,
    entry_from_form,
    generate_team_token,
    get_host,
    load_hosts_admin,
    load_team_api_admin,
    probe_host_connection,
    save_team_api_admin,
    update_host,
)
from bot.config.writers.users_admin import list_known_team_ids
from bot.web.auth import CurrentUser, require_admin


def _form_dict(form) -> dict[str, str]:
    return {k: str(form[k]) for k in form.keys()}


def register_hosts_settings_routes(
    app,
    templates: Jinja2Templates,
    root_path: Path,
) -> None:
    def _teams() -> list[str]:
        return list_known_team_ids(root_path)

    @app.get("/admin/settings/hosts", response_class=HTMLResponse)
    async def hosts_list(
        request: Request,
        user: CurrentUser,
        saved: str | None = None,
        test: str | None = None,
        ok: str | None = None,
    ):
        require_admin(user)
        cfg = load_hosts_admin(root_path)
        api_cfg = load_team_api_admin(root_path)
        return templates.TemplateResponse(
            request,
            "admin_settings_hosts.html",
            {
                "user": user,
                "hosts": cfg.hosts,
                "team_api": api_cfg,
                "team_ids": _teams(),
                "saved": saved,
                "test_host": test,
                "test_ok": ok == "1",
                "settings_active": "hosts",
            },
        )

    @app.get("/admin/settings/hosts/new", response_class=HTMLResponse)
    async def hosts_new_form(request: Request, user: CurrentUser):
        require_admin(user)
        team_ids = _teams()
        return templates.TemplateResponse(
            request,
            "admin_settings_host_form.html",
            {
                "user": user,
                "mode": "create",
                "entry": None,
                "team_ids": team_ids,
                "selected_teams": [],
                "error": None,
                "settings_active": "hosts",
            },
        )

    @app.post("/admin/settings/hosts/new")
    async def hosts_create(request: Request, user: CurrentUser):
        require_admin(user)
        form = _form_dict(await request.form())
        team_ids = _teams()
        try:
            entry = entry_from_form(form, team_ids=team_ids)
            create_host(root_path, entry, actor=user.username)
        except HostsAdminError as exc:
            return templates.TemplateResponse(
                request,
                "admin_settings_host_form.html",
                {
                    "user": user,
                    "mode": "create",
                    "entry": None,
                    "team_ids": team_ids,
                    "selected_teams": [],
                    "error": str(exc),
                    "form": form,
                    "settings_active": "hosts",
                },
                status_code=400,
            )
        return RedirectResponse("/admin/settings/hosts?saved=created", status_code=302)

    @app.post("/admin/settings/hosts/team-api")
    async def hosts_save_team_api(
        request: Request,
        user: CurrentUser,
        token_env: str = Form("BOT_TEAM_API_TOKEN"),
    ):
        require_admin(user)
        form = await request.form()
        team_ids = _teams()
        teams = [
            tid for tid in team_ids if form.get(f"api_team_{tid}") == "on"
        ]
        try:
            save_team_api_admin(
                root_path,
                TeamApiAdminConfig(
                    token_env=token_env.strip() or "BOT_TEAM_API_TOKEN",
                    teams=teams,
                ),
                actor=user.username,
            )
        except HostsAdminError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse("/admin/settings/hosts?saved=team_api", status_code=302)

    @app.get("/admin/settings/hosts/wizard", response_class=HTMLResponse)
    async def hosts_wizard_page(request: Request, user: CurrentUser):
        require_admin(user)
        return templates.TemplateResponse(
            request,
            "admin_settings_hosts_wizard.html",
            {
                "user": user,
                "team_ids": _teams(),
                "error": None,
                "result": None,
                "settings_active": "hosts",
            },
        )

    @app.post("/admin/settings/hosts/wizard", response_class=HTMLResponse)
    async def hosts_wizard_apply(request: Request, user: CurrentUser):
        require_admin(user)
        form = _form_dict(await request.form())
        team_ids = _teams()
        setup = form.get("setup", "local")
        if setup == "remote_channel":
            form["mode"] = "remote"
            form["channel"] = "on"
        elif setup == "remote_relay":
            form["mode"] = "remote"
            form["channel"] = "on"
        elif setup == "remote":
            form["mode"] = "remote"
        else:
            form["mode"] = "local"
        if not form.get("token_env"):
            form["token_env"] = "BOT_TEAM_API_TOKEN"
        token = generate_team_token()
        try:
            entry = entry_from_form(form, team_ids=team_ids)
            cfg = load_hosts_admin(root_path)
            if get_host(cfg, entry.id):
                update_host(root_path, entry.id, entry, actor=user.username)
            else:
                create_host(root_path, entry, actor=user.username)
            if entry.mode == "remote":
                api_teams = sorted(set(load_team_api_admin(root_path).teams) | set(entry.teams))
                save_team_api_admin(
                    root_path,
                    TeamApiAdminConfig(
                        token_env=form["token_env"],
                        teams=api_teams,
                    ),
                    actor=user.username,
                )
        except HostsAdminError as exc:
            return templates.TemplateResponse(
                request,
                "admin_settings_hosts_wizard.html",
                {
                    "user": user,
                    "team_ids": team_ids,
                    "error": str(exc),
                    "result": None,
                    "form": form,
                    "settings_active": "hosts",
                },
                status_code=400,
            )
        env_name = form.get("token_env", "BOT_TEAM_API_TOKEN")
        panel_env = f"{env_name}={token}"
        runner_env = panel_env
        return templates.TemplateResponse(
            request,
            "admin_settings_hosts_wizard.html",
            {
                "user": user,
                "team_ids": team_ids,
                "error": None,
                "result": {
                    "host_id": entry.id,
                    "mode": entry.mode,
                    "token": token,
                    "env_name": env_name,
                    "panel_env": panel_env,
                    "runner_env": runner_env,
                    "host_json_display": json.dumps(
                        entry.model_dump(mode="json", exclude_none=True),
                        indent=2,
                        ensure_ascii=False,
                    ),
                },
                "settings_active": "hosts",
            },
        )

    @app.get("/admin/settings/hosts/{host_id}", response_class=HTMLResponse)
    async def hosts_edit_form(request: Request, host_id: str, user: CurrentUser):
        require_admin(user)
        cfg = load_hosts_admin(root_path)
        entry = get_host(cfg, host_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Host nicht gefunden")
        team_ids = sorted(set(_teams()) | set(entry.teams))
        return templates.TemplateResponse(
            request,
            "admin_settings_host_form.html",
            {
                "user": user,
                "mode": "edit",
                "entry": entry,
                "team_ids": team_ids,
                "selected_teams": entry.teams,
                "error": None,
                "settings_active": "hosts",
            },
        )

    @app.post("/admin/settings/hosts/{host_id}")
    async def hosts_update(request: Request, host_id: str, user: CurrentUser):
        require_admin(user)
        form = _form_dict(await request.form())
        team_ids = sorted(set(_teams()))
        try:
            entry = entry_from_form(form, team_ids=team_ids, host_id=host_id)
            update_host(root_path, host_id, entry, actor=user.username)
        except HostsAdminError as exc:
            cfg = load_hosts_admin(root_path)
            entry = get_host(cfg, host_id)
            return templates.TemplateResponse(
                request,
                "admin_settings_host_form.html",
                {
                    "user": user,
                    "mode": "edit",
                    "entry": entry,
                    "team_ids": team_ids,
                    "selected_teams": entry.teams if entry else [],
                    "error": str(exc),
                    "form": form,
                    "settings_active": "hosts",
                },
                status_code=400,
            )
        return RedirectResponse("/admin/settings/hosts?saved=updated", status_code=302)

    @app.post("/admin/settings/hosts/{host_id}/delete")
    async def hosts_delete(host_id: str, user: CurrentUser):
        require_admin(user)
        try:
            delete_host(root_path, host_id, actor=user.username)
        except HostsAdminError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse("/admin/settings/hosts?saved=deleted", status_code=302)

    @app.post("/admin/settings/hosts/{host_id}/test")
    async def hosts_test(host_id: str, user: CurrentUser):
        require_admin(user)
        cfg = load_hosts_admin(root_path)
        entry = get_host(cfg, host_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Host nicht gefunden")
        result = probe_host_connection(root_path, entry)
        flag = "1" if result.get("ok") else "0"
        return RedirectResponse(
            f"/admin/settings/hosts?test={host_id}&ok={flag}",
            status_code=302,
        )
