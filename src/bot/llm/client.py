"""LiteLLM-Client mit Retry und Fallback-Modellen."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class LlmError(Exception):
    """LLM-Aufruf fehlgeschlagen nach Retries/Fallbacks."""


class LlmClient(Protocol):
    def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        fallbacks: list[str] | None = None,
    ) -> str: ...


class StubLlmClient:
    """Offline-Stub für Tests und llm.enabled=false."""

    def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        fallbacks: list[str] | None = None,
    ) -> str:
        user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return f"[llm-stub model={model}]\n{user.strip()}\n\n(Kurzantwort ohne echtes Modell)"


class LiteLLMClient:
    def __init__(
        self,
        *,
        api_base: str | None,
        secret_ref: str | None,
        max_retries: int,
        retry_backoff_seconds: float,
        timeout_seconds: float,
    ) -> None:
        self._api_base = api_base
        self._secret_ref = secret_ref
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._timeout_seconds = timeout_seconds

    def _apply_secret(self) -> None:
        if not self._secret_ref:
            return
        if os.environ.get(self._secret_ref):
            return
        # secret_ref ist der Name der Umgebungsvariable
        logger.debug("Erwarte API-Key in Umgebungsvariable %s", self._secret_ref)

    def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        fallbacks: list[str] | None = None,
    ) -> str:
        import litellm

        self._apply_secret()
        models_to_try = [model, *(fallbacks or [])]
        last_error: Exception | None = None

        for candidate in models_to_try:
            for attempt in range(self._max_retries):
                try:
                    kwargs: dict[str, Any] = {
                        "model": candidate,
                        "messages": messages,
                        "timeout": self._timeout_seconds,
                    }
                    if self._api_base:
                        kwargs["api_base"] = self._api_base
                    response = litellm.completion(**kwargs)
                    content = response.choices[0].message.content
                    if not content:
                        raise LlmError("Leere Modell-Antwort")
                    logger.info("LLM OK", extra={"model": candidate, "attempt": attempt + 1})
                    return content.strip()
                except Exception as exc:
                    last_error = exc
                    wait = self._retry_backoff_seconds * (2**attempt)
                    logger.warning(
                        "LLM Fehler (model=%s, attempt=%s): %s",
                        candidate,
                        attempt + 1,
                        exc,
                    )
                    if attempt + 1 < self._max_retries:
                        time.sleep(wait)

        raise LlmError(f"LLM fehlgeschlagen für {models_to_try}: {last_error}") from last_error
