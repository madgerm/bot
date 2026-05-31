"""Team-Pipeline: welche Agent-IDs für Ausführung/Review/Doku genutzt werden."""

from __future__ import annotations

from dataclasses import dataclass

from bot.config.models import PipelineConfig, TeamBundle


@dataclass(frozen=True)
class ResolvedPipeline:
    orchestrator_id: str
    execute_id: str
    review_id: str
    document_id: str | None = None


def resolve_pipeline(bundle: TeamBundle) -> ResolvedPipeline:
    team = bundle.team.team
    pipe: PipelineConfig | None = bundle.team.pipeline
    preset = (team.preset or "generic").lower()
    orch = team.orchestrator_id

    defaults: dict[str, tuple[str, str, str | None]] = {
        "demo": ("worker-exec", "worker-review", None),
        "generic": ("worker-exec", "worker-review", None),
        "coding": ("coder", "tester", "doku"),
        "story": ("drehbuch-autor", "logik-pruefer", "literatur-review"),
    }
    d_exec, d_review, d_doc = defaults.get(preset, defaults["generic"])

    execute = (pipe.execute if pipe and pipe.execute else d_exec)
    review = (pipe.review if pipe and pipe.review else d_review)
    document = pipe.document if pipe and pipe.document else d_doc

    for agent_id in (execute, review):
        if agent_id not in bundle.agents:
            raise ValueError(
                f"Pipeline-Agent '{agent_id}' fehlt in Team '{team.id}'"
            )
    if document and document not in bundle.agents:
        raise ValueError(
            f"Pipeline-Agent '{document}' fehlt in Team '{team.id}'"
        )

    return ResolvedPipeline(
        orchestrator_id=orch,
        execute_id=execute,
        review_id=review,
        document_id=document,
    )


def pipeline_for_team_id(root, team_id: str) -> ResolvedPipeline:
    from pathlib import Path

    from bot.config.loader import discover_teams

    teams = discover_teams(Path(root) / "teams")
    bundle = teams.get(team_id)
    if not bundle:
        raise ValueError(f"Team '{team_id}' nicht gefunden")
    return resolve_pipeline(bundle)
