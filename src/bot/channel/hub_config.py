"""Kanal-/Relay-Konfiguration aus system.json und team_hosts.json."""

from __future__ import annotations

import os

from bot.channel.urls import build_direct_runner_ws_url, build_relay_ws_url
from bot.config.models import ChannelHubConfig, RuntimeConfig
from bot.hosts.models import TeamHostEntry


def runner_hub_config(config: RuntimeConfig) -> ChannelHubConfig | None:
    return config.system.system.llm.hub


def runner_uses_internet_relay(config: RuntimeConfig) -> bool:
    hub = runner_hub_config(config)
    return bool(hub and hub.relay_url)


def panel_ws_url(entry: TeamHostEntry) -> str:
    assert entry.token_env
    token = os.environ.get(entry.token_env, "")
    if entry.relay_url:
        room = entry.relay_room or "default"
        return build_relay_ws_url(
            entry.relay_url,
            role="panel",
            room=room,
            token=token,
        )
    assert entry.base_url
    return build_direct_runner_ws_url(entry.base_url, entry.token_env)


def runner_ws_url(config: RuntimeConfig) -> str | None:
    llm = config.system.system.llm
    if not llm.enabled or llm.mode != "channel":
        return None
    hub = llm.hub
    if not hub or not hub.relay_url:
        return None
    token = os.environ.get(hub.token_env, "")
    return build_relay_ws_url(
        hub.relay_url,
        role="runner",
        room=hub.relay_room,
        token=token,
    )
