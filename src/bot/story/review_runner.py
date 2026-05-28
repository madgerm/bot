"""Parallele Story-Prüfer (LLM + optional file-basierte Agent-Inboxen)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bot.config import load_runtime_config
from bot.llm.factory import build_llm_stack
from bot.story.config import StoryCheckerConfig, load_story_review_config
from bot.story.db import StoryDB


class StoryReviewError(Exception):
    pass


@dataclass
class CheckerResult:
    checker_id: str
    name: str
    status: str
    raw: str
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "checker_id": self.checker_id,
            "name": self.name,
            "status": self.status,
            "raw": self.raw,
            "issues": self.issues,
        }


def _parse_issues(text: str) -> tuple[str, list[str]]:
    upper = text.strip().upper()
    if upper.startswith("OK") or "APPROVED" in upper[:20]:
        return "ok", []
    lines = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().upper().startswith("OK")
    ]
    if not lines and len(text) > 10:
        return "issues", [text.strip()[:500]]
    return "issues", lines[:10]


class StoryReviewRunner:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.db = StoryDB(root, team_id)
        self.cfg = load_story_review_config(root, team_id)
        self._runtime = load_runtime_config(root)
        self._llm = build_llm_stack(self._runtime)

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> StoryReviewRunner:
        return cls(Path(root), team_id)

    def _build_context(self, chapter_id: str, scene_id: str) -> str:
        meta, body = self.db.get_scene(chapter_id, scene_id)
        chars = self.db.list_characters()
        world_rules = self.db.read_world_file("regeln.md")[:2000]
        plot = self.db.get_plot()
        return (
            f"## Szene {chapter_id}/{scene_id}: {meta.get('title', '')}\n\n{body}\n\n"
            f"## Charaktere\n{json_dump_chars(chars)}\n\n"
            f"## World-Regeln\n{world_rules}\n\n"
            f"## Plot-Outline\n{json_dump_plot(plot)}"
        )

    def _run_checker(
        self, checker: StoryCheckerConfig, context: str
    ) -> CheckerResult:
        category = checker.task_category
        model = self._llm.router.resolve(category, role="reviewer")
        fallbacks = self._llm.router.fallbacks(category, role="reviewer")
        messages = [
            {"role": "system", "content": checker.prompt},
            {"role": "user", "content": context},
        ]
        raw = self._llm.client.complete(model, messages, fallbacks=fallbacks or None)
        status, issues = _parse_issues(raw)
        return CheckerResult(
            checker_id=checker.id,
            name=checker.name,
            status=status,
            raw=raw,
            issues=issues,
        )

    def review_scene_parallel(
        self,
        chapter_id: str,
        scene_id: str,
        *,
        dispatch_inbox: bool | None = None,
    ) -> list[CheckerResult]:
        context = self._build_context(chapter_id, scene_id)
        checkers = [c for c in self.cfg.checkers if c.enabled]
        if not checkers:
            raise StoryReviewError("Keine Prüfer konfiguriert")

        results: list[CheckerResult] = []
        with ThreadPoolExecutor(max_workers=self.cfg.max_parallel) as pool:
            futures = {
                pool.submit(self._run_checker, c, context): c for c in checkers
            }
            for fut in as_completed(futures):
                checker = futures[fut]
                try:
                    result = fut.result()
                except Exception as exc:
                    result = CheckerResult(
                        checker_id=checker.id,
                        name=checker.name,
                        status="error",
                        raw=str(exc),
                        issues=[str(exc)],
                    )
                results.append(result)
                for issue in result.issues:
                    self.db.add_review_issue(
                        checker=checker.id,
                        severity="error" if result.status == "error" else "warning",
                        message=issue,
                        chapter_id=chapter_id,
                        scene_id=scene_id,
                    )

        if dispatch_inbox if dispatch_inbox is not None else self.cfg.dispatch_to_agent_inbox:
            self._dispatch_to_agents(chapter_id, scene_id, context, checkers)

        return sorted(results, key=lambda r: r.checker_id)

    def _dispatch_to_agents(
        self,
        chapter_id: str,
        scene_id: str,
        context: str,
        checkers: list[StoryCheckerConfig],
    ) -> None:
        from bot.messages import MessageService, MessageError

        bundle = self._runtime.teams.get(self.team_id)
        if not bundle:
            return
        orch_id = bundle.team.team.orchestrator_id
        svc = MessageService(self.root)
        subject = f"Review {chapter_id}/{scene_id}"
        for checker in checkers:
            if checker.agent_id not in bundle.agents:
                continue
            try:
                svc.send(
                    team_id=self.team_id,
                    from_agent=orch_id,
                    to_agent=checker.agent_id,
                    subject=subject,
                    content=context[:4000],
                    type="review_task",
                    task_category=checker.task_category,
                )
            except MessageError:
                pass


def json_dump_chars(chars: list[dict]) -> str:
    import json

    return json.dumps(chars, ensure_ascii=False, indent=2)[:4000]


def json_dump_plot(plot: dict) -> str:
    import json

    return json.dumps(plot, ensure_ascii=False, indent=2)[:2000]
