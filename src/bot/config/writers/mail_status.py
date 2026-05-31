"""Status-Checks für Team-E-Mail (Panel /admin/settings/status)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bot.config.writers.system_admin import env_var_is_set
from bot.mail.config import EmailConfig, EmailTeamConfig


def teams_with_email_config(root: Path) -> list[str]:
    teams_dir = root / "teams"
    if not teams_dir.is_dir():
        return []
    ids: list[str] = []
    for path in sorted(teams_dir.iterdir()):
        if path.is_dir() and (path / "email.json").is_file():
            ids.append(path.name)
    return ids


def _load_email_team(root: Path, team_id: str) -> EmailTeamConfig:
    path = root / "teams" / team_id / "email.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    parsed = EmailConfig.model_validate(data)
    return parsed.email


def probe_team_mail_config(root: Path, team_id: str) -> dict[str, Any]:
    """Konfiguration und Secret-Env ohne Netzwerk."""
    try:
        cfg = _load_email_team(root, team_id)
    except Exception as exc:
        return {
            "team_id": team_id,
            "ok": False,
            "summary": str(exc),
            "imap_ok": None,
            "smtp_ok": None,
            "probe_summary": None,
        }

    if not cfg.enabled:
        return {
            "team_id": team_id,
            "ok": True,
            "summary": "E-Mail deaktiviert",
            "imap_ok": None,
            "smtp_ok": None,
            "probe_summary": None,
        }

    imap_secret = env_var_is_set(cfg.imap.secret_ref)
    smtp_secret = env_var_is_set(cfg.smtp.secret_ref)
    config_ok = imap_secret and smtp_secret
    parts = [
        f"IMAP {cfg.imap.host}:{cfg.imap.port}",
        f"SMTP {cfg.smtp.host}:{cfg.smtp.port}",
        f"{cfg.imap.secret_ref}: {'✓' if imap_secret else '✗'}",
        f"{cfg.smtp.secret_ref}: {'✓' if smtp_secret else '✗'}",
    ]
    return {
        "team_id": team_id,
        "ok": config_ok,
        "summary": " · ".join(parts),
        "imap_ok": imap_secret,
        "smtp_ok": smtp_secret,
        "probe_summary": None,
    }


def probe_team_mail_connections(root: Path, team_id: str) -> dict[str, Any]:
    """IMAP/SMTP Login-Test (kein Versand)."""
    base = probe_team_mail_config(root, team_id)
    if not base.get("ok") and base.get("summary") == "E-Mail deaktiviert":
        base["probe_summary"] = "Kein Verbindungstest (deaktiviert)"
        return base
    if not base.get("ok"):
        base["probe_summary"] = "Verbindungstest übersprungen (Config/Secrets unvollständig)"
        return base

    from bot.mail.service import MailService, MailServiceError

    try:
        svc = MailService.for_team(root, team_id)
        results = svc.test_connections()
    except MailServiceError as exc:
        return {
            **base,
            "ok": False,
            "probe_summary": str(exc),
        }

    imap_line = results.get("imap", "?")
    smtp_line = results.get("smtp", "?")
    imap_ok = imap_line == "ok"
    smtp_ok = smtp_line == "ok"
    probe_ok = imap_ok and smtp_ok
    return {
        **base,
        "ok": probe_ok,
        "imap_ok": imap_ok,
        "smtp_ok": smtp_ok,
        "probe_summary": f"IMAP: {imap_line} · SMTP: {smtp_line}",
    }


def collect_mail_status(root: Path, *, probe: bool = False) -> dict[str, Any]:
    team_ids = teams_with_email_config(root)
    rows = [
        probe_team_mail_connections(root, tid) if probe else probe_team_mail_config(root, tid)
        for tid in team_ids
    ]
    if not rows:
        return {
            "teams": [],
            "ok": None,
            "summary": "Kein Team mit email.json",
        }
    all_ok = all(r.get("ok") for r in rows)
    return {
        "teams": rows,
        "ok": all_ok,
        "summary": f"{len(rows)} Team(s) mit E-Mail-Config",
    }
