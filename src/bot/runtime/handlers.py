"""Rollenbasierte Message-Handler (MVP ohne LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field

from bot.messages.models import Message


@dataclass
class DelegateRequest:
    to_agent: str
    subject: str
    content: str
    type: str = "task"
    task_category: str | None = None


@dataclass
class HandlerResult:
    """Ergebnis einer Message-Verarbeitung."""

    complete: bool = True
    error: str | None = None
    delegates: list[DelegateRequest] = field(default_factory=list)


class AgentHandler:
    role: str

    def handle(self, message: Message, *, agent_id: str, team_id: str) -> HandlerResult:
        raise NotImplementedError


class OrchestratorHandler(AgentHandler):
    role = "orchestrator"

    def handle(self, message: Message, *, agent_id: str, team_id: str) -> HandlerResult:
        if message.type == "delegation_result":
            return HandlerResult(complete=True)

        if message.from_agent == "worker-review":
            return HandlerResult(complete=True)

        if message.from_agent in {"worker-exec", "worker-review"}:
            return HandlerResult(complete=True)

        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent="worker-exec",
                    subject=message.subject,
                    content=message.content,
                    type=message.type,
                    task_category=message.task_category,
                )
            ],
        )


class WorkerExecHandler(AgentHandler):
    role = "worker"

    def handle(self, message: Message, *, agent_id: str, team_id: str) -> HandlerResult:
        executed = f"{message.content.rstrip()}\n\n[ausgeführt von {agent_id}]"
        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent="worker-review",
                    subject=f"Review: {message.subject}",
                    content=executed,
                    type="review_task",
                    task_category=message.task_category,
                )
            ],
        )


class ReviewerHandler(AgentHandler):
    role = "reviewer"

    def handle(self, message: Message, *, agent_id: str, team_id: str) -> HandlerResult:
        reviewed = f"{message.content.rstrip()}\n\n[geprüft von {agent_id}: ok]"
        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent="orchestrator",
                    subject=f"Ergebnis: {message.subject}",
                    content=reviewed,
                    type="delegation_result",
                    task_category=message.task_category,
                )
            ],
        )


def handler_for_role(role: str) -> AgentHandler:
    mapping: dict[str, AgentHandler] = {
        "orchestrator": OrchestratorHandler(),
        "worker": WorkerExecHandler(),
        "reviewer": ReviewerHandler(),
    }
    if role not in mapping:
        raise ValueError(f"Kein Handler für Rolle '{role}'")
    return mapping[role]
