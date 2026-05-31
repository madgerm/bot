"""CLI: E-Mail (`bot mail`)."""

from __future__ import annotations

import argparse
import json
import sys


def cmd_mail_test(args: argparse.Namespace) -> int:
    from bot.mail import MailService, MailServiceError

    try:
        service = MailService.for_team(args.root, args.team)
        results = service.test_connections()
    except MailServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    for key, value in results.items():
        print(f"{key}: {value}")
    return 0 if all(v == "ok" for v in results.values()) else 1


def cmd_mail_poll(args: argparse.Namespace) -> int:
    from bot.mail import MailService, MailServiceError

    try:
        from bot.mail.notify import notify_new_mail_threads

        service = MailService.for_team(args.root, args.team)
        threads = service.poll(limit=args.limit)
        notify_new_mail_threads(args.root, args.team, threads)
    except MailServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(f"Neu: {len(threads)} Thread(s)")
    for thread in threads:
        print(json.dumps(thread.to_dict(), ensure_ascii=False))
    return 0


def cmd_mail_list(args: argparse.Namespace) -> int:
    from bot.mail.store import MailStore

    store = MailStore(args.root, args.team)
    if args.drafts:
        items = store.list_drafts(status=args.status, limit=args.limit)
        for item in items:
            print(json.dumps(item.to_dict(), ensure_ascii=False))
            print("---")
        return 0
    threads = store.list_threads(limit=args.limit)
    for thread in threads:
        print(json.dumps(thread.to_dict(), ensure_ascii=False))
        print("---")
    return 0


def cmd_mail_show(args: argparse.Namespace) -> int:
    from bot.mail.store import MailStore

    store = MailStore(args.root, args.team)
    thread = store.get_thread(args.thread)
    if not thread:
        print("Thread nicht gefunden", file=sys.stderr)
        return 1
    incoming = store.get_incoming(args.thread)
    drafts = store.list_drafts(thread_id=args.thread)
    print(json.dumps(thread.to_dict(), indent=2, ensure_ascii=False))
    if incoming:
        print("\nEingang:")
        print(json.dumps(incoming.to_dict(), indent=2, ensure_ascii=False))
    for draft in drafts:
        print("\nEntwurf:")
        print(json.dumps(draft.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_mail_draft(args: argparse.Namespace) -> int:
    from bot.mail import MailService, MailServiceError

    to_addrs = [a.strip() for a in args.to.split(",") if a.strip()] if args.to else None
    try:
        service = MailService.for_team(args.root, args.team)
        draft = service.create_reply_draft(
            args.thread,
            body_text=args.body,
            to_addrs=to_addrs,
            subject=args.subject,
            created_by=args.created_by,
        )
    except MailServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(draft.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_mail_approve(args: argparse.Namespace) -> int:
    from bot.mail import MailService, MailServiceError

    try:
        service = MailService.for_team(args.root, args.team)
        draft = service.approve(args.draft, args.approved_by)
    except MailServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(draft.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_mail_send(args: argparse.Namespace) -> int:
    from bot.mail import MailService, MailServiceError

    try:
        service = MailService.for_team(args.root, args.team)
        draft = service.send_approved(args.draft)
    except MailServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(draft.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_mail_reject(args: argparse.Namespace) -> int:
    from bot.mail import MailService, MailServiceError

    try:
        service = MailService.for_team(args.root, args.team)
        draft = service.reject(args.draft)
    except MailServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(draft.to_dict(), indent=2, ensure_ascii=False))
    return 0


def register_mail_commands(sub, add_root) -> None:
    mail = sub.add_parser("mail", help="E-Mail (IMAP/SMTP, Freigabe)")
    mail_sub = mail.add_subparsers(dest="mail_command", required=True)

    test = mail_sub.add_parser("test", help="IMAP/SMTP-Verbindung testen")
    add_root(test)
    test.add_argument("--team", required=True)
    test.set_defaults(func=cmd_mail_test)

    poll = mail_sub.add_parser("poll", help="Ungelesene Mails abholen")
    add_root(poll)
    poll.add_argument("--team", required=True)
    poll.add_argument("--limit", type=int, default=20)
    poll.set_defaults(func=cmd_mail_poll)

    list_cmd = mail_sub.add_parser("list", help="Threads oder Entwürfe")
    add_root(list_cmd)
    list_cmd.add_argument("--team", required=True)
    list_cmd.add_argument("--drafts", action="store_true")
    list_cmd.add_argument("--status", default=None)
    list_cmd.add_argument("--limit", type=int, default=50)
    list_cmd.set_defaults(func=cmd_mail_list)

    show = mail_sub.add_parser("show", help="Thread-Details")
    add_root(show)
    show.add_argument("--team", required=True)
    show.add_argument("--thread", required=True)
    show.set_defaults(func=cmd_mail_show)

    draft = mail_sub.add_parser("draft", help="Antwort-Entwurf anlegen")
    add_root(draft)
    draft.add_argument("--team", required=True)
    draft.add_argument("--thread", required=True)
    draft.add_argument("--body", required=True)
    draft.add_argument("--to", default=None, help="Komma-getrennte Empfänger")
    draft.add_argument("--subject", default=None)
    draft.add_argument("--created-by", default=None)
    draft.set_defaults(func=cmd_mail_draft)

    approve = mail_sub.add_parser("approve", help="Entwurf freigeben")
    add_root(approve)
    approve.add_argument("--team", required=True)
    approve.add_argument("--draft", required=True)
    approve.add_argument("--approved-by", required=True)
    approve.set_defaults(func=cmd_mail_approve)

    send = mail_sub.add_parser("send", help="Freigegebenen Entwurf senden")
    add_root(send)
    send.add_argument("--team", required=True)
    send.add_argument("--draft", required=True)
    send.set_defaults(func=cmd_mail_send)

    reject = mail_sub.add_parser("reject", help="Entwurf ablehnen")
    add_root(reject)
    reject.add_argument("--team", required=True)
    reject.add_argument("--draft", required=True)
    reject.set_defaults(func=cmd_mail_reject)
