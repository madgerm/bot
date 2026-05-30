"""Zentrales Audit-Log."""

from pathlib import Path

from bot.audit import AuditStore


def test_audit_log_roundtrip(runtime_project: Path) -> None:
    store = AuditStore(runtime_project)
    store.log(
        category="mail",
        action="approve",
        actor="admin",
        team_id="alpha",
        details={"id": "x"},
    )
    entries = store.list_entries(category="mail", limit=10)
    assert len(entries) == 1
    assert entries[0].actor == "admin"
    assert entries[0].details["id"] == "x"
