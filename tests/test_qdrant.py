import json
from pathlib import Path

import pytest

from bot.qdrant.collections import collection_name
from bot.qdrant.embeddings import hash_embedding
from bot.qdrant.service import QdrantService


def test_hash_embedding_normalized() -> None:
    a = hash_embedding("test", vector_size=32)
    assert len(a) == 32
    norm = sum(x * x for x in a) ** 0.5
    assert abs(norm - 1.0) < 0.01


def test_collection_names() -> None:
    assert collection_name("demo", "project") == "team_demo__project"


@pytest.fixture
def qdrant_project(runtime_project: Path) -> Path:
    system_path = runtime_project / "config" / "system.json"
    data = json.loads(system_path.read_text(encoding="utf-8"))
    data["qdrant_global"] = {
        "enabled": True,
        "url": ":memory:",
        "embedding": {"provider": "hash", "vector_size": 64},
    }
    system_path.write_text(json.dumps(data), encoding="utf-8")
    return runtime_project


def test_qdrant_upsert_search(qdrant_project: Path) -> None:
    service = QdrantService.from_root(qdrant_project)
    service.ensure_team_collections("alpha")
    service.upsert(
        "alpha",
        "project",
        text="Python Agent System mit FastAPI",
        payload={"topic": "docs"},
    )
    service.upsert("alpha", "project", text="Unrelated cooking recipes")
    results = service.search("alpha", "project", "Agent FastAPI", limit=3)
    assert results
    assert "Agent" in results[0]["payload"].get("text", "") or results[0]["score"] > 0
