"""Backup und Restore für Team-Daten (SQLite, Workspace)."""

from __future__ import annotations

import json
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class BackupError(Exception):
    pass


def _team_data_dir(root: Path, team_id: str) -> Path:
    return root / "data" / team_id


def list_team_databases(root: Path, team_id: str) -> list[Path]:
    team_dir = _team_data_dir(root, team_id)
    if not team_dir.is_dir():
        return []
    return sorted(team_dir.glob("*.sqlite"))


def create_backup(
    root: Path | str,
    *,
    team_ids: list[str] | None = None,
    include_teams_config: bool = True,
    output: Path | None = None,
) -> Path:
    """Erstellt ein tar.gz mit data/<team>/ und optional teams/<team>/."""
    root_path = Path(root).resolve()
    data_root = root_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)

    if team_ids is None:
        team_ids = sorted(
            p.name for p in data_root.iterdir() if p.is_dir() and not p.name.startswith(".")
        )
    if not team_ids:
        raise BackupError("Keine Teams zum Sichern gefunden (data/<team>/)")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if output is None:
        out_dir = root_path / "data" / "_backups"
        out_dir.mkdir(parents=True, exist_ok=True)
        output = out_dir / f"bot-backup-{stamp}.tar.gz"
    output = output.resolve()

    manifest: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "teams": team_ids,
        "include_teams_config": include_teams_config,
        "files": [],
    }

    with tarfile.open(output, "w:gz") as tar:
        for team_id in team_ids:
            team_data = _team_data_dir(root_path, team_id)
            if team_data.is_dir():
                for path in team_data.rglob("*"):
                    if path.is_file():
                        arc = f"data/{team_id}/{path.relative_to(team_data).as_posix()}"
                        tar.add(path, arcname=arc)
                        manifest["files"].append(arc)
            if include_teams_config:
                team_cfg = root_path / "teams" / team_id
                if team_cfg.is_dir():
                    for path in team_cfg.rglob("*"):
                        if path.is_file() and "inbox" not in path.parts and "outbox" not in path.parts:
                            arc = f"teams/{team_id}/{path.relative_to(team_cfg).as_posix()}"
                            tar.add(path, arcname=arc)
                            manifest["files"].append(arc)

        manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
        import io

        info = tarfile.TarInfo(name="manifest.json")
        info.size = len(manifest_bytes)
        tar.addfile(info, io.BytesIO(manifest_bytes))

    return output


def restore_backup(
    root: Path | str,
    archive: Path | str,
    *,
    team_ids: list[str] | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Stellt ein Backup ins Projektroot zurück (überschreibt vorhandene Dateien)."""
    root_path = Path(root).resolve()
    archive_path = Path(archive).resolve()
    if not archive_path.is_file():
        raise BackupError(f"Archiv nicht gefunden: {archive_path}")

    restored: list[str] = []
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            if member.name == "manifest.json":
                continue
            if team_ids:
                parts = member.name.split("/")
                if len(parts) >= 2 and parts[0] in ("data", "teams"):
                    tid = parts[1]
                    if tid not in team_ids:
                        continue
            target = root_path / member.name
            if dry_run:
                restored.append(member.name)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            target.write_bytes(extracted.read())
            restored.append(member.name)
    return restored
