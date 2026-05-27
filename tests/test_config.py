import json
import time
from pathlib import Path

import pytest

from bot.config import ConfigLoadError, ConfigStore, ConfigWatcher, load_runtime_config


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "system.json").write_text(
        json.dumps(
            {
                "system": {
                    "name": "test-runtime",
                    "host": "127.0.0.1",
                    "polling": {"interval_seconds": 2},
                }
            }
        ),
        encoding="utf-8",
    )

    team_dir = tmp_path / "teams" / "alpha"
    team_dir.mkdir(parents=True)
    agents = team_dir / "agents"
    (team_dir / "team.json").write_text(
        json.dumps(
            {
                "team": {
                    "id": "alpha",
                    "name": "Alpha",
                    "orchestrator_id": "orchestrator",
                }
            }
        ),
        encoding="utf-8",
    )
    orch = agents / "orchestrator"
    orch.mkdir(parents=True)
    (orch / "agent.json").write_text(
        json.dumps({"agent": {"id": "orchestrator", "role": "orchestrator"}}),
        encoding="utf-8",
    )
    worker = agents / "worker-a"
    worker.mkdir()
    (worker / "agent.json").write_text(
        json.dumps({"agent": {"id": "worker-a", "role": "worker"}}),
        encoding="utf-8",
    )
    return tmp_path


def test_load_runtime_config(project_root: Path) -> None:
    config = load_runtime_config(project_root)
    assert config.system.system.name == "test-runtime"
    assert "alpha" in config.teams
    assert len(config.teams["alpha"].agents) == 2


def test_missing_orchestrator_raises(project_root: Path) -> None:
    team_path = project_root / "teams" / "alpha" / "team.json"
    data = json.loads(team_path.read_text(encoding="utf-8"))
    data["team"]["orchestrator_id"] = "missing"
    team_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ConfigLoadError, match="Orchestrator"):
        load_runtime_config(project_root)


def test_team_folder_mismatch_raises(project_root: Path) -> None:
    team_path = project_root / "teams" / "alpha" / "team.json"
    data = json.loads(team_path.read_text(encoding="utf-8"))
    data["team"]["id"] = "beta"
    team_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ConfigLoadError, match="passt nicht"):
        load_runtime_config(project_root)


def test_config_store_reload_callback(project_root: Path) -> None:
    store = ConfigStore(project_root)
    seen: list[str] = []
    store.on_reload(lambda cfg: seen.append(cfg.system.system.name))

    store.reload()
    assert seen == ["test-runtime"]

    system_path = project_root / "config" / "system.json"
    data = json.loads(system_path.read_text(encoding="utf-8"))
    data["system"]["name"] = "renamed"
    system_path.write_text(json.dumps(data), encoding="utf-8")
    store.reload()
    assert store.get().system.system.name == "renamed"
    assert seen[-1] == "renamed"


def test_config_watcher_detects_change(project_root: Path) -> None:
    events: list[int] = []

    watcher = ConfigWatcher(project_root, interval_seconds=0.2, on_change=lambda: events.append(1))
    watcher.start()
    try:
        time.sleep(0.35)
        system_path = project_root / "config" / "system.json"
        data = json.loads(system_path.read_text(encoding="utf-8"))
        data["system"]["polling"]["interval_seconds"] = 3
        system_path.write_text(json.dumps(data), encoding="utf-8")

        deadline = time.time() + 2.0
        while time.time() < deadline and not events:
            time.sleep(0.1)
        assert events
    finally:
        watcher.stop()
