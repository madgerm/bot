"""Dateizugriff nur innerhalb des Team-Workspace-Roots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class FileServiceError(Exception):
    pass


@dataclass
class FileEntry:
    name: str
    path: str
    is_dir: bool
    size: int | None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "is_dir": self.is_dir,
            "size": self.size,
        }


class FileService:
    def __init__(self, root: Path | str, team_id: str) -> None:
        self.root = Path(root).resolve()
        self.team_id = team_id
        self.workspace = self.root / "data" / team_id / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> FileService:
        return cls(root, team_id)

    def _resolve(self, rel_path: str) -> Path:
        rel = rel_path.strip().lstrip("/")
        target = (self.workspace / rel).resolve()
        if not str(target).startswith(str(self.workspace.resolve())):
            raise FileServiceError("Pfad außerhalb des Workspace")
        return target

    def list_dir(self, rel_path: str = "") -> list[FileEntry]:
        target = self._resolve(rel_path)
        if not target.is_dir():
            raise FileServiceError("Kein Verzeichnis")
        entries: list[FileEntry] = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            rel = str(child.relative_to(self.workspace))
            entries.append(
                FileEntry(
                    name=child.name,
                    path=rel,
                    is_dir=child.is_dir(),
                    size=child.stat().st_size if child.is_file() else None,
                )
            )
        return entries

    def read_file(self, rel_path: str) -> str:
        target = self._resolve(rel_path)
        if not target.is_file():
            raise FileServiceError("Keine Datei")
        return target.read_text(encoding="utf-8", errors="replace")

    def write_file(self, rel_path: str, content: str) -> None:
        target = self._resolve(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def mkdir(self, rel_path: str) -> None:
        target = self._resolve(rel_path)
        target.mkdir(parents=True, exist_ok=True)

    def delete(self, rel_path: str) -> None:
        target = self._resolve(rel_path)
        if target == self.workspace.resolve():
            raise FileServiceError("Workspace-Root kann nicht gelöscht werden")
        if target.is_dir():
            import shutil

            shutil.rmtree(target)
        elif target.is_file():
            target.unlink()
        else:
            raise FileServiceError("Pfad nicht gefunden")
