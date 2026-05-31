"""CLI: LLM testen (`bot llm test`)."""

from __future__ import annotations

import argparse
import sys

from bot.config import ConfigLoadError, load_runtime_config
from bot.llm import LlmError, build_llm_stack


def cmd_llm_test(args: argparse.Namespace) -> int:
    try:
        config = load_runtime_config(args.root)
        stack = build_llm_stack(config)
    except ConfigLoadError as exc:
        print(f"Konfiguration ungültig: {exc}", file=sys.stderr)
        return 1

    llm_cfg = config.system.system.llm
    category = args.task_category
    model = stack.router.resolve(category, role=args.role, override=args.model)
    fallbacks = stack.router.fallbacks(category, role=args.role)

    print(f"LLM enabled: {llm_cfg.enabled}")
    print(f"Modell: {model}")
    if fallbacks:
        print(f"Fallbacks: {', '.join(fallbacks)}")
    print(f"API-Base: {llm_cfg.api_base}")

    messages = [
        {"role": "system", "content": "Antworte sehr kurz (ein Satz)."},
        {"role": "user", "content": args.prompt},
    ]

    try:
        reply = stack.client.complete(model, messages, fallbacks=fallbacks or None)
    except LlmError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    print("--- Antwort ---")
    print(reply)
    return 0


def register_llm_commands(
    sub: argparse._SubParsersAction,
    add_root,
) -> None:
    llm_parser = sub.add_parser("llm", help="LLM / LiteLLM")
    llm_sub = llm_parser.add_subparsers(dest="llm_command", required=True)

    test = llm_sub.add_parser("test", help="Test-Prompt an das konfigurierte Modell")
    add_root(test)
    test.add_argument("--prompt", default="Sag Hallo auf Deutsch.")
    test.add_argument(
        "--task-category",
        default="planning",
        help="Task-Kategorie aus task_models.json",
    )
    test.add_argument(
        "--role",
        default="orchestrator",
        choices=["orchestrator", "worker", "reviewer"],
    )
    test.add_argument("--model", default=None, help="Model-Override")
    test.set_defaults(func=cmd_llm_test)
