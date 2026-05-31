"""WebSocket /api/v1/channel/ws auf dem Team-Runner."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketException, status

from bot.channel.relay import get_channel_relay
from bot.team_api.auth import load_api_token

router = APIRouter()


def _verify_ws_token(root: Path, token: str | None) -> None:
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token fehlt")
    try:
        expected = load_api_token(root)
    except RuntimeError as exc:
        raise WebSocketException(
            code=status.WS_1011_INTERNAL_ERROR, reason=str(exc)
        ) from exc
    if not secrets.compare_digest(token, expected):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Ungültiger Token")


@router.websocket("/api/v1/channel/ws")
async def channel_websocket(websocket: WebSocket) -> None:
    root = Path(websocket.app.state.root)
    token = websocket.query_params.get("token")
    _verify_ws_token(root, token)
    relay = get_channel_relay(root)
    await relay.attach(websocket)
