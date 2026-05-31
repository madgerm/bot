"""Rollenbasierte Message-Handler mit LLM, Tools und Team-Pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from bot.config.loader import discover_teams
from bot.config.models import TeamBundle
from bot.llm import LlmError
from bot.messages.models import Message
from bot.runtime.agent_tools import resolve_allowed_tools
from bot.runtime.context import HandlerContext
from bot.runtime.pipeline import ResolvedPipeline, resolve_pipeline
from bot.runtime.tools import TOOL_NAMES, run_tool_loop


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


_TOOLS_EXEC = frozenset(
    {
        "read_file",
        "write_file",
        "list_files",
        "git_status",
        "git_commit",
        "qdrant_search",
        "browser_open",
        "story_read_scene",
        "story_write_scene",
        "index_workspace",
    }
)
_TOOLS_ORCH = frozenset(
    {"read_file", "list_files", "qdrant_search", "index_workspace", "git_status"}
)
_TOOLS_REVIEW = frozenset(
    {
        "read_file",
        "list_files",
        "qdrant_search",
        "story_read_scene",
        "git_status",
    }
)
_TOOLS_DOC = frozenset({"read_file", "write_file", "list_files", "git_status", "git_commit"})


def _bundle(ctx: HandlerContext) -> TeamBundle:
    teams = discover_teams(ctx.root / "teams")
    bundle = teams.get(ctx.team_id)
    if not bundle:
        raise RuntimeError(f"Team '{ctx.team_id}' nicht in der Konfiguration")
    return bundle


def _pipeline(ctx: HandlerContext) -> ResolvedPipeline:
    return resolve_pipeline(_bundle(ctx))


class AgentHandler:
    role: str
    default_category: str
    tools: frozenset[str] = TOOL_NAMES

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        raise NotImplementedError

    def _run_with_tools(
        self,
        ctx: HandlerContext,
        message: Message,
        *,
        system_prompt: str,
        task_category: str | None = None,
        tools: frozenset[str] | None = None,
    ) -> str:
        category = task_category or message.task_category or self.default_category
        user_content = f"Betreff: {message.subject}\n\n{message.content}"
        effective_tools = (
            tools if tools is not None else resolve_allowed_tools(ctx.role, ctx.agent)
        )
        prompt = system_prompt
        if ctx.agent and ctx.agent.system_prompt_extra:
            prompt = f"{prompt}\n\n{ctx.agent.system_prompt_extra}"
        try:
            return run_tool_loop(
                ctx,
                system_prompt=prompt,
                user_content=user_content,
                task_category=category,
                tools=effective_tools,
            )
        except LlmError as exc:
            raise RuntimeError(str(exc)) from exc


class OrchestratorHandler(AgentHandler):
    role = "orchestrator"
    default_category = "planning"
    tools = _TOOLS_ORCH

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        pipe = _pipeline(ctx)

        if message.type in {"delegation_result", "hours_check_result"}:
            return HandlerResult(complete=True)

        if message.from_agent == pipe.review_id:
            return HandlerResult(complete=True)

        if message.from_agent in {pipe.execute_id, pipe.review_id}:
            return HandlerResult(complete=True)

        plan = self._run_with_tools(
            ctx,
            message,
            system_prompt=(
                "Du bist ein Orchestrator. Erstelle einen kurzen Ausführungsplan "
                "(max. 8 Sätze) für den Ausführungs-Agenten. Nutze Tools wenn nötig "
                "(Kontext lesen, Wissen suchen). Beende mit done und summary."
            ),
            task_category="planning",
        )
        body = f"{message.content.rstrip()}\n\n--- Orchestrator-Plan ---\n{plan}"
        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent=pipe.execute_id,
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
    tools = _TOOLS_EXEC

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        pipe = _pipeline(ctx)
        result = self._run_with_tools(
            ctx,
            message,
            system_prompt=(
                "Du bist ein Ausführungs-Agent (Coding oder Story). "
                "Nutze Tools: Dateien lesen/schreiben, Git, Qdrant, Browser, Story-Szenen. "
                "Führe die Aufgabe aus und fasse das Ergebnis in done.summary zusammen."
            ),
            task_category=message.task_category or "coding",
        )
        executed = f"{message.content.rstrip()}\n\n--- Ausführung ---\n{result}"
        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent=pipe.review_id,
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
    tools = _TOOLS_REVIEW

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        pipe = _pipeline(ctx)
        review = self._run_with_tools(
            ctx,
            message,
            system_prompt=(
                "Du bist ein Review-Agent. Prüfe die Arbeit mit Tools wenn nötig. "
                "Antworte in done.summary mit APPROVED oder LISTE VON PROBLEMEN (kurz)."
            ),
            task_category="review",
        )
        reviewed = f"{message.content.rstrip()}\n\n--- Review ---\n{review}"
        delegates = [
            DelegateRequest(
                to_agent=pipe.orchestrator_id,
                subject=f"Ergebnis: {message.subject}",
                content=reviewed,
                type="delegation_result",
                task_category=message.task_category,
            )
        ]
        if pipe.document_id and "APPROVED" in review.upper():
            delegates.append(
                DelegateRequest(
                    to_agent=pipe.document_id,
                    subject=f"Doku: {message.subject}",
                    content=reviewed,
                    type="documentation_task",
                    task_category="documentation",
                )
            )
        return HandlerResult(complete=True, delegates=delegates)


class DocumenterHandler(AgentHandler):
    role = "documenter"
    default_category = "documentation"
    tools = _TOOLS_DOC

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        pipe = _pipeline(ctx)
        doc = self._run_with_tools(
            ctx,
            message,
            system_prompt=(
                "Du bist ein Doku-Agent. Erstelle oder aktualisiere Dokumentation "
                "(README, Kommentare, Story-Notizen) mit den Datei- und Git-Tools. "
                "Beende mit done.summary."
            ),
            task_category="documentation",
        )
        documented = f"{message.content.rstrip()}\n\n--- Dokumentation ---\n{doc}"
        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent=pipe.orchestrator_id,
                    subject=f"Doku fertig: {message.subject}",
                    content=documented,
                    type="delegation_result",
                    task_category="documentation",
                )
            ],
        )


class HoursCheckerHandler(AgentHandler):
    role = "hours_checker"
    default_category = "review"
    tools = frozenset({"browser_open"})

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        from bot.hours.service import HoursService, HoursServiceError

        try:
            service = HoursService.for_team(ctx.root, ctx.team_id)
            record = service.check(llm_stack=ctx.llm_stack)
            summary = service.format_check_summary(record)
        except HoursServiceError as exc:
            return HandlerResult(complete=True, error=str(exc))

        body = (
            f"{message.content.rstrip()}\n\n--- Öffnungszeiten-Prüfung ---\n{summary}"
            if message.content.strip()
            else summary
        )
        pipe = _pipeline(ctx)
        return HandlerResult(
            complete=True,
            delegates=[
                DelegateRequest(
                    to_agent=pipe.orchestrator_id,
                    subject=f"Öffnungszeiten: {message.subject or 'Abgleich'}",
                    content=body,
                    type="hours_check_result",
                )
            ],
        )


def handler_for_role(role: str) -> AgentHandler:
    mapping: dict[str, AgentHandler] = {
        "orchestrator": OrchestratorHandler(),
        "worker": WorkerExecHandler(),
        "reviewer": ReviewerHandler(),
        "story_writer": WorkerExecHandler(),
        "story_reviewer": ReviewerHandler(),
        "coder": WorkerExecHandler(),
        "tester": ReviewerHandler(),
        "documenter": DocumenterHandler(),
        "hours_checker": HoursCheckerHandler(),
    }
    if role not in mapping:
        raise ValueError(f"Kein Handler für Rolle '{role}'")
    return mapping[role]
