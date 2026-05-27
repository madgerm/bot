"""Rollenbasierte Message-Handler mit LLM (LiteLLM) oder Stub."""

from __future__ import annotations

from dataclasses import dataclass, field

from bot.llm import LlmError
from bot.messages.models import Message
from bot.runtime.context import HandlerContext


@dataclass
class DelegateRequest:
    to_agent: str
    subject: str
    content: str
    type: str = "task"
    task_category: str | None = None


@dataclass
class HandlerResult:
    complete: bool = True
    error: str | None = None
    delegates: list[DelegateRequest] = field(default_factory=list)


class AgentHandler:
    role: str
    default_category: str

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        raise NotImplementedError

    def _complete(
        self,
        ctx: HandlerContext,
        message: Message,
        *,
        system_prompt: str,
        task_category: str | None = None,
    ) -> str:
        category = task_category or message.task_category or self.default_category
        model = ctx.llm_stack.router.resolve(
            category, role=ctx.role, override=message.model_override
        )
        fallbacks = ctx.llm_stack.router.fallbacks(category, role=ctx.role)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Betreff: {message.subject}\n\n{message.content}",
            },
        ]
        try:
            return ctx.llm_stack.client.complete(
                model, messages, fallbacks=fallbacks or None
            )
        except LlmError as exc:
            raise RuntimeError(str(exc)) from exc


class OrchestratorHandler(AgentHandler):
    role = "orchestrator"
    default_category = "planning"

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        if message.type == "delegation_result":
            return HandlerResult(complete=True)

        if message.from_agent == "worker-review":
            return HandlerResult(complete=True)

        if message.from_agent in {"worker-exec", "worker-review"}:
            return HandlerResult(complete=True)

        plan = self._complete(
            ctx,
            message,
            system_prompt=(
                "Du bist ein Orchestrator. Erstelle einen kurzen Ausführungsplan "
                "(max. 5 Sätze) für den Worker-Agenten. Nur der Plan, keine Begrüßung."
            ),
            task_category="planning",
        )
        body = f"{message.content.rstrip()}\n\n--- Orchestrator-Plan ---\n{plan}"
        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent="worker-exec",
                    subject=message.subject,
                    content=body,
                    type=message.type,
                    task_category=message.task_category or "coding",
                )
            ],
        )


class WorkerExecHandler(AgentHandler):
    role = "worker"
    default_category = "coding"

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        result = self._complete(
            ctx,
            message,
            system_prompt=(
                "Du bist ein Ausführungs-Agent. Bearbeite die Aufgabe knapp "
                "(max. 8 Sätze). Beschreibe konkrete Schritte oder ein Ergebnis."
            ),
            task_category="coding",
        )
        executed = f"{message.content.rstrip()}\n\n--- Ausführung ---\n{result}"
        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent="worker-review",
                    subject=f"Review: {message.subject}",
                    content=executed,
                    type="review_task",
                    task_category="review",
                )
            ],
        )


class ReviewerHandler(AgentHandler):
    role = "reviewer"
    default_category = "review"

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        review = self._complete(
            ctx,
            message,
            system_prompt=(
                "Du bist ein Review-Agent. Prüfe die Arbeit. "
                "Antworte mit APPROVED oder LISTE VON PROBLEMEN (kurz)."
            ),
            task_category="review",
        )
        reviewed = f"{message.content.rstrip()}\n\n--- Review ---\n{review}"
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
