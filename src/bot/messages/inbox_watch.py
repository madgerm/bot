"""Inbox-Watch: dedizierter mtime-Thread weckt den Agent-Loop sofort."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def inbox_pending_snapshot(inbox: Path) -> dict[Path, float]:
    """Nur pending JSON direkt in der Inbox (nicht processed/failed)."""
    if not inbox.is_dir():
        return {}
    state: dict[Path, float] = {}
    for path in inbox.glob("*.json"):
        if path.name.endswith(".tmp"):
            continue
        state[path] = path.stat().st_mtime
    return state


class InboxWatcher:
    """Pollt die Inbox und setzt wake_event bei Änderungen (neue/aktualisierte Dateien)."""

    def __init__(
        self,
        inbox: Path,
        *,
        interval_seconds: float,
        wake_event: threading.Event,
        stop_event: threading.Event,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._inbox = inbox
        self._interval = interval_seconds
        self._wake = wake_event
        self._stop = stop_event
        self._on_change = on_change
        self._thread: threading.Thread | None = None
        self._last = inbox_pending_snapshot(inbox)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._last = inbox_pending_snapshot(self._inbox)
        self._thread = threading.Thread(
            target=self._run,
            name=f"inbox-watch-{self._inbox.name}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=self._interval * 3 + 1)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            current = inbox_pending_snapshot(self._inbox)
            if current == self._last:
                continue
            self._last = current
            logger.debug(
                "Inbox-Änderung erkannt",
                extra={"inbox": str(self._inbox), "files": len(current)},
            )
            self._wake.set()
            if self._on_change:
                self._on_change()
