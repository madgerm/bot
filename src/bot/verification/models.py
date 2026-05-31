"""Datenmodell für Prüffragen-Teams."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

CheckMethod = Literal["browser", "code", "db", "api", "mixed"]
QuestionStatus = Literal[
    "open",
    "checking",
    "reviewing",
    "fixing",
    "passed",
    "failed",
    "skipped",
]
Verdict = Literal["ja", "nein", "teilweise", "unklar"]
TeamWorkflow = Literal["tasks", "verification"]


@dataclass
class VerificationQuestion:
    id: str
    team_id: str
    seq: int
    title: str
    question: str
    expectation: str
    check_method: CheckMethod
    success_criteria: str
    status: QuestionStatus
    verdict: Verdict | None
    evidence: str
    review_notes: str
    fix_notes: str
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "team_id": self.team_id,
            "seq": self.seq,
            "title": self.title,
            "question": self.question,
            "expectation": self.expectation,
            "check_method": self.check_method,
            "success_criteria": self.success_criteria,
            "status": self.status,
            "verdict": self.verdict,
            "evidence": self.evidence,
            "review_notes": self.review_notes,
            "fix_notes": self.fix_notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
