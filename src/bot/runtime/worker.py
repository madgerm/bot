"""Factory für Agent-Worker (Thread vs. Subprozess)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from bot.config.models import AgentConfig
from bot.llm import LlmStack
from bot.runtime.agent import AgentRunner
from bot.runtime.agent_process import AgentProcessRunner
from bot.runtime.handlers import AgentHandler

WorkerMode = Literal["thread", "process"]


class AgentWorker(Protocol):
    team_id: str
    agent_id: str
    enabled: bool
    worker_kind: Literal["thread", "process"]

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def tick(self) -> bool: ...
    def is_alive(self) -> bool: ...


def create_agent_worker(
    *,
    root: Path,
    team_id: str,
    agent_cfg: AgentConfig,
    default_interval: float,
    inbox_watch_seconds: float,
    inbox_template: str,
    llm_stack: LlmStack,
    worker_mode: WorkerMode,
    handler: AgentHandler | None = None,
) -> AgentRunner | AgentProcessRunner:
    if worker_mode == "process":
        return AgentProcessRunner(
            root=root,
            team_id=team_id,
            agent_cfg=agent_cfg,
            default_interval=default_interval,
            inbox_watch_seconds=inbox_watch_seconds,
            inbox_template=inbox_template,
        )
    return AgentRunner(
        root=root,
        team_id=team_id,
        agent_cfg=agent_cfg,
        default_interval=default_interval,
        inbox_watch_seconds=inbox_watch_seconds,
        inbox_template=inbox_template,
        llm_stack=llm_stack,
        handler=handler,
    )
