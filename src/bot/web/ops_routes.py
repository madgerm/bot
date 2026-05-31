"""Admin: Panel & Runner aktualisieren."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.config import load_runtime_config
from bot.ops.upgrade import collect_git_version, run_panel_upgrade
from bot.web.auth import CurrentUser, require_admin


def _llm_panel_status(root: Path) -> dict:
    try:
        llm = load_runtime_config(root).system.system.llm
    except Exception:
        return {"enabled": False, "mode": "?", "api_base": "", "uses_stub": True}
    return {
        "enabled": llm.enabled,
        "mode": llm.mode,
        "api_base": llm.api_base or "",
        "uses_stub": not llm.enabled,
    }


def register_ops_routes(app: FastAPI, templates: Jinja2Templates, root: Path) -> None:
    @app.get("/admin/ops", response_class=HTMLResponse)
    async def admin_ops_page(request: Request, user: CurrentUser):
        require_admin(user)
        return templates.TemplateResponse(
            request,
            "admin_ops.html",
            {
                "user": user,
                "root": str(root),
                "llm": _llm_panel_status(root),
                "git": collect_git_version(root, fetch=True),
            },
        )

    @app.post("/admin/ops/upgrade")
    async def admin_ops_upgrade(
        request: Request,
        user: CurrentUser,
        confirm: str = Form(""),
        skip_git: str = Form(""),
    ):
        require_admin(user)
        if confirm != "yes":
            raise HTTPException(status_code=400, detail="Bestätigung fehlt (confirm=yes)")

        report = run_panel_upgrade(root, skip_git=skip_git == "1")
        return templates.TemplateResponse(
            request,
            "admin_ops.html",
            {
                "user": user,
                "root": str(root),
                "llm": _llm_panel_status(root),
                "git": collect_git_version(root, fetch=False),
                "report": report,
            },
        )

    @app.post("/admin/ops/reload-config")
    async def admin_ops_reload_config(request: Request, user: CurrentUser):
        """Signalisiert Neustart des Runners — Config-Watch greift nach bot run."""
        require_admin(user)
        return RedirectResponse(
            "/admin/ops?hint=config_reload",
            status_code=302,
        )
