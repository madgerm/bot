"""CLI: Team-Chat (`bot chat`)."""

from __future__ import annotations

import argparse
import json
import sys


def cmd_chat_send(args: argparse.Namespace) -> int:
    from bot.chat import ChatStore, ChatStoreError

    try:
        store = ChatStore(args.root, args.team)
        msg = store.add(
            role=args.role,
            content=args.content,
            agent_id=args.agent,
            thread_id=args.thread,
        )
    except ChatStoreError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(msg.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_chat_list(args: argparse.Namespace) -> int:
    from bot.chat import ChatStore

    store = ChatStore(args.root, args.team)
    messages = store.list_messages(
        agent_id=args.agent,
        thread_id=args.thread,
        search=args.search,
        limit=args.limit,
    )
    if not messages:
        print("(keine Nachrichten)")
        return 0
    for msg in messages:
        print(json.dumps(msg.to_dict(), ensure_ascii=False))
        print("---")
    return 0


def cmd_chat_clear(args: argparse.Namespace) -> int:
    from bot.chat import ChatStore

    if not args.yes:
        print("Abbruch — nutze --yes zum Bestätigen", file=sys.stderr)
        return 1
    store = ChatStore(args.root, args.team)
    count = store.clear_all()
    print(f"Gelöscht: {count} Nachricht(en)")
    return 0


def register_chat_commands(sub, add_root) -> None:
    chat = sub.add_parser("chat", help="Team-Chat (SQLite)")
    chat_sub = chat.add_subparsers(dest="chat_command", required=True)

    send = chat_sub.add_parser("send", help="Chat-Nachricht speichern")
    add_root(send)
    send.add_argument("--team", required=True)
    send.add_argument("--role", choices=["user", "assistant", "system", "tool"], default="user")
    send.add_argument("--content", required=True)
    send.add_argument("--agent", default=None)
    send.add_argument("--thread", default=None)
    send.set_defaults(func=cmd_chat_send)

    list_cmd = chat_sub.add_parser("list", help="Verlauf anzeigen")
    add_root(list_cmd)
    list_cmd.add_argument("--team", required=True)
    list_cmd.add_argument("--agent", default=None)
    list_cmd.add_argument("--thread", default=None)
    list_cmd.add_argument("--search", default=None)
    list_cmd.add_argument("--limit", type=int, default=50)
    list_cmd.set_defaults(func=cmd_chat_list)

    clear = chat_sub.add_parser("clear", help="Gesamten Verlauf leeren")
    add_root(clear)
    clear.add_argument("--team", required=True)
    clear.add_argument("--yes", action="store_true")
    clear.set_defaults(func=cmd_chat_clear)
