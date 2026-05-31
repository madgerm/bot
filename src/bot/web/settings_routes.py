"""Admin-Einstellungen (/admin/settings) — Konfiguration über das Panel."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from bot.web.auth import CurrentUser, require_admin
from bot.web.hosts_settings_routes import register_hosts_settings_routes
from bot.web.status_settings_routes import register_status_settings_routes
from bot.web.system_settings_routes import register_system_settings_routes
from bot.web.users_settings_routes import register_users_settings_routes


def register_settings_routes(
    app,
    templates: Jinja2Templates,
    root_path: Path,
) -> None:
    @app.get("/admin/settings", response_class=HTMLResponse)
    async def admin_settings_index(request: Request, user: CurrentUser):
        require_admin(user)
        sections = [
            {
                "id": "users",
                "title": "Nutzer & Zugänge",
                "description": "Benutzer anlegen, Rollen, Team-Zugriff, Passwörter",
                "href": "/admin/settings/users",
                "phase": None,
            },
            {
                "id": "system",
                "title": "System",
                "description": "LLM, Qdrant, Playwright, Polling, Webhooks",
                "href": "/admin/settings/system",
                "phase": None,
            },
            {
                "id": "models",
                "title": "Task-Modelle",
                "description": "Modell-Routing pro Aufgabenkategorie (planning, coding, …)",
                "href": "/admin/settings/models",
                "phase": None,
            },
            {
                "id": "media",
                "title": "Medien",
                "description": "STT, TTS, Vision, Bildgenerierung",
                "href": "/admin/media",
                "phase": None,
            },
            {
                "id": "hosts",
                "title": "Team-Runner & Verbindung",
                "description": "Lokal/Remote, Kanal, Relay — Setup-Assistent",
                "href": "/admin/settings/hosts",
                "phase": None,
            },
            {
                "id": "status",
                "title": "Status & Tests",
                "description": "LLM-, Qdrant- und Kanal-Verbindung prüfen",
                "href": "/admin/settings/status",
                "phase": None,
            },
        ]
        return templates.TemplateResponse(
            request,
            "admin_settings_index.html",
            {
                "user": user,
                "sections": sections,
                "root_label": str(root_path),
            },
        )

    register_users_settings_routes(app, templates, root_path)
    register_system_settings_routes(app, templates, root_path)
    register_hosts_settings_routes(app, templates, root_path)
    register_status_settings_routes(app, templates, root_path)
