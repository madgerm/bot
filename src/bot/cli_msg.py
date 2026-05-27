"""CLI-Befehle für Nachrichten (MVP Schritt 2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bot.messages import MessageError, MessageService, open_message_service


def _print_message(message) -> None:
    print(json.dumps(message.model_dump(mode="json"), indent=2, ensure_ascii=False))


def cmd_msg_send(args: argparse.Namespace) -> int:
    try:
        service = open_message_service(args.root)
        message = service.send(
            team_id=args.team,
            from_agent=args.sender,
            to_agent=args.to,
            subject=args.subject,
            content=args.content,
            type=args.type,
            task_category=args.task_category,
        )
    except MessageError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    print(f"Gesendet: {message.id} → {args.team}/{args.to}")
    return 0


def cmd_msg_list(args: argparse.Namespace) -> int:
    try:
        service = open_message_service(args.root)
        messages = service.list_inbox(args.team, args.agent, status=args.status)
    except MessageError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    if not messages:
        print("(keine Messages)")
        return 0

    for message in messages:
        _print_message(message)
        print("---")
    return 0


def cmd_msg_claim(args: argparse.Namespace) -> int:
    try:
        service = open_message_service(args.root)
        message = service.claim(args.team, args.agent)
    except MessageError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    if message is None:
        print("(keine pending Messages)")
        return 0

    _print_message(message)
    return 0


def cmd_msg_done(args: argparse.Namespace) -> int:
    try:
        service = open_message_service(args.root)
        message = service.complete(args.team, args.agent, args.id)
    except MessageError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    _print_message(message)
    return 0


def cmd_msg_fail(args: argparse.Namespace) -> int:
    try:
        service = open_message_service(args.root)
        message = service.fail(args.team, args.agent, args.id, args.error)
    except MessageError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    _print_message(message)
    return 0


def cmd_msg_retry(args: argparse.Namespace) -> int:
    try:
        service = open_message_service(args.root)
        message = service.retry(args.team, args.agent, args.id)
    except MessageError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    _print_message(message)
    return 0


def register_msg_commands(
    sub: argparse._SubParsersAction,
    add_root,
) -> None:
    msg_parser = sub.add_parser("msg", help="Nachrichten (Inbox/Outbox)")
    msg_sub = msg_parser.add_subparsers(dest="msg_command", required=True)

    send = msg_sub.add_parser("send", help="Nachricht an Agent senden")
    add_root(send)
    send.add_argument("--team", required=True)
    send.add_argument("--from", dest="sender", required=True)
    send.add_argument("--to", required=True)
    send.add_argument("--subject", required=True)
    send.add_argument("--content", required=True)
    send.add_argument("--type", default="task")
    send.add_argument("--task-category", default=None)
    send.set_defaults(func=cmd_msg_send)

    list_cmd = msg_sub.add_parser("list", help="Inbox eines Agents auflisten")
    add_root(list_cmd)
    list_cmd.add_argument("--team", required=True)
    list_cmd.add_argument("--agent", required=True)
    list_cmd.add_argument(
        "--status",
        choices=["pending", "processing", "done", "failed"],
        default=None,
    )
    list_cmd.set_defaults(func=cmd_msg_list)

    claim = msg_sub.add_parser("claim", help="Nächste pending-Message übernehmen")
    add_root(claim)
    claim.add_argument("--team", required=True)
    claim.add_argument("--agent", required=True)
    claim.set_defaults(func=cmd_msg_claim)

    done = msg_sub.add_parser("done", help="Message als erledigt markieren")
    add_root(done)
    done.add_argument("--team", required=True)
    done.add_argument("--agent", required=True)
    done.add_argument("--id", required=True)
    done.set_defaults(func=cmd_msg_done)

    fail = msg_sub.add_parser("fail", help="Message als fehlgeschlagen markieren")
    add_root(fail)
    fail.add_argument("--team", required=True)
    fail.add_argument("--agent", required=True)
    fail.add_argument("--id", required=True)
    fail.add_argument("--error", default="manuell als failed markiert")
    fail.set_defaults(func=cmd_msg_fail)

    retry = msg_sub.add_parser("retry", help="Fehlgeschlagene Message erneut einreihen")
    add_root(retry)
    retry.add_argument("--team", required=True)
    retry.add_argument("--agent", required=True)
    retry.add_argument("--id", required=True)
    retry.set_defaults(func=cmd_msg_retry)
