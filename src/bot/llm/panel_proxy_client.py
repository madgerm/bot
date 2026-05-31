"""LLM-Client: Team-Runner ruft das Web-Panel im LAN als Proxy auf."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from bot.llm.client import LlmError

logger = logging.getLogger(__name__)


class PanelProxyLlmClient:
    """Leitet Completions an POST /api/v1/llm/complete auf dem Web-Panel weiter."""

    def __init__(
        self,
        *,
        base_url: str,
        token_env: str,
        max_retries: int,
        retry_backoff_seconds: float,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_env = token_env
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._timeout_seconds = timeout_seconds

    def _token(self) -> str:
        token = os.environ.get(self._token_env)
        if not token:
            raise LlmError(
                f"LLM-Proxy-Token fehlt: Umgebungsvariable {self._token_env} setzen "
                "(gleicher Wert wie auf dem Web-Panel)."
            )
        return token

    def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        fallbacks: list[str] | None = None,
    ) -> str:
        url = f"{self._base_url}/api/v1/llm/complete"
        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "fallbacks": fallbacks or [],
        }
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    response = client.post(url, json=payload, headers=headers)
                if response.status_code == 401:
                    raise LlmError("LLM-Proxy: unauthorisiert — Token prüfen")
                if response.status_code == 403:
                    raise LlmError("LLM-Proxy: Zugriff verweigert — Token prüfen")
                if response.status_code >= 400:
                    detail = response.text
                    try:
                        detail = response.json().get("detail", detail)
                    except Exception:
                        pass
                    raise LlmError(f"LLM-Proxy HTTP {response.status_code}: {detail}")
                data = response.json()
                content = data.get("content")
                if not content:
                    raise LlmError("LLM-Proxy: leere Antwort vom Panel")
                logger.info(
                    "LLM-Proxy OK",
                    extra={"model": model, "panel": self._base_url, "attempt": attempt + 1},
                )
                return str(content).strip()
            except LlmError:
                raise
            except Exception as exc:
                last_error = exc
                wait = self._retry_backoff_seconds * (2**attempt)
                logger.warning(
                    "LLM-Proxy Fehler (attempt=%s): %s",
                    attempt + 1,
                    exc,
                )
                if attempt + 1 < self._max_retries:
                    time.sleep(wait)

        raise LlmError(f"LLM-Proxy fehlgeschlagen ({url}): {last_error}") from last_error
