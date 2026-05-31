"""Backup create/restore."""

from pathlib import Path

from bot.backup import create_backup, restore_backup
from bot.chat.store import ChatStore


def test_backup_create_and_restore(runtime_project: Path, tmp_path: Path) -> None:
    team = "alpha"
    (runtime_project / "data" / team).mkdir(parents=True, exist_ok=True)
    store = ChatStore(runtime_project, team)
    store.add(role="user", content="Backup-Test", agent_id="orchestrator")

    archive = create_backup(runtime_project, team_ids=[team], output=tmp_path / "t.tar.gz")
    assert archive.is_file()

    store.clear_all(actor="test")
    assert not store.list_messages(limit=5)

    restored = restore_backup(runtime_project, archive, team_ids=[team])
    assert any("chat.sqlite" in p for p in restored)

    store2 = ChatStore(runtime_project, team)
    msgs = store2.list_messages(limit=5)
    assert any("Backup-Test" in (m.content or "") for m in msgs)


def test_backup_dry_run(runtime_project: Path, tmp_path: Path) -> None:
    (runtime_project / "data" / "alpha").mkdir(parents=True, exist_ok=True)
    archive = create_backup(runtime_project, team_ids=["alpha"], output=tmp_path / "dry.tar.gz")
    paths = restore_backup(runtime_project, archive, dry_run=True)
    assert paths
