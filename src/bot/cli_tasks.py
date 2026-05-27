"""CLI: Task Board."""

from __future__ import annotations

import argparse
import json
import sys


def register_tasks_commands(sub, add_root) -> None:
    p = sub.add_parser("tasks", help="Task Board (SQLite)")
    add_root(p)
    tasks_sub = p.add_subparsers(dest="tasks_command", required=True)

    create = tasks_sub.add_parser("create", help="Task anlegen")
    add_root(create)
    create.add_argument("--team", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--description", default="")
    create.add_argument("--assignee", default=None)
    create.set_defaults(func=_cmd_create)

    ls = tasks_sub.add_parser("list", help="Tasks auflisten")
    add_root(ls)
    ls.add_argument("--team", required=True)
    ls.add_argument("--status", default=None)
    ls.set_defaults(func=_cmd_list)

    move = tasks_sub.add_parser("move", help="Status ändern")
    add_root(move)
    move.add_argument("--team", required=True)
    move.add_argument("--id", required=True)
    move.add_argument("--status", required=True, choices=["todo", "in_progress", "done"])
    move.set_defaults(func=_cmd_move)


def _cmd_create(args: argparse.Namespace) -> int:
    from bot.tasks import TaskService

    task = TaskService.for_team(args.root, args.team).create(
        title=args.title,
        description=args.description,
        assignee_agent=args.assignee,
    )
    print(json.dumps(task.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    from bot.tasks import TaskService

    tasks = TaskService.for_team(args.root, args.team).store.list_tasks(
        status=args.status  # type: ignore[arg-type]
    )
    print(json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False))
    return 0


def _cmd_move(args: argparse.Namespace) -> int:
    from bot.tasks import TaskService, TaskServiceError

    try:
        task = TaskService.for_team(args.root, args.team).move(
            args.id, args.status  # type: ignore[arg-type]
        )
    except TaskServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(task.to_dict(), indent=2, ensure_ascii=False))
    return 0
