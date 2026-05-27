"""Supervisor: lädt Config, startet Team-Agents, Hot-Reload."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from bot.config import ConfigLoadError, ConfigStore
from bot.config.models import RuntimeConfig
from bot.runtime.team import TeamRuntime

logger = logging.getLogger(__name__)


class Supervisor:
    """Zentrale Runtime — startet alle Teams und überwacht Worker-Threads."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self._store = ConfigStore(self.root)
        self._teams: dict[str, TeamRuntime] = {}
        self._lock = threading.RLock()
        self._running = False

    @property
    def config(self) -> RuntimeConfig:
        return self._store.get()

    def reload(self) -> RuntimeConfig:
        was_running = self._running
        if was_running:
            self.stop()
        config = self._store.reload()
        self._build_teams(config)
        if was_running:
            self.start()
        return config

    def _build_teams(self, config: RuntimeConfig, team_filter: set[str] | None = None) -> None:
        interval = config.system.system.polling.interval_seconds
        teams: dict[str, TeamRuntime] = {}
        for team_id, bundle in config.teams.items():
            if team_filter and team_id not in team_filter:
                continue
            if not bundle.team.team.enabled:
                continue
            teams[team_id] = TeamRuntime(
                root=self.root,
                team_id=team_id,
                bundle=bundle,
                default_interval=interval,
            )
        self._teams = teams

    def start(self, *, team_ids: list[str] | None = None) -> None:
        with self._lock:
            config = self._store.get()
            team_filter = set(team_ids) if team_ids else None
            self._build_teams(config, team_filter)
            for team in self._teams.values():
                team.start()
            self._running = True
            logger.info(
                "Supervisor gestartet",
                extra={
                    "teams": list(self._teams),
                    "agents": sum(len(t.agents) for t in self._teams.values()),
                },
            )

    def stop(self) -> None:
        with self._lock:
            for team in self._teams.values():
                team.stop()
            self._running = False
            logger.info("Supervisor gestoppt")

    def run_until_idle(
        self,
        *,
        team_ids: list[str] | None = None,
        max_rounds: int = 20,
    ) -> int:
        """Synchroner Modus für Tests: verarbeitet alle pending Messages."""
        config = self._store.get()
        team_filter = set(team_ids) if team_ids else None
        self._build_teams(config, team_filter)
        total = 0
        for team in self._teams.values():
            total += team.run_until_idle(max_rounds=max_rounds)
        return total

    def enable_config_watch(self, *, interval_seconds: float = 2.0) -> None:
        def _on_reload(config: RuntimeConfig) -> None:
            logger.info("Config neu geladen — Teams werden aktualisiert")
            try:
                with self._lock:
                    running = self._running
                    team_ids = list(self._teams)
                    if running:
                        self.stop()
                    self._build_teams(config, set(team_ids) if team_ids else None)
                    if running:
                        self.start(team_ids=team_ids or None)
            except ConfigLoadError as exc:
                logger.error("Hot-Reload fehlgeschlagen: %s", exc)

        self._store.on_reload(_on_reload)
        self._store.start_watching(interval_seconds=interval_seconds)

    def stop_config_watch(self) -> None:
        self._store.stop_watching()
