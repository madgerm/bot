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
        user_content: str | None = None,
    ) -> str:
        category = task_category or message.task_category or self.default_category
        if user_content is None:
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
                message_model_override=message.model_override,
            )
        except LlmError as exc:
            raise RuntimeError(str(exc)) from exc

    def handle_chat_direct(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        """Direkt-PM vom Panel — Dialog ohne Review-Pipeline."""
        from bot.chat.direct_chat import format_direct_context, record_direct_assistant

        agent_id = ctx.agent_id
        history = format_direct_context(ctx.root, ctx.team_id, agent_id)
        reply = self._run_with_tools(
            ctx,
            message,
            system_prompt=(
                "Du antwortest dem menschlichen Nutzer per Direkt-PM im Web-Panel. "
                "Antworte auf Deutsch, kurz und dialogisch. Keine Delegation an andere "
                "Agents, kein Review-Schritt — nur die direkte Antwort an den Nutzer. "
                "Tools nur bei Bedarf; keine künstliche done.summary-Struktur."
            ),
            task_category=message.task_category or self.default_category,
            user_content=(
                f"Direkt-Chat-Verlauf:\n{history}\n\n"
                f"Neue Nachricht:\n{message.content}\n\n"
                "Antworte dem Nutzer."
            ),
        )
        record_direct_assistant(
            ctx.root,
            ctx.team_id,
            agent_id,
            reply,
            internal_message_id=message.id,
        )
        return HandlerResult(complete=True)


class OrchestratorHandler(AgentHandler):
    role = "orchestrator"
    default_category = "planning"
    tools = _TOOLS_ORCH

    def handle(self, message: Message, ctx: HandlerContext) -> HandlerResult:
        pipe = _pipeline(ctx)

        if message.type in {"delegation_result", "hours_check_result"}:
            return HandlerResult(complete=True)

        from bot.verification.workflow import is_verification_team

        verification = is_verification_team(ctx.root, ctx.team_id)

        if message.type == "chat.user":
            from bot.chat import ChatStore
            from bot.chat.orchestrator_bridge import format_chat_context

            history = format_chat_context(ctx.root, ctx.team_id)
            if verification:
                prompt_user = (
                    f"Bisheriger Team-Chat:\n{history}\n\n"
                    f"Aktuelle Anfrage:\n{message.content}\n\n"
                    "Du bist der Requirement-Orchestrator (Fragen-Team). "
                    "Baue NICHTS. Kläre mit Rückfragen, was genau vorhanden sein soll. "
                    "Fasse am Ende Funktionen in Stichpunkten zusammen. "
                    "Der Nutzer muss freigeben — dann werden daraus nummerierte Prüffragen."
                )
                sys_prompt = (
                    "Du sprichst mit dem Team-Leiter. Deutsch, verständlich. "
                    "Kein Code, keine Implementierung — nur Anforderungen klären."
                )
            else:
                prompt_user = (
                    f"Bisheriger Team-Chat:\n{history}\n\n"
                    f"Aktuelle Anfrage:\n{message.content}\n\n"
                    "Du bist der Orchestrator. Erstelle einen klaren Plan: welche Schritte, "
                    "welche Agent-Rollen/IDs. Delegiere noch NICHT — der Nutzer muss "
                    "erst freigeben. Ende mit kurzer Zusammenfassung für den Nutzer."
                )
                sys_prompt = (
                    "Du sprichst mit dem menschlichen Team-Leiter im Panel-Chat. "
                    "Antworte auf Deutsch, verständlich, ohne interne JSON-Formate."
                )
            plan = self._run_with_tools(
                ctx,
                message,
                system_prompt=sys_prompt,
                task_category="planning",
                user_content=prompt_user,
            )
            ChatStore(ctx.root, ctx.team_id).add(
                role="assistant",
                content=plan,
                agent_id=ctx.agent_id,
                metadata={"awaiting_approval": True, "internal_message_id": message.id},
            )
            return HandlerResult(complete=True)

        if message.type == "chat.approve":
            from bot.chat import ChatStore
            from bot.chat.orchestrator_bridge import format_chat_context

            history = format_chat_context(ctx.root, ctx.team_id)
            if verification:
                from bot.verification.workflow import (
                    start_next_check,
                    store_questions_from_llm,
                )

                prompt_user = (
                    f"Team-Chat (freigegeben):\n{history}\n\n"
                    "Erzeuge eine JSON-Liste von Prüffragen. Jede Frage klein und prüfbar.\n"
                    "Antworte NUR mit einem JSON-Array in einem ```json Block:\n"
                    '[{"seq":1,"title":"...","question":"Ist ...?","expectation":"...",'
                    '"check_method":"browser|code|db|api|mixed","success_criteria":"..."}]'
                )
                generated = self._run_with_tools(
                    ctx,
                    message,
                    system_prompt=(
                        "Requirement-Orchestrator. Erzeuge 8–25 Prüffragen aus dem Gespräch. "
                        "check_method passend wählen. Kein Fließtext außerhalb JSON."
                    ),
                    task_category="planning",
                    user_content=prompt_user,
                )
                questions = store_questions_from_llm(
                    ctx.root, ctx.team_id, generated
                )
                summary = (
                    f"Freigegeben — {len(questions)} Prüffragen erzeugt. "
                    "Die erste Prüfung startet automatisch.\n\n"
                    f"Siehe Panel → Prüfungen oder `teams/{ctx.team_id}/verification/`."
                )
                ChatStore(ctx.root, ctx.team_id).add(
                    role="assistant",
                    content=summary,
                    agent_id=ctx.agent_id,
                    metadata={"awaiting_approval": False},
                )
                start_next_check(ctx.root, ctx.team_id, ctx.agent_id)
                return HandlerResult(complete=True)

            prompt_user = (
                f"Team-Chat:\n{history}\n\n"
                "Der Nutzer hat den Plan freigegeben (z. B. „so ist top“). "
                "Setze jetzt um: formuliere die Aufgabe für den Ausführungs-Agenten."
            )
            plan = self._run_with_tools(
                ctx,
                message,
                system_prompt=(
                    "Orchestrator nach Freigabe. Nutze Tools wenn nötig. "
                    "Danach kurze Bestätigung für den Nutzer-Chat."
                ),
                task_category="planning",
                user_content=prompt_user,
            )
            ChatStore(ctx.root, ctx.team_id).add(
                role="assistant",
                content=f"Freigegeben — Aufgabe an {pipe.execute_id} delegiert.\n\n{plan}",
                agent_id=ctx.agent_id,
                metadata={"awaiting_approval": False},
            )
            body = f"{message.content.rstrip()}\n\n--- Ausführung ---\n{plan}"
            return HandlerResult(
                complete=True,
                delegates=[
                    DelegateRequest(
                        to_agent=pipe.execute_id,
                        subject=message.subject or "Chat-Aufgabe",
                        content=body,
                        type="task",
                        task_category=message.task_category or "coding",
                    )
                ],
            )

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
        if message.type == "chat.direct":
            return self.handle_chat_direct(message, ctx)

        from bot.verification.workflow import (
            MSG_CHECK,
            MSG_FIX,
            MSG_RETEST,
            parse_question_payload,
            record_check_evidence_and_review,
        )

        if message.type in (MSG_CHECK, MSG_RETEST):
            pipe = _pipeline(ctx)
            payload = parse_question_payload(message.content)
            qid = str(payload.get("question_id", ""))
            evidence = self._run_with_tools(
                ctx,
                message,
                system_prompt=(
                    "Du bist ein Prüf-Agent. Führe NUR die eine Prüffrage aus. "
                    "Kein Bauen, kein Refactoring — nur prüfen und dokumentieren."
                ),
                task_category=message.task_category or "review",
            )
            if qid:
                record_check_evidence_and_review(
                    ctx.root,
                    ctx.team_id,
                    pipe.orchestrator_id,
                    pipe.review_id,
                    qid,
                    evidence,
                )
            return HandlerResult(complete=True)

        if message.type == MSG_FIX:
            from bot.verification.workflow import enqueue_check
            from bot.verification.store import VerificationStore

            pipe = _pipeline(ctx)
            payload = parse_question_payload(message.content)
            qid = str(payload.get("question_id", ""))
            self._run_with_tools(
                ctx,
                message,
                system_prompt=(
                    "Du bist ein Fix-Agent. Behebe NUR die beschriebene Lücke. "
                    "Keine Zusatzfeatures."
                ),
                task_category="coding",
            )
            store = VerificationStore(ctx.root, ctx.team_id)
            q = store.get_question(qid) if qid else None
            if q:
                enqueue_check(
                    ctx.root,
                    ctx.team_id,
                    pipe.orchestrator_id,
                    q,
                    retest=True,
                )
            return HandlerResult(complete=True)

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
        if message.type == "chat.direct":
            return self.handle_chat_direct(message, ctx)

        from bot.verification.workflow import (
            MSG_REVIEW,
            apply_review_and_continue,
            parse_question_payload,
        )

        if message.type == MSG_REVIEW:
            pipe = _pipeline(ctx)
            payload = parse_question_payload(message.content)
            qid = str(payload.get("question_id", ""))
            review = self._run_with_tools(
                ctx,
                message,
                system_prompt=(
                    "Du bist die Kontroll-Instanz. Bewerte den Prüf-Nachweis nach Kriterien. "
                    "Antworte NUR als JSON: "
                    '{"verdict":"ja|nein|teilweise|unklar","reasons":"...",'
                    '"gaps":["..."],"fix_needed":true,"next_fix":"..."}'
                ),
                task_category="review",
            )
            if qid:
                apply_review_and_continue(
                    ctx.root,
                    ctx.team_id,
                    pipe.orchestrator_id,
                    pipe.execute_id,
                    pipe.review_id,
                    qid,
                    review,
                )
            return HandlerResult(complete=True)

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
        if message.type == "chat.direct":
            return self.handle_chat_direct(message, ctx)

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
