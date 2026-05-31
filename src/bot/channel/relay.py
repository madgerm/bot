"""Runner-Seite: WebSocket zum Panel, LLM-Queue entkoppeln (läuft in bot team serve)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from bot.channel.protocol import decode_message, encode_message
from bot.channel.queue import LlmChannelQueue
from bot.channel.rpc_queue import ChannelRpcQueue

logger = logging.getLogger(__name__)

CHANNEL_WS_PATH = "/api/v1/channel/ws"


def http_base_to_ws(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + CHANNEL_WS_PATH
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + CHANNEL_WS_PATH
    return "ws://" + base + CHANNEL_WS_PATH


class ChannelRelay:
    """Ein Panel-WebSocket; ping/status optional; LLM aus Queue."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        self._llm_queue = LlmChannelQueue(self._root)
        self._rpc_queue = ChannelRpcQueue(self._root)
        self._ws: WebSocket | None = None
        self._send_lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None

    @property
    def connected(self) -> bool:
        return self._ws is not None

    async def attach(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._ws = websocket
        await self.send_json({"type": "channel.hello", "role": "runner"})
        self._flush_task = asyncio.create_task(self._flush_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())
        try:
            while True:
                raw = await websocket.receive_text()
                await self._handle_incoming(raw)
        except WebSocketDisconnect:
            logger.info("Panel-Kanal getrennt")
        finally:
            await self._detach()

    async def _detach(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            self._flush_task = None
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None
        self._ws = None

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            return
        async with self._send_lock:
            await self._ws.send_text(encode_message(payload))

    async def _handle_incoming(self, raw: str) -> None:
        try:
            msg = decode_message(raw)
        except ValueError as exc:
            logger.warning("Kanal: ungültige Nachricht: %s", exc)
            return
        mtype = msg.get("type")
        if mtype == "pong":
            return
        if mtype == "ping":
            await self.send_json({"type": "pong", "id": msg.get("id")})
            return
        if mtype == "channel.hello":
            await self._push_pending()
            return
        if mtype == "llm.response":
            req_id = msg.get("id")
            content = msg.get("content")
            if req_id and content is not None:
                self._llm_queue.complete(str(req_id), str(content))
            return
        if mtype == "llm.error":
            req_id = msg.get("id")
            detail = msg.get("detail", "LLM-Fehler")
            if req_id:
                self._llm_queue.fail(str(req_id), str(detail))
            return
        if mtype == "rpc.response":
            req_id = msg.get("id")
            result = msg.get("result")
            if req_id and isinstance(result, dict):
                self._rpc_queue.complete(str(req_id), result)
            return
        if mtype == "rpc.error":
            req_id = msg.get("id")
            detail = msg.get("detail", "RPC-Fehler")
            if req_id:
                self._rpc_queue.fail(str(req_id), str(detail))
            return

    async def _push_pending(self) -> None:
        for item in self._llm_queue.list_pending():
            await self._send_llm_request(item)
        for item in self._rpc_queue.list_pending():
            await self._send_rpc_request(item)

    async def _send_llm_request(self, item: dict) -> None:
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
        self._llm_queue.mark_sent(req_id)

    async def _send_rpc_request(self, item: dict) -> None:
        req_id = item["id"]
        await self.send_json(
            {
                "type": "rpc.request",
                "id": req_id,
                "kind": item["kind"],
                "payload": item["payload"],
            }
        )
        self._rpc_queue.mark_sent(req_id)

    async def _flush_loop(self) -> None:
        while self._ws is not None:
            try:
                for item in self._llm_queue.list_pending():
                    if item["id"]:  # noqa: SIM114
                        await self._send_llm_request(item)
                for item in self._rpc_queue.list_pending():
                    await self._send_rpc_request(item)
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Kanal flush: %s", exc)
                await asyncio.sleep(1.0)

    async def _ping_loop(self) -> None:
        n = 0
        while self._ws is not None:
            try:
                await asyncio.sleep(30.0)
                n += 1
                await self.send_json({"type": "ping", "id": f"runner-{n}"})
            except asyncio.CancelledError:
                break
            except Exception:
                break


_relays: dict[str, ChannelRelay] = {}


def get_channel_relay(root: Path | str) -> ChannelRelay:
    key = str(Path(root).resolve())
    if key not in _relays:
        _relays[key] = ChannelRelay(root)
    return _relays[key]
