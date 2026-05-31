"""Config-Writer (atomisches JSON)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from bot.config.writers import (
    ConfigWriterError,
    atomic_write_json,
    load_json_file,
    load_json_model,
    merge_json_at_key,
)


class _SampleModel(BaseModel):
    name: str
    count: int = 0


def test_atomic_write_json_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "cfg.json"
    atomic_write_json(path, {"hello": "world", "n": 1})
    assert path.is_file()
    assert load_json_file(path) == {"hello": "world", "n": 1}


def test_load_json_model_with_key(tmp_path: Path) -> None:
    path = tmp_path / "wrap.json"
    path.write_text(json.dumps({"block": {"name": "demo", "count": 3}}), encoding="utf-8")
    model = load_json_model(path, _SampleModel, key="block")
    assert model.name == "demo"
    assert model.count == 3


def test_load_json_model_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"name": 123}', encoding="utf-8")
    with pytest.raises(ConfigWriterError, match="Validierung"):
        load_json_model(path, _SampleModel)


def test_merge_json_at_key(tmp_path: Path) -> None:
    path = tmp_path / "system.json"
    path.write_text('{"other": true}', encoding="utf-8")
    merge_json_at_key(path, "media_global", {"vision": {}})
    data = load_json_file(path)
    assert data["other"] is True
    assert data["media_global"] == {"vision": {}}


def test_merge_json_at_key_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    with pytest.raises(ConfigWriterError, match="fehlt"):
        merge_json_at_key(path, "x", {})
