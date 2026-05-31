"""WebSocket-URLs für Kanal: direkt (Panel→Runner) oder Internet-Relay."""

from __future__ import annotations

import os
from urllib.parse import quote, urlencode

from bot.channel.relay import CHANNEL_WS_PATH


def build_relay_ws_url(
    relay_url: str,
    *,
    role: str,
    room: str,
    token: str,
) -> str:
    base = relay_url.rstrip("/")
    if not base.endswith("/ws"):
        if "/ws" not in base.split("?")[0].split("#")[0]:
            base = f"{base}/ws"
    params = urlencode(
        {"role": role, "room": room, "token": token},
        quote_via=quote,
    )
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{params}"


def build_direct_runner_ws_url(base_url: str, token_env: str) -> str:
    token = os.environ.get(token_env, "")
    base = base_url.rstrip("/")
    if base.startswith("https://"):
        host = base[len("https://") :]
        scheme = "wss"
    elif base.startswith("http://"):
        host = base[len("http://") :]
        scheme = "ws"
    else:
        host = base
        scheme = "ws"
    return f"{scheme}://{host}{CHANNEL_WS_PATH}?token={quote(token)}"
