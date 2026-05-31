"""Automatisches Audit-Logging für alle erfolgreichen Panel-POST-Aktionen."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from bot.web.audit_helper import log_panel_action
from bot.web.auth import SESSION_USER_KEY

_SKIP_PREFIXES = ("/static", "/api/docs", "/health")
_SKIP_EXACT: set[str] = set()


def _parse_post_action(path: str) -> tuple[str, str, str | None, dict[str, Any]] | None:
    """Liefert category, action, team_id, details aus dem URL-Pfad."""
    if path in _SKIP_EXACT:
        return None

    m = re.match(r"^/teams/([^/]+)/tasks/create$", path)
    if m:
        return ("tasks", "create", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/tasks/([^/]+)/status$", path)
    if m:
        return ("tasks", "update_status", m.group(1), {"task_id": m.group(2)})
    m = re.match(r"^/teams/([^/]+)/agents/create$", path)
    if m:
        return ("agents", "create", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/agents/([^/]+)/delete$", path)
    if m:
        return ("agents", "delete", m.group(1), {"agent_id": m.group(2)})
    m = re.match(r"^/teams/([^/]+)/files/save$", path)
    if m:
        return ("files", "save", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/git/commit$", path)
    if m:
        return ("git", "commit", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/chat/send$", path)
    if m:
        return ("chat", "send", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/chat/delete$", path)
    if m:
        return ("chat", "delete_message", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/chat/clear$", path)
    if m:
        return ("chat", "clear_all", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/knowledge/reindex$", path)
    if m:
        return ("knowledge", "reindex", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/knowledge/search$", path)
    if m:
        return ("knowledge", "search", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/mail/([^/]+)/draft$", path)
    if m:
        return ("mail", "create_draft", m.group(1), {"thread_id": m.group(2)})
    m = re.match(r"^/teams/([^/]+)/mail/draft/([^/]+)/approve$", path)
    if m:
        return ("mail", "approve_draft", m.group(1), {"draft_id": m.group(2)})
    m = re.match(r"^/teams/([^/]+)/mail/draft/([^/]+)/send$", path)
    if m:
        return ("mail", "send_draft", m.group(1), {"draft_id": m.group(2)})
    m = re.match(r"^/teams/([^/]+)/hours/check$", path)
    if m:
        return ("hours", "check", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/hours/diff/([^/]+)/approve$", path)
    if m:
        return ("hours", "approve_diff", m.group(1), {"diff_id": m.group(2)})
    m = re.match(r"^/teams/([^/]+)/hours/diff/([^/]+)/publish$", path)
    if m:
        return ("hours", "publish_diff", m.group(1), {"diff_id": m.group(2)})
    m = re.match(r"^/teams/([^/]+)/story/planner$", path)
    if m:
        return ("story", "planner", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/story/characters$", path)
    if m:
        return ("story", "characters", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/story/world$", path)
    if m:
        return ("story", "world", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/story/scenes/chapter$", path)
    if m:
        return ("story", "scene_chapter", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/story/scenes/new$", path)
    if m:
        return ("story", "scene_new", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/story/scenes/save$", path)
    if m:
        return ("story", "scene_save", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/story/review$", path)
    if m:
        return ("story", "review", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/story/export$", path)
    if m:
        return ("story", "export", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/media/image$", path)
    if m:
        return ("media", "image", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/media/voice/stt$", path)
    if m:
        return ("media", "stt", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/media/voice/tts$", path)
    if m:
        return ("media", "tts", m.group(1), {})
    m = re.match(r"^/teams/([^/]+)/crawl/run$", path)
    if m:
        return ("crawl", "run", m.group(1), {})
    m = re.match(r"^/admin/deploy/([^/]+)$", path)
    if m:
        return ("admin", "deploy_generate", None, {"team_id": m.group(1)})
    m = re.match(r"^/admin/media/global$", path)
    if m:
        return ("config", "media_global_save", None, {"config_path": "config/system.json"})
    m = re.match(r"^/admin/media/team/([^/]+)$", path)
    if m:
        return (
            "config",
            "media_team_save",
            m.group(1),
            {"config_path": f"teams/{m.group(1)}/media.json"},
        )
    m = re.match(r"^/admin/settings(?:/([^/]+))?(?:/([^/]+))?$", path)
    if m:
        sub = "/".join(x for x in (m.group(1), m.group(2)) if x)
        return ("config", sub or "save", None, {"path": path})
    m = re.match(r"^/api/v1/webhooks/([^/]+)/([^/]+)$", path)
    if m:
        return ("webhook", "ingest", m.group(1), {"agent_id": m.group(2)})
    m = re.match(r"^/api/v1/integrations/([^/]+)/telegram$", path)
    if m:
        return ("integration", "telegram", m.group(1), {})
    m = re.match(r"^/api/v1/integrations/([^/]+)/matrix$", path)
    if m:
        return ("integration", "matrix", m.group(1), {})
    if path == "/login":
        return ("auth", "login", None, {})
    if path == "/logout":
        return ("auth", "logout", None, {})
    return None


class PanelAuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, root: Path) -> None:
        super().__init__(app)
        self._root = root

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.method != "POST":
            return response
        if response.status_code >= 400:
            return response
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return response

        parsed = _parse_post_action(path)
        if parsed is None:
            return response

        category, action, team_id, details = parsed
        actor = request.session.get(SESSION_USER_KEY) if hasattr(request, "session") else None
        if not actor:
            if path.startswith("/api/v1/webhooks"):
                actor = "webhook"
            elif path.startswith("/api/v1/integrations"):
                actor = "integration"
            else:
                return response

        details = {**details, "path": path, "method": request.method}
        log_panel_action(
            self._root,
            category=category,
            action=action,
            actor=str(actor),
            team_id=team_id,
            details=details,
        )
        return response
