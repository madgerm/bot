"""Task-Service mit optionaler Message-Benachrichtigung."""

from __future__ import annotations

from pathlib import Path

from bot.tasks.store import TaskRecord, TaskStatus, TaskStore, TaskStoreError


class TaskServiceError(Exception):
    pass


class TaskService:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.store = TaskStore(root, team_id)

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> TaskService:
        return cls(Path(root), team_id)

    def create(
        self,
        *,
        title: str,
        description: str = "",
        assignee_agent: str | None = None,
        created_by: str | None = None,
        notify_agent: bool = False,
    ) -> TaskRecord:
        task = self.store.create(
            title=title,
            description=description,
            assignee_agent=assignee_agent,
            created_by=created_by,
        )
        if notify_agent and assignee_agent:
            self._notify_agent(assignee_agent, task)
        return task

    def move(self, task_id: str, status: TaskStatus) -> TaskRecord:
        try:
            return self.store.update(task_id, status=status)
        except TaskStoreError as exc:
            raise TaskServiceError(str(exc)) from exc

    def _notify_agent(self, agent_id: str, task: TaskRecord) -> None:
        from bot.config import load_runtime_config
        from bot.messages import MessageError, MessageService

        cfg = load_runtime_config(self.root)
        bundle = cfg.teams.get(self.team_id)
        if not bundle:
            return
        orch_id = bundle.team.team.orchestrator_id
        try:
            MessageService(self.root).send(
                team_id=self.team_id,
                from_agent=orch_id,
                to_agent=agent_id,
                subject=f"Task: {task.title}",
                content=task.description or task.title,
                type="task",
            )
        except MessageError:
            pass
