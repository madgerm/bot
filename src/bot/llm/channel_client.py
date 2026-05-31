"""LLM über Panel-Kanal (Queue + WebSocket) — Runner muss Panel nicht anrufen."""

from __future__ import annotations

from pathlib import Path

from bot.channel.queue import ChannelQueueError, LlmChannelQueue
from bot.llm.client import LlmError


class ChannelLlmClient:
    """Stellt LLM-Anfragen in die persistente Queue; Antwort wenn Panel verbunden ist."""

    def __init__(self, *, root: Path | str, timeout_seconds: float) -> None:
        self._queue = LlmChannelQueue(root)
        self._timeout_seconds = timeout_seconds

    def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        fallbacks: list[str] | None = None,
    ) -> str:
        req_id = self._queue.enqueue(
            model=model, messages=messages, fallbacks=fallbacks
        )
        try:
            return self._queue.wait_for_result(req_id, timeout_seconds=self._timeout_seconds)
        except ChannelQueueError as exc:
            raise LlmError(str(exc)) from exc
