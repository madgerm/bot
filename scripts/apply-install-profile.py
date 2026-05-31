#!/usr/bin/env python3
"""Installations-Profile: Example-Configs in config/ übernehmen (Panel/Runner/Satellit)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Overlay in base mergen (_comment-Keys ignorieren)."""
    result = dict(base)
    for key, value in overlay.items():
        if str(key).startswith("_"):
            continue
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON-Root muss ein Objekt sein: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def merge_system_example(root: Path, example_name: str) -> bool:
    config_dir = root / "config"
    system_path = config_dir / "system.json"
    example_path = config_dir / example_name
    if not example_path.is_file():
        print(f"Beispiel fehlt: {example_path}", file=sys.stderr)
        return False
    if not system_path.is_file():
        print(f"system.json fehlt: {system_path}", file=sys.stderr)
        return False
    base = load_json(system_path)
    overlay = load_json(example_path)
    merged = deep_merge(base, overlay)
    write_json(system_path, merged)
    print(f"system.json ← {example_name}")
    return True


def copy_if_missing(root: Path, example_name: str, target_name: str) -> bool:
    config_dir = root / "config"
    example_path = config_dir / example_name
    target_path = config_dir / target_name
    if target_path.is_file():
        print(f"übersprungen (existiert): {target_name}")
        return False
    if not example_path.is_file():
        print(f"Beispiel fehlt: {example_path}", file=sys.stderr)
        return False
    target_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"{target_name} ← {example_name}")
    return True


def write_team_api(root: Path, *, token_env: str, teams: list[str]) -> None:
    path = root / "config" / "team_api.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {"token_env": token_env, "teams": teams})


def list_team_ids(root: Path) -> list[str]:
    teams_dir = root / "teams"
    if not teams_dir.is_dir():
        return ["demo"]
    ids = sorted(
        p.name
        for p in teams_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
    return ids or ["demo"]


def apply_profile(root: Path, profile: str, *, channel_hosts: bool = False) -> int:
    profile = profile.strip().lower()
    if profile == "relay":
        print("Profil relay: keine Config-Dateien (nur Relay-Dienst).")
        return 0

    ok = True
    if profile == "panel":
        ok = merge_system_example(root, "system.panel-lan.example.json") and ok
        if channel_hosts:
            ok = (
                copy_if_missing(
                    root,
                    "team_hosts.channel.example.json",
                    "team_hosts.json",
                )
                or True
            ) and ok
    elif profile in ("runner", "satellite"):
        ok = merge_system_example(root, "system.runner-channel.example.json") and ok
        teams = list_team_ids(root)
        write_team_api(root, token_env="BOT_TEAM_API_TOKEN", teams=teams)
        print(f"team_api.json angelegt (teams={teams})")
    else:
        print(f"Unbekanntes Profil: {profile}", file=sys.stderr)
        return 1
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Bot-Projektroot (BOT_ROOT)")
    parser.add_argument(
        "profile",
        choices=("panel", "runner", "satellite", "relay"),
        help="Installationsprofil",
    )
    parser.add_argument(
        "--channel-hosts",
        action="store_true",
        help="Panel: team_hosts.channel.example.json kopieren wenn fehlend",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / "pyproject.toml").is_file():
        print(f"Kein Bot-Projekt: {root}", file=sys.stderr)
        return 1
    return apply_profile(root, args.profile, channel_hosts=args.channel_hosts)


if __name__ == "__main__":
    raise SystemExit(main())
