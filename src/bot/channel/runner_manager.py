"""Hintergrund-Connector: Runner → Internet-Relay (bot run)."""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from bot.channel.client_link import run_outbound_channel_loop
from bot.channel.hub_config import runner_ws_url
from bot.config import ConfigStore

logger = logging.getLogger(__name__)


class RunnerChannelManager:
    """Asyncio-Loop in Daemon-Thread für Relay-Modus."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        url = runner_ws_url(ConfigStore(self._root).get())
        if not url:
            return
        if self._thread is not None:
            return

        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(
                    run_outbound_channel_loop(
                        url,
                        self._root,
                        role="runner",
                        label="relay",
                    )
                )
            except Exception as exc:
                logger.warning("Runner-Kanal beendet: %s", exc)
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=_run, name="bot-runner-channel", daemon=True)
        self._thread.start()
        logger.info("Runner-Kanal (Internet-Relay) gestartet")

    def stop(self) -> None:
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(lambda: asyncio.get_event_loop().stop())
        except Exception:
            pass
        self._thread = None
        self._loop = None
