"""Steuerung: Fragen erzeugen, prüfen, bewerten, fixen, Re-Test."""

from __future__ import annotations

import json
from pathlib import Path

from bot.chat import ChatStore
from bot.config.writers.team_admin import load_team_config
from bot.messages import open_message_service
from bot.messages.models import Message
from bot.verification.models import TeamWorkflow, VerificationQuestion
from bot.verification.parse import parse_questions_json, parse_verdict_json
from bot.verification.router import route_verification_check
from bot.verification.store import VerificationStore

MSG_GENERATE = "verify.generate"
MSG_CHECK = "verify.check"
MSG_REVIEW = "verify.review"
MSG_FIX = "verify.fix"
MSG_RETEST = "verify.retest"


def team_workflow(root: Path, team_id: str) -> TeamWorkflow:
    try:
        cfg = load_team_config(root, team_id)
        wf = getattr(cfg.team, "workflow", "tasks")
        if wf in ("tasks", "verification"):
            return wf  # type: ignore[return-value]
    except Exception:
        pass
    return "tasks"


def is_verification_team(root: Path, team_id: str) -> bool:
    return team_workflow(root, team_id) == "verification"


def question_payload(q: VerificationQuestion) -> str:
    return json.dumps(
        {
            "question_id": q.id,
            "seq": q.seq,
            "title": q.title,
            "question": q.question,
            "expectation": q.expectation,
            "check_method": q.check_method,
            "success_criteria": q.success_criteria,
        },
        ensure_ascii=False,
    )


def parse_question_payload(content: str) -> dict:
    start = content.find("{")
    if start < 0:
        return {"raw": content}
    try:
        return json.loads(content[start:])
    except json.JSONDecodeError:
        return {"raw": content}


def store_questions_from_llm(
    root: Path, team_id: str, llm_text: str
) -> list[VerificationQuestion]:
    store = VerificationStore(root, team_id)
    store.clear_questions()
    items = parse_questions_json(llm_text)
    created: list[VerificationQuestion] = []
    for item in items:
        if not item.get("question"):
            continue
        q = store.add_question(
            seq=int(item["seq"]),
            title=str(item["title"]),
            question=str(item["question"]),
            expectation=str(item.get("expectation", "")),
            check_method=item.get("check_method", "code"),  # type: ignore[arg-type]
            success_criteria=str(item.get("success_criteria", "")),
        )
        created.append(q)
    store.set_state("phase", "running")
    return created


def enqueue_check(
    root: Path,
    team_id: str,
    orch_id: str,
    question: VerificationQuestion,
    *,
    retest: bool = False,
) -> Message:
    route = route_verification_check(root, team_id, question.check_method)
    store = VerificationStore(root, team_id)
    store.update_question(question.id, status="checking")
    msg_type = MSG_RETEST if retest else MSG_CHECK
    body = (
        f"{'RE-TEST' if retest else 'PRÜFUNG'} — Aufgabe {question.seq:03d}: {question.title}\n\n"
        f"Prüfmethode: {route.check_method}\n"
        f"{route.method_hint}\n\n"
        f"Prüffrage:\n{question.question}\n\n"
        f"Erwartung:\n{question.expectation}\n\n"
        f"Erfolgskriterien:\n{question.success_criteria}\n\n"
        f"Liefere strukturierten Prüfbericht (Was geprüft, Was gefunden, Screenshots/Dateien)."
    )
    svc = open_message_service(root)
    return svc.send(
        team_id=team_id,
        from_agent=orch_id,
        to_agent=route.agent_id,
        subject=f"{'Re-Test' if retest else 'Prüfung'} {question.seq:03d}: {question.title}",
        content=body + "\n\n---\n" + question_payload(question),
        type=msg_type,
        task_category=route.task_category,
    )


def enqueue_review(
    root: Path,
    team_id: str,
    orch_id: str,
    review_id: str,
    question: VerificationQuestion,
    evidence: str,
) -> Message:
    store = VerificationStore(root, team_id)
    store.update_question(question.id, status="reviewing", evidence=evidence[:12000])
    body = (
        f"BEWERTUNG — Aufgabe {question.seq:03d}: {question.title}\n\n"
        f"Prüffrage:\n{question.question}\n\n"
        f"Nachweis des Prüf-Agents:\n{evidence}\n\n"
        "Bewerte nach Kriterien. Antworte NUR als JSON:\n"
        '{"verdict":"ja|nein|teilweise|unklar","reasons":"...","gaps":["..."],'
        '"fix_needed":true,"next_fix":"..."}'
    )
    svc = open_message_service(root)
    return svc.send(
        team_id=team_id,
        from_agent=orch_id,
        to_agent=review_id,
        subject=f"Bewertung {question.seq:03d}",
        content=body + "\n\n---\n" + question_payload(question),
        type=MSG_REVIEW,
        task_category="review",
    )


def enqueue_fix(
    root: Path,
    team_id: str,
    orch_id: str,
    execute_id: str,
    question: VerificationQuestion,
    fix_instruction: str,
) -> Message:
    store = VerificationStore(root, team_id)
    store.update_question(
        question.id, status="fixing", fix_notes=fix_instruction[:8000]
    )
    body = (
        f"FIX — Aufgabe {question.seq:03d}: {question.title}\n\n"
        f"Die Prüffrage wurde mit NEIN/TEILWEISE bewertet.\n\n"
        f"Prüffrage:\n{question.question}\n\n"
        f"Was fehlt / kaputt:\n{fix_instruction}\n\n"
        "Baue NUR diese Lücke — keine Nebenfeatures. Danach kurze Zusammenfassung."
    )
    svc = open_message_service(root)
    return svc.send(
        team_id=team_id,
        from_agent=orch_id,
        to_agent=execute_id,
        subject=f"Fix {question.seq:03d}: {question.title}",
        content=body + "\n\n---\n" + question_payload(question),
        type=MSG_FIX,
        task_category="coding",
    )


def start_next_check(root: Path, team_id: str, orch_id: str) -> Message | None:
    store = VerificationStore(root, team_id)
    nxt = store.next_open_question()
    if not nxt:
        store.set_state("phase", "complete")
        ChatStore(root, team_id).add(
            role="assistant",
            content="Alle Prüffragen abgeschlossen. Siehe Team → Prüfungen.",
            agent_id=orch_id,
            metadata={"verification_complete": True},
        )
        return None
    return enqueue_check(root, team_id, orch_id, nxt)


def apply_review_and_continue(
    root: Path,
    team_id: str,
    orch_id: str,
    pipe_execute: str,
    pipe_review: str,
    question_id: str,
    review_text: str,
) -> None:
    store = VerificationStore(root, team_id)
    q = store.get_question(question_id)
    if not q:
        return
    was_fixing = q.status == "fixing"
    verdict_data = parse_verdict_json(review_text)
    verdict = verdict_data["verdict"]
    notes = (
        f"{verdict_data.get('reasons', '')}\n\n"
        f"Fehlend:\n{verdict_data.get('gaps', '')}"
    ).strip()
    if verdict == "ja":
        store.update_question(
            question_id,
            status="passed",
            verdict=verdict,
            review_notes=notes,
        )
        start_next_check(root, team_id, orch_id)
        return
    if verdict == "unklar":
        store.update_question(
            question_id,
            status="open",
            verdict=verdict,
            review_notes=notes,
        )
        start_next_check(root, team_id, orch_id)
        return
    if was_fixing:
        store.update_question(
            question_id,
            status="failed",
            verdict=verdict,
            review_notes=notes,
        )
        start_next_check(root, team_id, orch_id)
        return
    fix_text = verdict_data.get("next_fix") or notes
    store.update_question(
        question_id,
        status="fixing",
        verdict=verdict,
        review_notes=notes,
    )
    enqueue_fix(root, team_id, orch_id, pipe_execute, q, fix_text)


def record_check_evidence_and_review(
    root: Path,
    team_id: str,
    orch_id: str,
    review_id: str,
    question_id: str,
    evidence: str,
) -> None:
    store = VerificationStore(root, team_id)
    q = store.get_question(question_id)
    if not q:
        return
    enqueue_review(root, team_id, orch_id, review_id, q, evidence)
