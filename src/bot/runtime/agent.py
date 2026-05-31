"""Agent-Loop: Inbox-Watch (sofort) + Polling-Fallback (Idle)."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Literal

from bot.config.models import AgentConfig
from bot.llm import LlmStack
from bot.messages import Message, MessageError, MessageService
from bot.messages.inbox_watch import InboxWatcher
from bot.messages.paths import agent_inbox
from bot.runtime.context import HandlerContext
from bot.runtime.handlers import AgentHandler, HandlerResult, handler_for_role

logger = logging.getLogger(__name__)


class AgentRunner:
    """Ein Agent mit Inbox-Watch-Thread und periodischem Idle-Polling."""

    def __init__(
        self,
        *,
        root: Path,
        team_id: str,
        agent_cfg: AgentConfig,
        default_interval: float,
        inbox_watch_seconds: float = 0.5,
        llm_stack: LlmStack,
        handler: AgentHandler | None = None,
        inbox_template: str = "teams/{team_id}/agents/{agent_id}/inbox",
        stop_event: threading.Event | None = None,
    ) -> None:
        self.root = root
        self.team_id = team_id
        self.agent_id = agent_cfg.agent.id
        self._agent_block = agent_cfg.agent
        self.role = agent_cfg.agent.role
        self.enabled = agent_cfg.agent.enabled
        self.interval = agent_cfg.agent.interval_seconds or default_interval
        self._watch_interval = inbox_watch_seconds
        self._inbox_template = inbox_template
        self._llm_stack = llm_stack
        self._handler = handler or handler_for_role(self.role)
        self._stop = stop_event or threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._inbox_watcher: InboxWatcher | None = None

    @property
    def worker_kind(self) -> Literal["thread"]:
        return "thread"

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def tick(self) -> bool:
        """Ein Polling-Zyklus. Gibt True zurück, wenn eine Message verarbeitet wurde."""
        if not self.enabled:
            return False

        service = MessageService(self.root)
        message = service.claim(self.team_id, self.agent_id)
        if message is None:
            return False

        logger.info(
            "Message übernommen",
            extra={
                "team_id": self.team_id,
                "agent_id": self.agent_id,
                "message_id": message.id,
            },
        )

        ctx = HandlerContext(
            root=self.root,
            team_id=self.team_id,
            agent_id=self.agent_id,
            role=self.role,
            llm_stack=self._llm_stack,
            agent=self._agent_block,
        )
        try:
            result = self._handler.handle(message, ctx)
            self._apply_result(service, message, result)
        except Exception as exc:
            logger.exception(
                "Verarbeitung fehlgeschlagen",
                extra={"message_id": message.id, "agent_id": self.agent_id},
            )
            service.fail(self.team_id, self.agent_id, message.id, str(exc))
        return True

    def _apply_result(
        self, service: MessageService, message: Message, result: HandlerResult
    ) -> None:
        for delegate in result.delegates:
            service.send(
                team_id=self.team_id,
                from_agent=self.agent_id,
                to_agent=delegate.to_agent,
                subject=delegate.subject,
                content=delegate.content,
                type=delegate.type,
                task_category=delegate.task_category,
            )
            logger.info(
                "Delegation",
                extra={
                    "from": self.agent_id,
                    "to": delegate.to_agent,
                    "subject": delegate.subject,
                },
            )

        if result.error:
            service.fail(self.team_id, self.agent_id, message.id, result.error)
            return

        if result.complete:
            service.complete(self.team_id, self.agent_id, message.id)

    def start(self) -> None:
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._wake.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"agent-{self.team_id}-{self.agent_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._inbox_watcher:
            self._inbox_watcher.stop()
        if self._thread:
            self._thread.join(timeout=max(self.interval * 2, 5.0))

    def _inbox_dir(self) -> Path:
        return agent_inbox(
            self.root, self.team_id, self.agent_id, self._inbox_template
        )

    def _wait_for_idle_or_wake(self) -> None:
        """Blockiert bis Wake (neue Inbox-Datei), Idle-Intervall abgelaufen oder Stop."""
        deadline = time.monotonic() + self.interval
        while not self._stop.is_set():
            if self._wake.is_set():
                self._wake.clear()
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            chunk = min(self._watch_interval, remaining, 0.25)
            if self._stop.wait(chunk):
                return
            if self._wake.is_set():
                self._wake.clear()
                return

    def _run_loop(self) -> None:
        inbox = self._inbox_dir()
        inbox.mkdir(parents=True, exist_ok=True)
        self._inbox_watcher = InboxWatcher(
            inbox,
            interval_seconds=self._watch_interval,
            wake_event=self._wake,
            stop_event=self._stop,
        )
        self._inbox_watcher.start()
        try:
            while not self._stop.is_set():
                try:
                    while self.tick() and not self._stop.is_set():
                        pass
                except MessageError as exc:
                    logger.warning("Message-Fehler: %s", exc)
                except Exception:
                    logger.exception("Unerwarteter Fehler im Agent-Loop")
                if self._stop.is_set():
                    break
                self._wait_for_idle_or_wake()
        finally:
            if self._inbox_watcher:
                self._inbox_watcher.stop()
                self._inbox_watcher = None
