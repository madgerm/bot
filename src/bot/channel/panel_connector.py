"""Panel verbindet sich zum Team-Runner (ausgehend) — bidirektionaler Kanal."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from bot.channel.protocol import decode_message, encode_message
from bot.channel.relay import CHANNEL_WS_PATH, http_base_to_ws
from bot.config import load_runtime_config
from bot.hosts.models import TeamHostEntry
from bot.hosts.registry import load_team_hosts_config
from bot.channel.panel_rpc import execute_panel_rpc
from bot.llm.proxy_service import complete_via_local_llm

logger = logging.getLogger(__name__)


def _ws_url(entry: TeamHostEntry) -> str:
    assert entry.base_url and entry.token_env
    base = entry.base_url.rstrip("/")
    if base.startswith("https://"):
        host = base[len("https://") :]
        scheme = "wss"
    elif base.startswith("http://"):
        host = base[len("http://") :]
        scheme = "ws"
    else:
        host = base
        scheme = "ws"
    token = os.environ.get(entry.token_env, "")
    return f"{scheme}://{host}{CHANNEL_WS_PATH}?token={token}"


async def _handle_rpc_request(panel_root: Path, msg: dict[str, Any]) -> dict[str, Any]:
    req_id = msg.get("id")
    kind = str(msg.get("kind", ""))
    payload = msg.get("payload") or {}
    try:
        result = await asyncio.to_thread(
            execute_panel_rpc, panel_root, kind, payload
        )
        return {"type": "rpc.response", "id": req_id, "result": result}
    except Exception as exc:
        return {"type": "rpc.error", "id": req_id, "detail": str(exc)}


async def _handle_llm_request(panel_root: Path, msg: dict[str, Any]) -> dict[str, Any]:
    req_id = msg.get("id")
    model = msg.get("model", "")
    messages = msg.get("messages", [])
    fallbacks = msg.get("fallbacks") or []
    try:
        config = load_runtime_config(panel_root)
        content = await asyncio.to_thread(
            complete_via_local_llm,
            config,
            model=str(model),
            messages=messages,
            fallbacks=fallbacks or None,
        )
        return {"type": "llm.response", "id": req_id, "content": content}
    except Exception as exc:
        return {"type": "llm.error", "id": req_id, "detail": str(exc)}


async def _session_loop(panel_root: Path, entry: TeamHostEntry) -> None:
    url = _ws_url(entry)
    backoff = 2.0
    while True:
        try:
            async with ws_connect(url, open_timeout=30) as ws:
                logger.info("Kanal verbunden: %s (%s)", entry.label, entry.id)
                await ws.send(encode_message({"type": "channel.hello", "role": "panel"}))
                backoff = 2.0
                ping_n = 0
                async for raw in ws:
                    msg = decode_message(raw)
                    mtype = msg.get("type")
                    if mtype == "ping":
                        await ws.send(encode_message({"type": "pong", "id": msg.get("id")}))
                        continue
                    if mtype == "pong":
                        continue
                    if mtype == "llm.request":
                        reply = await _handle_llm_request(panel_root, msg)
                        await ws.send(encode_message(reply))
                        continue
                    if mtype == "rpc.request":
                        reply = await _handle_rpc_request(panel_root, msg)
                        await ws.send(encode_message(reply))
                        continue
                    if mtype == "channel.hello":
                        continue
        except ConnectionClosed as exc:
            logger.warning("Kanal getrennt (%s): %s", entry.id, exc)
        except Exception as exc:
            logger.warning("Kanal Fehler (%s): %s — Reconnect in %.0fs", entry.id, exc, backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 1.5, 60.0)


async def _http_ping_loop(entry: TeamHostEntry) -> None:
    """Optionaler HTTP-Health — darf fehlschlagen ohne LLM-Queue zu blockieren."""
    if not entry.base_url or not entry.token_env:
        return
    token = os.environ.get(entry.token_env)
    if not token:
        return
    url = f"{entry.base_url.rstrip('/')}/api/v1/health"
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get(url, headers=headers)
        except Exception:
            pass
        await asyncio.sleep(60.0)


def channel_hosts(panel_root: Path) -> list[TeamHostEntry]:
    cfg = load_team_hosts_config(panel_root)
    return [h for h in cfg.hosts if h.mode == "remote" and h.channel]


async def run_panel_connectors(panel_root: Path) -> None:
    hosts = channel_hosts(panel_root)
    if not hosts:
        return
    tasks = []
    for entry in hosts:
        tasks.append(asyncio.create_task(_session_loop(panel_root, entry)))
        tasks.append(asyncio.create_task(_http_ping_loop(entry)))
    await asyncio.gather(*tasks)


class PanelChannelManager:
    """Start/stop Hintergrund-Connectors für bot web."""

    def __init__(self, panel_root: Path) -> None:
        self._root = panel_root
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        hosts = channel_hosts(self._root)
        if not hosts:
            logger.info("Kein remote host mit channel=true — Panel-Kanal inaktiv")
            return
        self._task = asyncio.create_task(run_panel_connectors(self._root))

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
