"""Team-E-Mail-Konfiguration (`teams/<id>/email.json`)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


class EmailConfigError(Exception):
    pass


class ImapConfig(BaseModel):
    host: str
    port: int = 993
    use_ssl: bool = True
    username: str
    secret_ref: str
    mailbox: str = "INBOX"
    poll_interval_seconds: int = Field(default=120, ge=10)


class SmtpConfig(BaseModel):
    host: str
    port: int = 587
    starttls: bool = True
    use_ssl: bool = False
    username: str
    secret_ref: str
    from_display_name: str | None = None


class EmailRules(BaseModel):
    allowed_recipient_domains: list[str] = Field(default_factory=list)
    max_attachment_mb: int = 10
    require_approval: bool = True


class EmailTeamConfig(BaseModel):
    enabled: bool = True
    imap: ImapConfig
    smtp: SmtpConfig
    rules: EmailRules = Field(default_factory=EmailRules)


class EmailConfig(BaseModel):
    email: EmailTeamConfig


def _resolve_secret(secret_ref: str) -> str:
    value = os.environ.get(secret_ref, "").strip()
    if not value:
        raise EmailConfigError(
            f"Secret '{secret_ref}' nicht gesetzt (Umgebungsvariable)"
        )
    return value


def imap_password(cfg: EmailTeamConfig) -> str:
    return _resolve_secret(cfg.imap.secret_ref)


def smtp_password(cfg: EmailTeamConfig) -> str:
    return _resolve_secret(cfg.smtp.secret_ref)


def load_email_config(root: Path, team_id: str) -> EmailTeamConfig:
    path = root / "teams" / team_id / "email.json"
    if not path.is_file():
        raise EmailConfigError(f"Keine E-Mail-Config: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    parsed = EmailConfig.model_validate(data)
    if not parsed.email.enabled:
        raise EmailConfigError(f"E-Mail für Team '{team_id}' ist deaktiviert")
    return parsed.email


def validate_recipient(cfg: EmailTeamConfig, address: str) -> None:
    domains = cfg.rules.allowed_recipient_domains
    if not domains:
        return
    addr = address.strip().lower()
    if "@" not in addr:
        raise EmailConfigError(f"Ungültige Adresse: {address}")
    domain = addr.split("@", 1)[1]
    allowed = {d.lower() for d in domains}
    if domain not in allowed:
        raise EmailConfigError(
            f"Empfänger-Domain '{domain}' nicht erlaubt (erlaubt: {', '.join(sorted(allowed))})"
        )
