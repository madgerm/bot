"""Ausgehende WebSocket-Verbindung (Panel oder Runner) mit Queue-Flush."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from bot.channel.incoming import ChannelIncomingHandler
from bot.channel.protocol import decode_message, encode_message
from bot.channel.queue import LlmChannelQueue
from bot.channel.rpc_queue import ChannelRpcQueue

logger = logging.getLogger(__name__)


class ChannelClientLink:
    """Hält WS offen, flusht LLM/RPC-Queues, verarbeitet Antworten."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        self._llm = LlmChannelQueue(self._root)
        self._rpc = ChannelRpcQueue(self._root)
        self._ws: Any = None
        self._send_lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._handler = ChannelIncomingHandler(self._llm, self._rpc, self.send_json)

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            return
        async with self._send_lock:
            await self._ws.send(encode_message(payload))

    async def run_session(
        self,
        url: str,
        *,
        hello_role: str,
        on_connected: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        async with ws_connect(url, open_timeout=30) as ws:
            self._ws = ws
            await self.send_json({"type": "channel.hello", "role": hello_role})
            if on_connected:
                await on_connected()
            self._flush_task = asyncio.create_task(self._flush_loop())
            try:
                async for raw in ws:
                    msg = decode_message(raw)
                    if msg.get("type") == "llm.request":
                        continue
                    if msg.get("type") == "rpc.request":
                        continue
                    await self._handler.handle_message(msg)
            finally:
                if self._flush_task:
                    self._flush_task.cancel()
                    self._flush_task = None
                self._ws = None

    async def _flush_loop(self) -> None:
        while self._ws is not None:
            try:
                for item in self._llm.list_pending():
                    await self._send_llm(item)
                for item in self._rpc.list_pending():
                    await self._send_rpc(item)
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Kanal-Flush: %s", exc)
                await asyncio.sleep(1.0)

    async def _send_llm(self, item: dict) -> None:
        req_id = item["id"]
        await self.send_json(
            {
                "type": "llm.request",
                "id": req_id,
                "model": item["model"],
                "messages": item["messages"],
                "fallbacks": item.get("fallbacks") or [],
            }
        )
        self._llm.mark_sent(req_id)

    async def _send_rpc(self, item: dict) -> None:
        req_id = item["id"]
        await self.send_json(
            {
                "type": "rpc.request",
                "id": req_id,
                "kind": item["kind"],
                "payload": item["payload"],
            }
        )
        self._rpc.mark_sent(req_id)

    async def push_pending(self) -> None:
        for item in self._llm.list_pending():
            await self._send_llm(item)
        for item in self._rpc.list_pending():
            await self._send_rpc(item)


async def run_outbound_channel_loop(
    url: str,
    root: Path | str,
    *,
    role: str,
    label: str,
) -> None:
    link = ChannelClientLink(root)
    backoff = 2.0
    while True:
        try:
            logger.info("Kanal verbinde (%s): %s", label, url.split("?")[0])
            await link.run_session(
                url,
                hello_role=role,
                on_connected=link.push_pending,
            )
        except ConnectionClosed as exc:
            logger.warning("Kanal getrennt (%s): %s", label, exc)
        except Exception as exc:
            logger.warning("Kanal Fehler (%s): %s", label, exc)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 1.5, 60.0)
