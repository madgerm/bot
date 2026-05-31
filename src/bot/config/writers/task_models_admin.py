"""Lesen/Schreiben von config/task_models.json (Panel)."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from bot.config.models import TaskModelEntry, TaskModelsConfig
from bot.config.writers import (
    ConfigWriterError,
    atomic_write_json,
    load_json_file,
    relative_config_path,
)
from bot.config.writers.audit import log_config_change


class TaskModelsAdminError(ConfigWriterError):
    pass


def task_models_path(root: Path) -> Path:
    return root / "config" / "task_models.json"


def load_task_models_admin(root: Path) -> TaskModelsConfig:
    path = task_models_path(root)
    if not path.is_file():
        return TaskModelsConfig(
            task_models={
                "planning": TaskModelEntry(default="ollama/llama3.2"),
                "coding": TaskModelEntry(default="ollama/llama3.2"),
                "review": TaskModelEntry(default="ollama/llama3.2"),
            }
        )
    try:
        return TaskModelsConfig.model_validate(load_json_file(path))
    except ValidationError as exc:
        raise TaskModelsAdminError(str(exc)) from exc


def save_task_models_admin(
    root: Path,
    models: dict[str, TaskModelEntry],
    *,
    actor: str,
) -> None:
    try:
        cfg = TaskModelsConfig(task_models=models)
    except ValidationError as exc:
        raise TaskModelsAdminError(str(exc)) from exc
    atomic_write_json(
        task_models_path(root),
        cfg.model_dump(mode="json"),
    )
    log_config_change(
        root,
        actor=actor,
        config_path=relative_config_path(root, task_models_path(root)),
        action="task_models_update",
        details={"categories": sorted(models.keys())},
    )


def parse_models_from_form(form: dict[str, str]) -> dict[str, TaskModelEntry]:
    """Form keys: model_<category>, alt_<category>, optional new_category + new_default."""
    models: dict[str, TaskModelEntry] = {}
    for key, value in form.items():
        if key.startswith("model_") and value.strip():
            cat = key[6:]
            alt_key = f"alt_{cat}"
            alts_raw = form.get(alt_key, "")
            alts = [a.strip() for a in alts_raw.split(",") if a.strip()]
            models[cat] = TaskModelEntry(default=value.strip(), alternatives=alts)
    new_cat = form.get("new_category", "").strip()
    new_def = form.get("new_default", "").strip()
    if new_cat and new_def:
        models[new_cat] = TaskModelEntry(default=new_def, alternatives=[])
    if not models:
        raise TaskModelsAdminError("Mindestens eine Task-Kategorie mit Modell erforderlich.")
    return models
