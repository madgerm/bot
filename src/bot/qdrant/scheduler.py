"""Periodischer Qdrant-Reindex und Workspace-Watch (Hooks)."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from bot.config.models import QdrantGlobalConfig, QdrantReindexConfig
from bot.qdrant.indexer import (
    index_crawl_snapshots,
    index_team_workspace,
    index_workspace_file,
    workspace_snapshot,
)

logger = logging.getLogger(__name__)


class QdrantReindexScheduler:
    """Hintergrund-Threads: periodischer Voll-Reindex + mtime-Watch auf Workspaces."""

    def __init__(
        self,
        root: Path,
        *,
        qdrant_cfg: QdrantGlobalConfig,
        team_ids: list[str],
    ) -> None:
        self.root = root.resolve()
        self.qdrant_cfg = qdrant_cfg
        self.team_ids = list(team_ids)
        self.reindex_cfg: QdrantReindexConfig = qdrant_cfg.reindex
        self._stop = threading.Event()
        self._periodic_thread: threading.Thread | None = None
        self._watch_thread: threading.Thread | None = None
        self._last_snapshot: dict[str, dict[str, float]] = {}
        self._pending_teams: set[str] = set()
        self._pending_lock = threading.Lock()
        self._last_fire: dict[str, float] = {}

    def start(self) -> None:
        if not self.qdrant_cfg.enabled or not self.reindex_cfg.enabled:
            return
        self._stop.clear()
        if self.reindex_cfg.interval_seconds > 0:
            self._periodic_thread = threading.Thread(
                target=self._periodic_loop,
                name="qdrant-reindex-periodic",
                daemon=True,
            )
            self._periodic_thread.start()
        if self.reindex_cfg.watch_workspace:
            self._watch_thread = threading.Thread(
                target=self._watch_loop,
                name="qdrant-reindex-watch",
                daemon=True,
            )
            self._watch_thread.start()
        logger.info(
            "Qdrant-Reindex aktiv",
            extra={
                "interval_s": self.reindex_cfg.interval_seconds,
                "watch": self.reindex_cfg.watch_workspace,
                "teams": self.team_ids,
            },
        )

    def stop(self) -> None:
        self._stop.set()
        for t in (self._periodic_thread, self._watch_thread):
            if t:
                t.join(timeout=self.reindex_cfg.watch_interval_seconds + 5)

    def notify_file_saved(self, team_id: str, rel_path: str) -> None:
        """Hook: sofort nach Speichern im Datei-Editor (einzelne Datei)."""
        if not self.qdrant_cfg.enabled:
            return
        try:
            if index_workspace_file(self.root, team_id, rel_path):
                logger.info(
                    "Qdrant Hook: Datei indexiert",
                    extra={"team_id": team_id, "path": rel_path},
                )
        except Exception as exc:
            logger.warning("Qdrant Hook fehlgeschlagen: %s", exc)

    def _periodic_loop(self) -> None:
        while not self._stop.is_set():
            for team_id in self.team_ids:
                if self._stop.is_set():
                    break
                self._reindex_team(team_id, reason="periodic")
            self._stop.wait(self.reindex_cfg.interval_seconds)

    def _watch_loop(self) -> None:
        while not self._stop.is_set():
            for team_id in self.team_ids:
                if self._stop.is_set():
                    break
                current = workspace_snapshot(self.root, team_id)
                previous = self._last_snapshot.get(team_id, {})
                if previous and current != previous:
                    with self._pending_lock:
                        self._pending_teams.add(team_id)
                self._last_snapshot[team_id] = current
            self._flush_debounced()
            self._stop.wait(self.reindex_cfg.watch_interval_seconds)

    def _flush_debounced(self) -> None:
        now = time.monotonic()
        with self._pending_lock:
            due = [
                t
                for t in self._pending_teams
                if now - self._last_fire.get(t, 0) >= self.reindex_cfg.debounce_seconds
            ]
            for team_id in due:
                self._pending_teams.discard(team_id)
                self._last_fire[team_id] = now
        for team_id in due:
            self._reindex_team(team_id, reason="watch")

    def _reindex_team(self, team_id: str, *, reason: str) -> None:
        try:
            ws = index_team_workspace(self.root, team_id)
            cr = 0
            if self.reindex_cfg.include_crawl:
                cr = index_crawl_snapshots(self.root, team_id)
            logger.info(
                "Qdrant Reindex (%s)",
                reason,
                extra={"team_id": team_id, "workspace": ws, "crawl": cr},
            )
        except Exception as exc:
            logger.warning(
                "Qdrant Reindex fehlgeschlagen",
                extra={"team_id": team_id, "error": str(exc)},
            )
