"""SMTP-Versand (stdlib) — nur nach Freigabe aufrufen."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from bot.mail.config import EmailTeamConfig, smtp_password, validate_recipient


class SmtpClientError(Exception):
    pass


def send_message(
    cfg: EmailTeamConfig,
    *,
    to_addrs: list[str],
    subject: str,
    body_text: str,
    in_reply_to: str | None = None,
) -> None:
    for addr in to_addrs:
        validate_recipient(cfg, addr)

    password = smtp_password(cfg)
    msg = EmailMessage()
    display = cfg.smtp.from_display_name
    from_addr = cfg.smtp.username
    if display:
        msg["From"] = f"{display} <{from_addr}>"
    else:
        msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.set_content(body_text)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to

    try:
        if cfg.smtp.use_ssl:
            with smtplib.SMTP_SSL(cfg.smtp.host, cfg.smtp.port) as smtp:
                smtp.login(cfg.smtp.username, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg.smtp.host, cfg.smtp.port) as smtp:
                if cfg.smtp.starttls:
                    smtp.starttls()
                smtp.login(cfg.smtp.username, password)
                smtp.send_message(msg)
    except smtplib.SMTPException as exc:
        raise SmtpClientError(str(exc)) from exc
    except OSError as exc:
        raise SmtpClientError(str(exc)) from exc


def test_smtp_connection(cfg: EmailTeamConfig) -> None:
    password = smtp_password(cfg)
    try:
        if cfg.smtp.use_ssl:
            client: smtplib.SMTP = smtplib.SMTP_SSL(cfg.smtp.host, cfg.smtp.port)
        else:
            client = smtplib.SMTP(cfg.smtp.host, cfg.smtp.port)
            if cfg.smtp.starttls:
                client.starttls()
        client.login(cfg.smtp.username, password)
        client.quit()
    except smtplib.SMTPException as exc:
        raise SmtpClientError(f"SMTP: {exc}") from exc
