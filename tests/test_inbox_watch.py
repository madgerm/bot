"""Inbox-Watch: schnelle Reaktion auf neue Messages."""

import time
from pathlib import Path

from bot.messages.inbox_watch import inbox_pending_snapshot
from bot.messages.paths import agent_inbox
from bot.runtime.agent import AgentRunner
from bot.runtime.handlers import AgentHandler, HandlerResult
from bot.config.models import AgentBlock, AgentConfig


def test_inbox_snapshot_detects_new_file(runtime_project: Path) -> None:
    inbox = agent_inbox(
        runtime_project, "alpha", "worker-exec", "teams/{team_id}/agents/{agent_id}/inbox"
    )
    inbox.mkdir(parents=True, exist_ok=True)
    snap1 = inbox_pending_snapshot(inbox)
    path = inbox / "test-msg.json"
    path.write_text("{}", encoding="utf-8")
    snap2 = inbox_pending_snapshot(inbox)
    assert snap2 != snap1


class _ImmediateHandler(AgentHandler):
    role = "worker"

    def handle(self, message, ctx) -> HandlerResult:
        return HandlerResult(complete=True)


def test_agent_runner_processes_on_watch(runtime_project: Path) -> None:
    from bot.llm import build_llm_stack
    from bot.config import load_runtime_config

    config = load_runtime_config(runtime_project)
    stack = build_llm_stack(config)
    agent_cfg = AgentConfig(
        agent=AgentBlock(id="worker-exec", role="worker", enabled=True),
    )
    from bot.messages import MessageService

    svc = MessageService(runtime_project)
    svc.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="worker-exec",
        subject="Watch",
        content="Ping",
    )

    runner = AgentRunner(
        root=runtime_project,
        team_id="alpha",
        agent_cfg=agent_cfg,
        default_interval=5.0,
        inbox_watch_seconds=0.1,
        inbox_template=config.system.system.communication.inbox_base,
        llm_stack=stack,
        handler=_ImmediateHandler(),
    )
    runner.start()
    try:
        deadline = time.monotonic() + 3.0
        done = False
        while time.monotonic() < deadline:
            inbox = agent_inbox(
                runtime_project,
                "alpha",
                "worker-exec",
                config.system.system.communication.inbox_base,
            )
            processed = inbox / "processed"
            if processed.is_dir() and list(processed.glob("*.json")):
                done = True
                break
            time.sleep(0.05)
        assert done, "Message wurde nicht innerhalb des Watch-Fensters verarbeitet"
    finally:
        runner.stop()
