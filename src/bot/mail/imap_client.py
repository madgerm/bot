"""IMAP-Polling (stdlib)."""

from __future__ import annotations

import email
import imaplib
from dataclasses import dataclass
from email.header import decode_header
from email.utils import parseaddr

from bot.mail.config import EmailTeamConfig, imap_password


@dataclass
class FetchedMessage:
    uid: str
    subject: str
    from_addr: str
    body_text: str


class ImapClientError(Exception):
    pass


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out: list[str] = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(chunk)
    return "".join(out)


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    charset = msg.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def fetch_unseen(cfg: EmailTeamConfig, *, limit: int = 20) -> list[FetchedMessage]:
    password = imap_password(cfg)
    try:
        if cfg.imap.use_ssl:
            client = imaplib.IMAP4_SSL(cfg.imap.host, cfg.imap.port)
        else:
            client = imaplib.IMAP4(cfg.imap.host, cfg.imap.port)
        client.login(cfg.imap.username, password)
        client.select(cfg.imap.mailbox)
        _typ, data = client.search(None, "UNSEEN")
        if not data or not data[0]:
            client.logout()
            return []

        uids = data[0].split()[-limit:]
        results: list[FetchedMessage] = []
        for uid in uids:
            _typ, msg_data = client.fetch(uid, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            if not isinstance(raw, bytes):
                continue
            msg = email.message_from_bytes(raw)
            subject = _decode_header_value(msg.get("Subject"))
            _name, from_addr = parseaddr(msg.get("From", ""))
            body = _extract_body(msg).strip() or "(kein Textinhalt)"
            results.append(
                FetchedMessage(
                    uid=uid.decode() if isinstance(uid, bytes) else str(uid),
                    subject=subject or "(ohne Betreff)",
                    from_addr=from_addr or "unknown",
                    body_text=body,
                )
            )
        client.logout()
        return results
    except imaplib.IMAP4.error as exc:
        raise ImapClientError(str(exc)) from exc
    except OSError as exc:
        raise ImapClientError(str(exc)) from exc


def test_imap_connection(cfg: EmailTeamConfig) -> None:
    password = imap_password(cfg)
    try:
        if cfg.imap.use_ssl:
            client = imaplib.IMAP4_SSL(cfg.imap.host, cfg.imap.port)
        else:
            client = imaplib.IMAP4(cfg.imap.host, cfg.imap.port)
        client.login(cfg.imap.username, password)
        client.select(cfg.imap.mailbox)
        client.logout()
    except imaplib.IMAP4.error as exc:
        raise ImapClientError(f"IMAP: {exc}") from exc
