"""Datei-Watch per mtime-Polling für Hot-Reload."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path


def _snapshot(paths: list[Path]) -> dict[Path, float]:
    state: dict[Path, float] = {}
    for base in paths:
        if not base.exists():
            state[base] = -1.0
            continue
        if base.is_file():
            state[base] = base.stat().st_mtime
            continue
        for path in base.rglob("*"):
            if path.is_file():
                state[path] = path.stat().st_mtime
    return state


class ConfigWatcher:
    """Beobachtet config/ und teams/ und ruft bei Änderungen einen Callback auf."""

    def __init__(
        self,
        root: Path,
        *,
        interval_seconds: float = 1.0,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._root = root.resolve()
        self._interval = interval_seconds
        self._on_change = on_change
        self._watch_paths = [self._root / "config", self._root / "teams"]
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last = _snapshot(self._watch_paths)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._last = _snapshot(self._watch_paths)
        self._thread = threading.Thread(target=self._run, name="config-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self._interval * 3)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            current = _snapshot(self._watch_paths)
            if current != self._last:
                self._last = current
                if self._on_change:
                    self._on_change()
