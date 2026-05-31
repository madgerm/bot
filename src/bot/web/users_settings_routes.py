"""Nutzer-Verwaltung unter /admin/settings/users."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.config.writers.users_admin import (
    UsersAdminError,
    create_user,
    delete_user,
    get_user,
    list_known_team_ids,
    load_users_config,
    team_access_levels_for_user,
    update_user,
)
from bot.web.auth import CurrentUser, require_admin


def _parse_team_levels(form, team_ids: list[str]) -> dict[str, str]:
    levels: dict[str, str] = {}
    for tid in team_ids:
        raw = form.get(f"access_{tid}", "none")
        if raw in ("none", "reader", "operator"):
            levels[tid] = raw
        else:
            levels[tid] = "none"
    return levels


def register_users_settings_routes(
    app,
    templates: Jinja2Templates,
    root_path: Path,
) -> None:
    def _teams() -> list[str]:
        return list_known_team_ids(root_path)

    @app.get("/admin/settings/users", response_class=HTMLResponse)
    async def users_list(request: Request, user: CurrentUser, saved: str | None = None):
        require_admin(user)
        cfg = load_users_config(root_path)
        rows = [
            {
                "username": u.username,
                "role": u.role,
                "enabled": u.enabled,
                "teams": u.teams,
                "team_access": u.team_access,
                "is_self": u.username == user.username,
            }
            for u in cfg.users
        ]
        return templates.TemplateResponse(
            request,
            "admin_settings_users.html",
            {
                "user": user,
                "users": rows,
                "saved": saved,
                "settings_active": "users",
            },
        )

    @app.get("/admin/settings/users/new", response_class=HTMLResponse)
    async def users_new_form(request: Request, user: CurrentUser):
        require_admin(user)
        team_ids = _teams()
        return templates.TemplateResponse(
            request,
            "admin_settings_user_form.html",
            {
                "user": user,
                "mode": "create",
                "record": None,
                "team_ids": team_ids,
                "team_levels": {tid: "none" for tid in team_ids},
                "error": None,
                "settings_active": "users",
            },
        )

    @app.get("/admin/settings/users/{username}", response_class=HTMLResponse)
    async def users_edit_form(request: Request, username: str, user: CurrentUser):
        require_admin(user)
        cfg = load_users_config(root_path)
        record = get_user(cfg, username)
        if record is None:
            raise HTTPException(status_code=404, detail="Nutzer nicht gefunden")
        team_ids = sorted(set(_teams()) | set(record.teams) | {e.team_id for e in record.team_access})
        return templates.TemplateResponse(
            request,
            "admin_settings_user_form.html",
            {
                "user": user,
                "mode": "edit",
                "record": record,
                "team_ids": team_ids,
                "team_levels": team_access_levels_for_user(record, team_ids),
                "error": None,
                "is_self": record.username == user.username,
                "settings_active": "users",
            },
        )

    @app.post("/admin/settings/users/create")
    async def users_create(
        request: Request,
        user: CurrentUser,
        username: str = Form(...),
        password: str = Form(...),
        password_confirm: str = Form(...),
        role: Literal["admin", "user"] = Form("user"),
        enabled: str | None = Form(None),
    ):
        require_admin(user)
        form = await request.form()
        team_ids = _teams()
        if password != password_confirm:
            return templates.TemplateResponse(
                request,
                "admin_settings_user_form.html",
                {
                    "user": user,
                    "mode": "create",
                    "record": None,
                    "team_ids": team_ids,
                    "team_levels": _parse_team_levels(form, team_ids),
                    "error": "Passwörter stimmen nicht überein.",
                    "settings_active": "users",
                    "form_username": username.strip(),
                    "form_role": role,
                    "form_enabled": enabled == "on",
                },
                status_code=400,
            )
        try:
            create_user(
                root_path,
                username=username.strip(),
                password_plain=password,
                role=role,
                team_levels=_parse_team_levels(form, team_ids),
                enabled=enabled == "on",
                actor=user.username,
            )
        except UsersAdminError as exc:
            return templates.TemplateResponse(
                request,
                "admin_settings_user_form.html",
                {
                    "user": user,
                    "mode": "create",
                    "record": None,
                    "team_ids": team_ids,
                    "team_levels": _parse_team_levels(form, team_ids),
                    "error": str(exc),
                    "settings_active": "users",
                    "form_username": username.strip(),
                    "form_role": role,
                    "form_enabled": enabled == "on",
                },
                status_code=400,
            )
        return RedirectResponse("/admin/settings/users?saved=created", status_code=302)

    @app.post("/admin/settings/users/{username}/save")
    async def users_save(
        request: Request,
        username: str,
        user: CurrentUser,
        role: Literal["admin", "user"] = Form("user"),
        enabled: str | None = Form(None),
        password: str = Form(""),
        password_confirm: str = Form(""),
    ):
        require_admin(user)
        form = await request.form()
        cfg = load_users_config(root_path)
        record = get_user(cfg, username)
        if record is None:
            raise HTTPException(status_code=404, detail="Nutzer nicht gefunden")
        team_ids = sorted(set(_teams()) | set(record.teams) | {e.team_id for e in record.team_access})
        pwd = password.strip()
        pwd_confirm = password_confirm.strip()
        if pwd or pwd_confirm:
            if pwd != pwd_confirm:
                return templates.TemplateResponse(
                    request,
                    "admin_settings_user_form.html",
                    {
                        "user": user,
                        "mode": "edit",
                        "record": record,
                        "team_ids": team_ids,
                        "team_levels": _parse_team_levels(form, team_ids),
                        "error": "Passwörter stimmen nicht überein.",
                        "is_self": record.username == user.username,
                        "settings_active": "users",
                    },
                    status_code=400,
                )
        else:
            pwd = None
        try:
            update_user(
                root_path,
                username=username,
                role=role,
                team_levels=_parse_team_levels(form, team_ids),
                enabled=enabled == "on",
                password_plain=pwd,
                actor=user.username,
            )
        except UsersAdminError as exc:
            return templates.TemplateResponse(
                request,
                "admin_settings_user_form.html",
                {
                    "user": user,
                    "mode": "edit",
                    "record": record,
                    "team_ids": team_ids,
                    "team_levels": _parse_team_levels(form, team_ids),
                    "error": str(exc),
                    "is_self": record.username == user.username,
                    "settings_active": "users",
                },
                status_code=400,
            )
        return RedirectResponse("/admin/settings/users?saved=updated", status_code=302)

    @app.post("/admin/settings/users/{username}/delete")
    async def users_delete(request: Request, username: str, user: CurrentUser):
        require_admin(user)
        try:
            delete_user(root_path, username=username, actor=user.username)
        except UsersAdminError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse("/admin/settings/users?saved=deleted", status_code=302)
