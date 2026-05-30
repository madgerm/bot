from bot.chat.store import ChatStore


def test_chat_audit_on_clear(runtime_project) -> None:
    store = ChatStore(runtime_project, "alpha")
    store.add(role="user", content="Hallo")
    store.clear_all(actor="tester")
    audit = store.list_audit()
    assert len(audit) == 1
    assert audit[0].action == "clear_all"
    assert audit[0].actor == "tester"


def test_chat_audit_on_delete(runtime_project) -> None:
    store = ChatStore(runtime_project, "alpha")
    msg = store.add(role="user", content="X")
    store.delete_message(msg.id, actor="alice")
    audit = store.list_audit()
    assert any(e.action == "delete_message" for e in audit)
