"""Panel-Audit-Middleware deckt alle POST-Aktionen ab."""

from pathlib import Path

from fastapi.testclient import TestClient

from bot.audit import AuditStore
from bot.web import create_app


def test_audit_middleware_logs_task_create(web_project: Path) -> None:
    client = TestClient(create_app(web_project))
    client.get("/login")
    client.post("/login", data={"username": "admin", "password": "secret"})

    client.post(
        "/teams/alpha/tasks/create",
        data={"title": "Audit-Test", "description": "x", "status": "todo"},
    )

    entries = AuditStore(web_project).list_entries(category="tasks", limit=20)
    assert any(e.action == "create" and e.team_id == "alpha" for e in entries)


def test_audit_middleware_logs_chat_send(web_project: Path) -> None:
    client = TestClient(create_app(web_project))
    client.get("/login")
    client.post("/login", data={"username": "admin", "password": "secret"})
    client.post(
        "/teams/alpha/chat/send",
        data={"content": "Hallo Audit", "role": "user", "agent_id": "orchestrator"},
    )
    entries = AuditStore(web_project).list_entries(category="chat", limit=10)
    assert any(e.action == "send" for e in entries)
