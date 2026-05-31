"""Supervisor: lädt Config, startet Team-Agents, Hot-Reload."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from bot.config import ConfigLoadError, ConfigStore
from bot.config.models import RuntimeConfig
from bot.llm import LlmStack, build_llm_stack
from bot.qdrant.scheduler import QdrantReindexScheduler
from bot.runtime.team import TeamRuntime
from bot.runtime.worker import WorkerMode

logger = logging.getLogger(__name__)


class Supervisor:
    """Zentrale Runtime — startet Teams mit Agent-Workern (Thread oder Subprozess)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self._store = ConfigStore(self.root)
        self._teams: dict[str, TeamRuntime] = {}
        self._llm_stack: LlmStack | None = None
        self._lock = threading.RLock()
        self._running = False
        self._qdrant_scheduler: QdrantReindexScheduler | None = None

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

    def status(self) -> dict:
        """Laufzeitstatus für Health-Endpoints."""
        with self._lock:
            workers: list[dict] = []
            for team in self._teams.values():
                workers.extend(team.workers_status())
            return {
                "running": self._running,
                "teams": len(self._teams),
                "agents": sum(len(t.agents) for t in self._teams.values()),
                "workers": workers,
            }

    def _build_teams(
        self,
        config: RuntimeConfig,
        team_filter: set[str] | None = None,
        *,
        worker_mode: WorkerMode | None = None,
    ) -> None:
        polling = config.system.system.polling
        interval = polling.interval_seconds
        watch = polling.inbox_watch_seconds
        mode: WorkerMode = worker_mode or polling.worker_mode
        inbox_template = config.system.system.communication.inbox_base
        self._llm_stack = build_llm_stack(config, root=self.root)
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
                inbox_watch_seconds=watch,
                inbox_template=inbox_template,
                llm_stack=self._llm_stack,
                worker_mode=mode,
            )
        self._teams = teams

    def start(self, *, team_ids: list[str] | None = None) -> None:
        with self._lock:
            config = self._store.get()
            team_filter = set(team_ids) if team_ids else None
            self._build_teams(config, team_filter)
            for team in self._teams.values():
                team.start()
            self._start_qdrant_reindex(config, list(self._teams.keys()))
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
            if self._qdrant_scheduler:
                self._qdrant_scheduler.stop()
                self._qdrant_scheduler = None
            for team in self._teams.values():
                team.stop()
            self._running = False
            logger.info("Supervisor gestoppt")

    def _start_qdrant_reindex(self, config: RuntimeConfig, team_ids: list[str]) -> None:
        from bot.channel.satellite import is_satellite_runner

        if is_satellite_runner(config):
            return
        qdrant = config.system.qdrant_global
        if not qdrant or not qdrant.enabled or not qdrant.reindex.enabled:
            return
        from bot.qdrant.scheduler import QdrantReindexScheduler

        self._qdrant_scheduler = QdrantReindexScheduler(
            self.root,
            qdrant_cfg=qdrant,
            team_ids=team_ids,
        )
        self._qdrant_scheduler.start()

    def run_until_idle(
        self,
        *,
        team_ids: list[str] | None = None,
        max_rounds: int = 20,
    ) -> int:
        """Synchroner Modus für Tests/Cron — verarbeitet pending Messages im Thread-Modus."""
        config = self._store.get()
        team_filter = set(team_ids) if team_ids else None
        self._build_teams(config, team_filter, worker_mode="thread")
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
