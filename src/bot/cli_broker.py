"""CLI: Redis-Broker."""

from __future__ import annotations

import argparse
import sys


def register_broker_commands(sub, add_root) -> None:
    p = sub.add_parser("broker", help="Message-Broker (Redis)")
    add_root(p)
    broker_sub = p.add_subparsers(dest="broker_command", required=True)

    drain = broker_sub.add_parser("drain", help="Broker → lokale Inbox")
    add_root(drain)
    drain.add_argument("--team", required=True)
    drain.add_argument("--agent", required=True)
    drain.add_argument("--limit", type=int, default=50)
    drain.set_defaults(func=_cmd_drain)


def _cmd_drain(args: argparse.Namespace) -> int:
    from bot.config import load_runtime_config
    from bot.messages.broker import BrokerError, MessageBroker

    broker = MessageBroker.from_root(args.root)
    if broker is None:
        print("Broker-Modus nicht aktiv", file=sys.stderr)
        return 1
    cfg = load_runtime_config(args.root)
    inbox_base = cfg.system.system.communication.inbox_base
    try:
        n = broker.drain_to_mailbox(
            args.root, args.team, args.agent, inbox_base, args.limit
        )
    except BrokerError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{n} Nachricht(en) übernommen")
    return 0
