"""Rollenbasierte Message-Handler mit LLM (LiteLLM) oder Stub."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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


def _story_team(ctx: HandlerContext) -> bool:
    return (ctx.root / "data" / ctx.team_id / "story" / "meta.json").is_file()


def _checker_agent_ids(ctx: HandlerContext) -> list[str]:
    from bot.story.config import load_story_review_config

    cfg = load_story_review_config(ctx.root, ctx.team_id)
    return [c.agent_id for c in cfg.checkers if c.enabled]


class StoryOrchestratorHandler(AgentHandler):
    """Story-Team: plant und delegiert an drehbuch-autor; sammelt Prüfer-Ergebnisse."""

    role = "orchestrator"
    default_category = "story_planning"

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        if message.type in ("delegation_result", "review_result"):
            return HandlerResult(complete=True)
        if message.from_agent in _STORY_CHECKER_ROLES or message.from_agent in _checker_agent_ids(
            ctx
        ):
            return HandlerResult(complete=True)

        plan = self._complete(
            ctx,
            message,
            system_prompt=(
                "Du bist der Story-Orchestrator. Erstelle einen kurzen Plan "
                "für den Drehbuch-Autor (max. 5 Sätze)."
            ),
            task_category="story_planning",
        )
        body = f"{message.content.rstrip()}\n\n--- Story-Plan ---\n{plan}"
        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent="drehbuch-autor",
                    subject=message.subject,
                    content=body,
                    type=message.type,
                    task_category="scene_writing",
                )
            ],
        )


class StoryWriterHandler(AgentHandler):
    """Drehbuch-Autor: Szene ausarbeiten, dann parallele Review an alle Prüfer-Inboxen."""

    role = "story_writer"
    default_category = "scene_writing"

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        result = self._complete(
            ctx,
            message,
            system_prompt=(
                "Du bist Drehbuch-Autor. Bearbeite die Szene knapp aber konkret "
                "(max. 12 Sätze Prosa oder Stichpunkte)."
            ),
            task_category="scene_writing",
        )
        executed = f"{message.content.rstrip()}\n\n--- Szene ---\n{result}"
        from bot.story.config import load_story_review_config

        delegates = [
            DelegateRequest(
                to_agent=c.agent_id,
                subject=f"Review: {message.subject}",
                content=executed,
                type="review_task",
                task_category=c.task_category,
            )
            for c in load_story_review_config(ctx.root, ctx.team_id).checkers
            if c.enabled
        ]
        return HandlerResult(complete=True, delegates=delegates)


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


class StoryCheckerHandler(AgentHandler):
    """Story-Prüfer (logik, world, character, …) — kurzes Review, zurück an Orchestrator."""

    default_category = "logic_check"

    def __init__(self, *, task_category: str = "logic_check", checker_name: str = "checker") -> None:
        self.task_category = task_category
        self.checker_name = checker_name
        self.role = "reviewer"

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        category = message.task_category or self.task_category
        review = self._complete(
            ctx,
            message,
            system_prompt=(
                f"Du bist der Story-Prüfer '{self.checker_name}'. "
                "Prüfe die Szene. Antworte mit OK oder kurzer ISSUE-Liste."
            ),
            task_category=category,
        )
        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent="orchestrator",
                    subject=f"Review {self.checker_name}: {message.subject}",
                    content=review,
                    type="review_result",
                    task_category=category,
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


_STORY_CHECKER_ROLES: dict[str, tuple[str, str]] = {
    "logik-pruefer": ("logic_check", "Logik-Prüfer"),
    "worldkeeper": ("world_consistency", "Worldkeeper"),
    "character-manager": ("character_consistency", "Character-Manager"),
    "stil-pruefer": ("style_check", "Stil-Prüfer"),
    "deutsch-pruefer": ("grammar_check", "Deutsch-Prüfer"),
    "zeit-pruefer": ("tense_check", "Zeit-Prüfer"),
    "detail-pruefer": ("detail_check", "Detail-Prüfer"),
}


def handler_for_role(
    role: str,
    *,
    team_id: str | None = None,
    root: Path | None = None,
) -> AgentHandler:
    if role in _STORY_CHECKER_ROLES:
        cat, name = _STORY_CHECKER_ROLES[role]
        return StoryCheckerHandler(task_category=cat, checker_name=name)
    if role == "orchestrator" and root and team_id:
        if (root / "data" / team_id / "story" / "meta.json").is_file():
            return StoryOrchestratorHandler()
    if role == "story_writer":
        return StoryWriterHandler()
    mapping: dict[str, AgentHandler] = {
        "orchestrator": OrchestratorHandler(),
        "worker": WorkerExecHandler(),
        "reviewer": ReviewerHandler(),
        "story_writer": WorkerExecHandler(),
        "story_reviewer": ReviewerHandler(),
        "coder": WorkerExecHandler(),
        "tester": ReviewerHandler(),
    }
    if role not in mapping:
        raise ValueError(f"Kein Handler für Rolle '{role}'")
    return mapping[role]
