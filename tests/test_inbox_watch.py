"""Inbox-Watch und Agent-Worker."""

import json
import time
from pathlib import Path

import pytest

from bot.config.models import AgentBlock, AgentConfig
from bot.messages.inbox_watch import InboxWatcher, inbox_pending_snapshot
from bot.messages.paths import agent_inbox
from bot.runtime.agent import AgentRunner
from bot.runtime.agent_process import AgentProcessRunner
from bot.runtime.handlers import AgentHandler, HandlerResult


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


def test_inbox_watcher_sets_wake_event(runtime_project: Path) -> None:
    import threading

    inbox = agent_inbox(
        runtime_project, "alpha", "worker-exec", "teams/{team_id}/agents/{agent_id}/inbox"
    )
    inbox.mkdir(parents=True, exist_ok=True)
    wake = threading.Event()
    stop = threading.Event()
    watcher = InboxWatcher(
        inbox, interval_seconds=0.1, wake_event=wake, stop_event=stop
    )
    watcher.start()
    try:
        assert not wake.wait(timeout=0.3)
        (inbox / "neu.json").write_text("{}", encoding="utf-8")
        assert wake.wait(timeout=1.0)
    finally:
        stop.set()
        watcher.stop()


class _ImmediateHandler(AgentHandler):
    role = "worker"

    def handle(self, message, ctx) -> HandlerResult:
        return HandlerResult(complete=True)


def test_agent_reacts_via_watch_before_idle_interval(runtime_project: Path) -> None:
    """Neue Message während langem interval_seconds — Reaktion in Sekunden, nicht Minuten."""
    from bot.config import load_runtime_config
    from bot.llm import build_llm_stack
    from bot.messages import MessageService

    config = load_runtime_config(runtime_project)
    stack = build_llm_stack(config)
    agent_cfg = AgentConfig(
        agent=AgentBlock(id="worker-exec", role="worker", enabled=True),
    )

    runner = AgentRunner(
        root=runtime_project,
        team_id="alpha",
        agent_cfg=agent_cfg,
        default_interval=60.0,
        inbox_watch_seconds=0.1,
        inbox_template=config.system.system.communication.inbox_base,
        llm_stack=stack,
        handler=_ImmediateHandler(),
    )
    runner.start()
    try:
        time.sleep(0.25)
        svc = MessageService(runtime_project)
        t0 = time.monotonic()
        svc.send(
            team_id="alpha",
            from_agent="orchestrator",
            to_agent="worker-exec",
            subject="Watch",
            content="Ping",
        )
        inbox = agent_inbox(
            runtime_project,
            "alpha",
            "worker-exec",
            config.system.system.communication.inbox_base,
        )
        processed = inbox / "processed"
        while time.monotonic() - t0 < 2.0:
            if processed.is_dir() and list(processed.glob("*.json")):
                assert time.monotonic() - t0 < 2.0
                return
            time.sleep(0.05)
        pytest.fail("Inbox-Watch hat nicht schnell genug reagiert")
    finally:
        runner.stop()


def test_agent_process_runner(runtime_project: Path) -> None:
    from bot.config import load_runtime_config

    config = load_runtime_config(runtime_project)
    agent_cfg = AgentConfig(
        agent=AgentBlock(id="worker-exec", role="worker", enabled=True),
    )
    runner = AgentProcessRunner(
        root=runtime_project,
        team_id="alpha",
        agent_cfg=agent_cfg,
        default_interval=5.0,
        inbox_watch_seconds=0.2,
        inbox_template=config.system.system.communication.inbox_base,
    )
    runner.start()
    try:
        assert runner.is_alive()
        assert runner.worker_kind == "process"
    finally:
        runner.stop()
        assert not runner.is_alive()


def test_supervisor_process_mode(runtime_project: Path) -> None:
    system_path = runtime_project / "config" / "system.json"
    data = json.loads(system_path.read_text(encoding="utf-8"))
    data["system"]["polling"]["worker_mode"] = "process"
    system_path.write_text(json.dumps(data), encoding="utf-8")

    from bot.runtime import Supervisor

    supervisor = Supervisor(runtime_project)
    supervisor.start(team_ids=["alpha"])
    try:
        workers = supervisor.status()["workers"]
        assert len(workers) == 3
        assert all(w["worker_kind"] == "process" for w in workers)
        assert all(w["alive"] for w in workers)
    finally:
        supervisor.stop()
