"""Team-Runtime: alle Agents eines Teams."""

from __future__ import annotations

from pathlib import Path

from bot.config.models import TeamBundle
from bot.llm import LlmStack
from bot.runtime.agent import AgentRunner


class TeamRuntime:
    def __init__(
        self,
        *,
        root: Path,
        team_id: str,
        bundle: TeamBundle,
        default_interval: float,
        inbox_watch_seconds: float,
        inbox_template: str,
        llm_stack: LlmStack,
    ) -> None:
        self.team_id = team_id
        self._runners: list[AgentRunner] = []

        orch_id = bundle.team.team.orchestrator_id
        agent_items = list(bundle.agents.items())

        def sort_key(item: tuple[str, object]) -> tuple[int, str]:
            agent_id, cfg = item
            if agent_id == orch_id:
                return (0, agent_id)
            role_order = {"worker": 1, "reviewer": 2, "orchestrator": 0}
            return (role_order.get(cfg.agent.role, 9), agent_id)

        for agent_id, agent_cfg in sorted(agent_items, key=sort_key):
            if not agent_cfg.agent.enabled:
                continue
            self._runners.append(
                AgentRunner(
                    root=root,
                    team_id=team_id,
                    agent_cfg=agent_cfg,
                    default_interval=default_interval,
                    inbox_watch_seconds=inbox_watch_seconds,
                    inbox_template=inbox_template,
                    llm_stack=llm_stack,
                )
            )

    @property
    def agents(self) -> list[AgentRunner]:
        return list(self._runners)

    def start(self) -> None:
        for runner in self._runners:
            runner.start()

    def stop(self) -> None:
        for runner in self._runners:
            runner.stop()

    def tick_round(self) -> int:
        """Ein Durchlauf: jeder Agent einmal. Gibt Anzahl verarbeiteter Messages zurück."""
        processed = 0
        for runner in self._runners:
            if runner.tick():
                processed += 1
        return processed

    def run_until_idle(self, *, max_rounds: int = 20) -> int:
        total = 0
        for _ in range(max_rounds):
            count = self.tick_round()
            total += count
            if count == 0:
                break
        return total
