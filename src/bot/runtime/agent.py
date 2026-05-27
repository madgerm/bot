"""Agent-Polling-Loop: Inbox lesen, verarbeiten, Status setzen."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from bot.config.models import AgentConfig
from bot.llm import LlmStack
from bot.messages import Message, MessageError, MessageService
from bot.runtime.context import HandlerContext
from bot.runtime.handlers import AgentHandler, HandlerResult, handler_for_role

logger = logging.getLogger(__name__)


class AgentRunner:
    """Ein Agent mit periodischem Inbox-Polling."""

    def __init__(
        self,
        *,
        root: Path,
        team_id: str,
        agent_cfg: AgentConfig,
        default_interval: float,
        llm_stack: LlmStack,
        handler: AgentHandler | None = None,
    ) -> None:
        self.root = root
        self.team_id = team_id
        self.agent_id = agent_cfg.agent.id
        self.role = agent_cfg.agent.role
        self.enabled = agent_cfg.agent.enabled
        self.interval = agent_cfg.agent.interval_seconds or default_interval
        self._llm_stack = llm_stack
        self._handler = handler or handler_for_role(self.role)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

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
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"agent-{self.team_id}-{self.agent_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval * 3)

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except MessageError as exc:
                logger.warning("Message-Fehler: %s", exc)
            except Exception:
                logger.exception("Unerwarteter Fehler im Agent-Loop")
            self._stop.wait(self.interval)
