"""Zentraler Config-Store mit Hot-Reload und Callbacks."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from bot.config.loader import ConfigLoadError, load_runtime_config
from bot.config.models import RuntimeConfig
from bot.config.watcher import ConfigWatcher


class ConfigStore:
    """Hält die aktuelle Runtime-Konfiguration und lädt sie bei Bedarf neu."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        self._lock = threading.RLock()
        self._config: RuntimeConfig | None = None
        self._callbacks: list[Callable[[RuntimeConfig], None]] = []
        self._watcher: ConfigWatcher | None = None
        self._last_error: ConfigLoadError | None = None

    @property
    def root(self) -> Path:
        return self._root

    @property
    def last_error(self) -> ConfigLoadError | None:
        return self._last_error

    def load(self) -> RuntimeConfig:
        with self._lock:
            try:
                config = load_runtime_config(self._root)
            except ConfigLoadError as exc:
                self._last_error = exc
                raise
            self._last_error = None
            self._config = config
            return config

    def get(self) -> RuntimeConfig:
        with self._lock:
            if self._config is None:
                return self.load()
            return self._config

    def reload(self) -> RuntimeConfig:
        config = self.load()
        self._notify(config)
        return config

    def on_reload(self, callback: Callable[[RuntimeConfig], None]) -> None:
        self._callbacks.append(callback)

    def start_watching(self, *, interval_seconds: float = 1.0) -> None:
        if self._watcher is not None:
            return

        def _handle_change() -> None:
            try:
                self.reload()
            except ConfigLoadError:
                pass

        self._watcher = ConfigWatcher(
            self._root,
            interval_seconds=interval_seconds,
            on_change=_handle_change,
        )
        self._watcher.start()

    def stop_watching(self) -> None:
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    def _notify(self, config: RuntimeConfig) -> None:
        for callback in list(self._callbacks):
            callback(config)
