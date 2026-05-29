import json
from pathlib import Path

from bot.qdrant.indexer import index_workspace_file, workspace_snapshot


def test_workspace_snapshot_and_file_hook(runtime_project: Path) -> None:
    system_path = runtime_project / "config" / "system.json"
    data = json.loads(system_path.read_text(encoding="utf-8"))
    data["qdrant_global"] = {
        "enabled": True,
        "url": ":memory:",
        "embedding": {"provider": "hash", "vector_size": 64},
        "reindex": {"enabled": True, "interval_seconds": 0},
    }
    system_path.write_text(json.dumps(data), encoding="utf-8")

    from bot.files.service import FileService

    fs = FileService.for_team(runtime_project, "alpha")
    fs.write_file("hook-test.py", "print('hello qdrant')")

    snap1 = workspace_snapshot(runtime_project, "alpha")
    assert "hook-test.py" in snap1

    assert index_workspace_file(runtime_project, "alpha", "hook-test.py")
