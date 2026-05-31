"""Markdown-Spiegel: teams/<id>/verification/questions|results|fixes."""

from __future__ import annotations

from pathlib import Path

from bot.verification.models import VerificationQuestion


def verification_dir(root: Path, team_id: str) -> Path:
    return root / "teams" / team_id / "verification"


def sync_verification_files(
    root: Path, team_id: str, questions: list[VerificationQuestion]
) -> None:
    base = verification_dir(root, team_id)
    qdir = base / "questions"
    rdir = base / "results"
    fdir = base / "fixes"
    for d in (qdir, rdir, fdir):
        d.mkdir(parents=True, exist_ok=True)

    for path in qdir.glob("*.md"):
        path.unlink()
    for path in rdir.glob("*.md"):
        path.unlink()
    for path in fdir.glob("*.md"):
        path.unlink()

    for q in questions:
        num = f"{q.seq:03d}"
        qpath = qdir / f"{num}_{_slug(q.title)}.md"
        qpath.write_text(_question_md(q), encoding="utf-8")
        if q.evidence or q.verdict:
            (rdir / f"{num}_result.md").write_text(_result_md(q), encoding="utf-8")
        if q.fix_notes:
            (fdir / f"{num}_fix.md").write_text(_fix_md(q), encoding="utf-8")

    state = {
        "total": len(questions),
        "passed": sum(1 for q in questions if q.status == "passed"),
        "failed": sum(1 for q in questions if q.status == "failed"),
        "open": sum(1 for q in questions if q.status in ("open", "checking", "fixing")),
    }
    (base / "state.json").write_text(
        __import__("json").dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _slug(title: str) -> str:
    s = "".join(c if c.isalnum() else "_" for c in title.lower())[:40].strip("_")
    return s or "frage"


def _question_md(q: VerificationQuestion) -> str:
    return f"""# Aufgabe {q.seq:03d} — {q.title}

## Prüffrage
{q.question}

## Erwartung
{q.expectation or "—"}

## Prüfmethode
{q.check_method}

## Erfolgskriterien
{q.success_criteria or "—"}

## Status
{q.status}
"""


def _result_md(q: VerificationQuestion) -> str:
    return f"""# Bewertung Aufgabe {q.seq:03d}

## Ergebnis
{q.verdict or "—"}

## Status
{q.status}

## Nachweis (Prüf-Agent)
{q.evidence or "—"}

## Bewertung (Kontrolle)
{q.review_notes or "—"}
"""


def _fix_md(q: VerificationQuestion) -> str:
    return f"""# Fix Aufgabe {q.seq:03d}

{q.fix_notes}
"""
