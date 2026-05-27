from pathlib import Path

from bot.chat import ChatStore


def test_chat_store_add_list_clear(runtime_project: Path) -> None:
    store = ChatStore(runtime_project, "alpha")
    store.add(role="user", content="Hallo Team", agent_id="orchestrator")
    store.add(role="assistant", content="Hallo zurück", agent_id="orchestrator")

    messages = store.list_messages()
    assert len(messages) == 2
    assert messages[0].content == "Hallo Team"

    assert store.delete_message(messages[0].id)
    assert len(store.list_messages()) == 1

    count = store.clear_all()
    assert count == 1
    assert not store.list_messages()
