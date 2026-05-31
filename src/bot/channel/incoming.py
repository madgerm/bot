"""Eingehende Kanal-Nachrichten (Runner-Seite)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from bot.channel.protocol import decode_message
from bot.channel.queue import LlmChannelQueue
from bot.channel.rpc_queue import ChannelRpcQueue

logger = logging.getLogger(__name__)

SendFn = Callable[[dict[str, Any]], Awaitable[None]]


class ChannelIncomingHandler:
    def __init__(
        self,
        llm_queue: LlmChannelQueue,
        rpc_queue: ChannelRpcQueue,
        send: SendFn,
    ) -> None:
        self._llm = llm_queue
        self._rpc = rpc_queue
        self._send = send

    async def handle_raw(self, raw: str) -> None:
        try:
            msg = decode_message(raw)
        except ValueError as exc:
            logger.warning("Kanal: ungültige Nachricht: %s", exc)
            return
        await self.handle_message(msg)

    async def handle_message(self, msg: dict[str, Any]) -> None:
        mtype = msg.get("type")
        if mtype == "pong":
            return
        if mtype == "ping":
            await self._send({"type": "pong", "id": msg.get("id")})
            return
        if mtype == "channel.hello":
            return
        if mtype == "llm.response":
            req_id = msg.get("id")
            content = msg.get("content")
            if req_id and content is not None:
                self._llm.complete(str(req_id), str(content))
            return
        if mtype == "llm.error":
            req_id = msg.get("id")
            if req_id:
                self._llm.fail(str(req_id), str(msg.get("detail", "LLM-Fehler")))
            return
        if mtype == "rpc.response":
            req_id = msg.get("id")
            result = msg.get("result")
            if req_id and isinstance(result, dict):
                self._rpc.complete(str(req_id), result)
            return
        if mtype == "rpc.error":
            req_id = msg.get("id")
            if req_id:
                self._rpc.fail(str(req_id), str(msg.get("detail", "RPC-Fehler")))
