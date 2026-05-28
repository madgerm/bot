"""CLI: Öffnungszeiten (`bot hours`)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _llm_stack_for_root(root: Path):
    from bot.config import ConfigStore
    from bot.llm import build_llm_stack

    return build_llm_stack(ConfigStore(root).get())


def cmd_hours_show(args: argparse.Namespace) -> int:
    from bot.hours import HoursService, HoursServiceError

    try:
        service = HoursService.for_team(args.root, args.team)
        master = service.get_master()
    except HoursServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(master.normalized(), indent=2, ensure_ascii=False))
    return 0


def cmd_hours_check(args: argparse.Namespace) -> int:
    from bot.hours import HoursService, HoursServiceError

    try:
        service = HoursService.for_team(args.root, args.team)
        record = service.check(llm_stack=_llm_stack_for_root(args.root))
    except HoursServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(record.to_dict(), indent=2, ensure_ascii=False))
    print("---", file=sys.stderr)
    print(service.format_check_summary(record), file=sys.stderr)
    return 0


def cmd_hours_queue(args: argparse.Namespace) -> int:
    from bot.config import ConfigLoadError, ConfigStore
    from bot.hours.config import HoursConfigError, load_hours_config
    from bot.messages import MessageService

    try:
        cfg = load_hours_config(args.root, args.team)
        agent_id = args.agent or cfg.checker_agent_id
        bundle = ConfigStore(args.root).get().teams.get(args.team)
        if not bundle or agent_id not in bundle.agents:
            print(f"Agent '{agent_id}' fehlt im Team.", file=sys.stderr)
            return 1
    except (HoursConfigError, ConfigLoadError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    msg = MessageService(args.root).send(
        team_id=args.team,
        from_agent=bundle.team.team.orchestrator_id,
        to_agent=agent_id,
        subject=args.subject or "Öffnungszeiten prüfen",
        content=args.content or "Lies die Website und prüfe die Öffnungszeiten.",
        type="hours_check",
        task_category="review",
    )
    print(json.dumps(msg.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


def cmd_hours_list(args: argparse.Namespace) -> int:
    from bot.hours.store import HoursStore

    for record in HoursStore(args.root, args.team).list_diffs(limit=args.limit):
        print(json.dumps(record.to_dict(), ensure_ascii=False))
        print("---")
    return 0


def cmd_hours_approve(args: argparse.Namespace) -> int:
    from bot.hours import HoursService, HoursServiceError

    try:
        record = HoursService.for_team(args.root, args.team).approve(
            args.diff, args.approved_by
        )
    except HoursServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(record.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_hours_publish(args: argparse.Namespace) -> int:
    from bot.hours import HoursService, HoursServiceError

    try:
        record = HoursService.for_team(args.root, args.team).publish(args.diff)
    except HoursServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(record.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_hours_reject(args: argparse.Namespace) -> int:
    from bot.hours import HoursService, HoursServiceError

    try:
        record = HoursService.for_team(args.root, args.team).reject(args.diff)
    except HoursServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(record.to_dict(), indent=2, ensure_ascii=False))
    return 0


def register_hours_commands(sub, add_root) -> None:
    hours = sub.add_parser("hours", help="Öffnungszeiten (Agent liest Website)")
    hours_sub = hours.add_subparsers(dest="hours_command", required=True)

    show = hours_sub.add_parser("show", help="Master anzeigen")
    add_root(show)
    show.add_argument("--team", required=True)
    show.set_defaults(func=cmd_hours_show)

    check = hours_sub.add_parser("check", help="Agent liest Seite und gleicht ab")
    add_root(check)
    check.add_argument("--team", required=True)
    check.set_defaults(func=cmd_hours_check)

    queue = hours_sub.add_parser("queue", help="Auftrag an hours_checker")
    add_root(queue)
    queue.add_argument("--team", required=True)
    queue.add_argument("--agent")
    queue.add_argument("--subject", default="Öffnungszeiten prüfen")
    queue.add_argument("--content", default="")
    queue.set_defaults(func=cmd_hours_queue)

    list_cmd = hours_sub.add_parser("list", help="Diff-Verlauf")
    add_root(list_cmd)
    list_cmd.add_argument("--team", required=True)
    list_cmd.add_argument("--limit", type=int, default=20)
    list_cmd.set_defaults(func=cmd_hours_list)

    approve = hours_sub.add_parser("approve", help="Diff freigeben")
    add_root(approve)
    approve.add_argument("--team", required=True)
    approve.add_argument("--diff", required=True)
    approve.add_argument("--approved-by", required=True)
    approve.set_defaults(func=cmd_hours_approve)

    publish = hours_sub.add_parser("publish", help="Veröffentlichen")
    add_root(publish)
    publish.add_argument("--team", required=True)
    publish.add_argument("--diff", required=True)
    publish.set_defaults(func=cmd_hours_publish)

    reject = hours_sub.add_parser("reject", help="Diff ablehnen")
    add_root(reject)
    reject.add_argument("--team", required=True)
    reject.add_argument("--diff", required=True)
    reject.set_defaults(func=cmd_hours_reject)
