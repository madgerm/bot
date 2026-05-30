"""mtime-Snapshot für Agent-Inboxen (schnelle Reaktion auf neue Messages)."""

from __future__ import annotations

from pathlib import Path


def inbox_pending_snapshot(inbox: Path) -> dict[Path, float]:
    """Nur pending JSON direkt in der Inbox (nicht processed/failed)."""
    if not inbox.is_dir():
        return {}
    state: dict[Path, float] = {}
    for path in inbox.glob("*.json"):
        if path.name.endswith(".tmp"):
            continue
        state[path] = path.stat().st_mtime
    return state
