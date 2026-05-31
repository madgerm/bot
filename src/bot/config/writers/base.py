"""Gemeinsame Hilfen für Panel-gesteuerte JSON-Konfiguration."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class ConfigWriterError(Exception):
    """Konfiguration konnte nicht gelesen oder geschrieben werden."""


def relative_config_path(root: Path, path: Path) -> str:
    """Pfad relativ zum Projekt-root (für Audit-Logs)."""
    try:
        return str(path.resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigWriterError(f"Datei fehlt: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigWriterError(f"Ungültiges JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigWriterError(f"JSON-Root muss ein Objekt sein: {path}")
    return data


def load_json_model(path: Path, model: type[T], *, key: str | None = None) -> T:
    """Lädt eine Datei und validiert mit Pydantic (optional nur ein Top-Level-Key)."""
    data = load_json_file(path)
    block: Any = data[key] if key is not None else data
    try:
        return model.model_validate(block)
    except ValidationError as exc:
        label = f"{path} → {key}" if key else str(path)
        raise ConfigWriterError(f"Validierung fehlgeschlagen ({label}): {exc}") from exc


def atomic_write_json(path: Path, data: dict[str, Any], *, indent: int = 2) -> None:
    """Schreibt JSON atomisch (temp + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=indent, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def merge_json_at_key(
    path: Path,
    key: str,
    value: dict[str, Any],
    *,
    create_if_missing: bool = False,
) -> dict[str, Any]:
    """Ersetzt einen Top-Level-Key und speichert die Datei atomisch."""
    if path.is_file():
        data = load_json_file(path)
    elif create_if_missing:
        data = {}
    else:
        raise ConfigWriterError(f"Datei fehlt: {path}")
    data[key] = value
    atomic_write_json(path, data)
    return data
