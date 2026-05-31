"""CSRF-Schutz (Session-Token + httponly SameSite-Cookie, Double-Submit)."""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

SESSION_CSRF_KEY = "csrf_token"
CSRF_COOKIE = "bot_csrf"


def csrf_enabled() -> bool:
    raw = os.environ.get("BOT_WEB_CSRF", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get(SESSION_CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[SESSION_CSRF_KEY] = token
    return token


def validate_csrf(request: Request, token: str | None) -> None:
    if not csrf_enabled():
        return
    expected = request.session.get(SESSION_CSRF_KEY)
    if not expected or not token or not secrets.compare_digest(expected, token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF-Token ungültig oder fehlend",
        )


def _csrf_exempt(path: str) -> bool:
    if path == "/health":
        return True
    if path.startswith("/static"):
        return True
    if path.startswith("/api/v1/webhooks"):
        return True
    if path.startswith("/api/v1/llm/"):
        return True
    if path.startswith("/api/v1/integrations"):
        return True
    if path.startswith("/api/docs"):
        return True
    return False


class CsrfMiddleware(BaseHTTPMiddleware):
    """Setzt CSRF-Cookie bei GET; prüft Cookie==Session bei POST."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not csrf_enabled():
            return await call_next(request)

        if request.method == "GET" and not _csrf_exempt(request.url.path):
            ensure_csrf_token(request)

        if request.method == "POST" and not _csrf_exempt(request.url.path):
            session_tok = request.session.get(SESSION_CSRF_KEY)
            cookie_tok = request.cookies.get(CSRF_COOKIE)
            if not session_tok or not cookie_tok or not secrets.compare_digest(
                session_tok, cookie_tok
            ):
                return JSONResponse(
                    {"detail": "CSRF-Validierung fehlgeschlagen"},
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        response = await call_next(request)

        if request.method == "GET" and not _csrf_exempt(request.url.path):
            token = ensure_csrf_token(request)
            response.set_cookie(
                CSRF_COOKIE,
                token,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https",
            )
        return response
