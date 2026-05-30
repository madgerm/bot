"""Agent-Worker als eigener OS-Prozess (Isolation bei Abstürzen/blockierenden Tools)."""

from __future__ import annotations

import logging
import multiprocessing
from multiprocessing.synchronize import Event as MpEvent
from pathlib import Path
from typing import Literal

from bot.config.models import AgentConfig

logger = logging.getLogger(__name__)

_mp_context = multiprocessing.get_context("spawn")


def _agent_worker_main(
    *,
    root: str,
    team_id: str,
    agent_id: str,
    role: str,
    enabled: bool,
    interval: float,
    inbox_watch_seconds: float,
    inbox_template: str,
    stop: MpEvent,
) -> None:
    """Einstiegspunkt im Kindprozess — baut LLM/Handler neu auf."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    from bot.config import load_runtime_config
    from bot.config.models import AgentBlock, AgentConfig as AgentCfg
    from bot.llm import build_llm_stack
    from bot.runtime.agent import AgentRunner

    root_path = Path(root)
    config = load_runtime_config(root_path)
    stack = build_llm_stack(config)
    agent_cfg = AgentCfg(agent=AgentBlock(id=agent_id, role=role, enabled=enabled))

    runner = AgentRunner(
        root=root_path,
        team_id=team_id,
        agent_cfg=agent_cfg,
        default_interval=interval,
        inbox_watch_seconds=inbox_watch_seconds,
        inbox_template=inbox_template,
        llm_stack=stack,
        stop_event=stop,
    )
    runner._run_loop()


class AgentProcessRunner:
    """Startet einen AgentRunner in einem separaten Prozess."""

    def __init__(
        self,
        *,
        root: Path,
        team_id: str,
        agent_cfg: AgentConfig,
        default_interval: float,
        inbox_watch_seconds: float,
        inbox_template: str,
    ) -> None:
        self.root = root
        self.team_id = team_id
        self.agent_id = agent_cfg.agent.id
        self.role = agent_cfg.agent.role
        self.enabled = agent_cfg.agent.enabled
        self.interval = agent_cfg.agent.interval_seconds or default_interval
        self._watch_interval = inbox_watch_seconds
        self._inbox_template = inbox_template
        self._stop: MpEvent = _mp_context.Event()
        self._process: multiprocessing.Process | None = None

    def tick(self) -> bool:
        """Im Prozess-Modus läuft die Verarbeitung nur im Kind — kein Parent-Tick."""
        return False

    def start(self) -> None:
        if not self.enabled or (self._process and self._process.is_alive()):
            return
        self._stop.clear()
        self._process = _mp_context.Process(
            target=_agent_worker_main,
            kwargs={
                "root": str(self.root.resolve()),
                "team_id": self.team_id,
                "agent_id": self.agent_id,
                "role": self.role,
                "enabled": self.enabled,
                "interval": self.interval,
                "inbox_watch_seconds": self._watch_interval,
                "inbox_template": self._inbox_template,
                "stop": self._stop,
            },
            name=f"agent-{self.team_id}-{self.agent_id}",
            daemon=True,
        )
        self._process.start()
        logger.info(
            "Agent-Prozess gestartet",
            extra={"team_id": self.team_id, "agent_id": self.agent_id, "pid": self._process.pid},
        )

    def stop(self) -> None:
        self._stop.set()
        if not self._process:
            return
        self._process.join(timeout=max(self.interval * 2, 5.0))
        if self._process.is_alive():
            logger.warning(
                "Agent-Prozess reagiert nicht — terminate",
                extra={"team_id": self.team_id, "agent_id": self.agent_id},
            )
            self._process.terminate()
            self._process.join(timeout=5.0)
        self._process = None

    def is_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    @property
    def worker_kind(self) -> Literal["process"]:
        return "process"
