"""Bearer-Token-Auth für die Team-Runner-API."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def load_api_token(root: Path) -> str:
    env_name = "BOT_TEAM_API_TOKEN"
    path = root / "config" / "team_api.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        env_name = data.get("token_env", env_name)
    token = os.environ.get(env_name)
    if not token:
        raise RuntimeError(
            f"API-Token fehlt: setze Umgebungsvariable {env_name} "
            f"(erzeugen mit: bot team token)"
        )
    return token


def generate_api_token() -> str:
    return secrets.token_urlsafe(32)


def verify_bearer(root: Path, credentials: HTTPAuthorizationCredentials | None) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer-Token erforderlich",
        )
    expected = load_api_token(root)
    if not secrets.compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ungültiger API-Token",
        )


def auth_dependency(root: Path):
    def _dep(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    ) -> None:
        verify_bearer(root, credentials)

    return _dep
