"""Periodischer IMAP-Poll für E-Mail-Teams (Supervisor)."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from bot.mail.config import EmailConfig
from bot.mail.notify import notify_new_mail_threads
from bot.mail.service import MailService, MailServiceError

logger = logging.getLogger(__name__)

_DEFAULT_TICK_SECONDS = 30.0


def _load_poll_interval(root: Path, team_id: str) -> float | None:
    path = root / "teams" / team_id / "email.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = EmailConfig.model_validate(data).email
    except Exception:
        return None
    if not cfg.enabled:
        return None
    return float(cfg.imap.poll_interval_seconds)


class MailPollScheduler:
    """Pollt IMAP für Teams mit email.json im Hintergrund."""

    def __init__(self, root: Path, team_ids: list[str]) -> None:
        self.root = root.resolve()
        self.team_ids = list(team_ids)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_poll: dict[str, float] = {}

    def start(self) -> None:
        enabled = [
            tid
            for tid in self.team_ids
            if _load_poll_interval(self.root, tid) is not None
        ]
        if not enabled:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="mail-imap-poll",
            daemon=True,
        )
        self._thread.start()
        logger.info("Mail-Poll aktiv", extra={"teams": enabled})

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=_DEFAULT_TICK_SECONDS + 10)

    def poll_team_now(self, team_id: str, *, limit: int = 20) -> int:
        """Einmaliger Poll; Rückgabe Anzahl neuer Threads."""
        try:
            service = MailService.for_team(self.root, team_id)
            new_threads = service.poll(limit=limit)
        except MailServiceError as exc:
            logger.warning("Mail poll %s: %s", team_id, exc)
            return 0
        notify_new_mail_threads(self.root, team_id, new_threads)
        self._last_poll[team_id] = time.monotonic()
        return len(new_threads)

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = time.monotonic()
            for team_id in self.team_ids:
                interval = _load_poll_interval(self.root, team_id)
                if interval is None:
                    continue
                last = self._last_poll.get(team_id, 0.0)
                if now - last < interval:
                    continue
                self.poll_team_now(team_id)
            self._stop.wait(_DEFAULT_TICK_SECONDS)
