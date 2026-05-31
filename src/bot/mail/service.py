"""Orchestrierung: Poll, Entwurf, Freigabe, Versand."""

from __future__ import annotations

from pathlib import Path

from bot.approval.status import ApprovalError, assert_can_send
from bot.mail.config import EmailConfigError, EmailTeamConfig, load_email_config
from bot.mail.imap_client import ImapClientError, fetch_unseen, test_imap_connection
from bot.mail.smtp_client import SmtpClientError, send_message, test_smtp_connection
from bot.mail.store import EmailDraft, EmailThread, MailStore, MailStoreError


class MailServiceError(Exception):
    pass


class MailService:
    def __init__(self, root: Path, team_id: str, cfg: EmailTeamConfig) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.cfg = cfg
        self.store = MailStore(root, team_id)

    @classmethod
    def for_team(cls, root: Path, team_id: str) -> MailService:
        try:
            cfg = load_email_config(root, team_id)
        except EmailConfigError as exc:
            raise MailServiceError(str(exc)) from exc
        return cls(root, team_id, cfg)

    def test_connections(self) -> dict[str, str]:
        results: dict[str, str] = {}
        try:
            test_imap_connection(self.cfg)
            results["imap"] = "ok"
        except ImapClientError as exc:
            results["imap"] = f"fehler: {exc}"
        try:
            test_smtp_connection(self.cfg)
            results["smtp"] = "ok"
        except SmtpClientError as exc:
            results["smtp"] = f"fehler: {exc}"
        return results

    def poll(self, *, limit: int = 20) -> list[EmailThread]:
        """Neue IMAP-Mails abholen. Rückgabe nur **neu** angelegte Threads."""
        try:
            fetched = fetch_unseen(self.cfg, limit=limit)
        except ImapClientError as exc:
            raise MailServiceError(str(exc)) from exc

        new_threads: list[EmailThread] = []
        for item in fetched:
            if item.uid and self.store.thread_by_imap_uid(item.uid):
                continue
            thread = self.store.add_thread(
                subject=item.subject,
                from_addr=item.from_addr,
                body_text=item.body_text,
                imap_uid=item.uid,
            )
            new_threads.append(thread)
        return new_threads

    def revise_draft(
        self,
        draft_id: str,
        *,
        feedback: str,
        revised_by: str,
    ) -> EmailDraft:
        """Ablehnen des alten Entwurfs + neuer Entwurf mit Anmerkung."""
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise MailServiceError(f"Entwurf nicht gefunden: {draft_id}")
        if draft.status not in ("draft", "awaiting_approval"):
            raise MailServiceError(
                f"Entwurf kann nicht überarbeitet werden (Status: {draft.status})"
            )
        try:
            self.store.reject_draft(draft_id)
        except MailStoreError as exc:
            raise MailServiceError(str(exc)) from exc

        note = feedback.strip()
        body = draft.body_text
        if note:
            body = f"{body.rstrip()}\n\n---\nAnmerkung ({revised_by}):\n{note}"
        return self.store.create_draft(
            thread_id=draft.thread_id,
            subject=draft.subject,
            body_text=body,
            to_addrs=list(draft.to_addrs),
            created_by=revised_by,
            submit=True,
        )

    def import_fixture(
        self,
        *,
        subject: str,
        from_addr: str,
        body_text: str,
        imap_uid: str | None = None,
    ) -> EmailThread:
        """Für Tests/Demo ohne echten IMAP-Server."""
        return self.store.add_thread(
            subject=subject,
            from_addr=from_addr,
            body_text=body_text,
            imap_uid=imap_uid,
        )

    def create_reply_draft(
        self,
        thread_id: str,
        *,
        body_text: str,
        to_addrs: list[str] | None = None,
        subject: str | None = None,
        created_by: str | None = None,
    ) -> EmailDraft:
        thread = self.store.get_thread(thread_id)
        if not thread:
            raise MailServiceError(f"Thread nicht gefunden: {thread_id}")
        recipients = to_addrs or [thread.from_addr]
        subj = subject or f"Re: {thread.subject}"
        return self.store.create_draft(
            thread_id=thread_id,
            subject=subj,
            body_text=body_text,
            to_addrs=recipients,
            created_by=created_by,
            submit=True,
        )

    def approve(self, draft_id: str, approved_by: str) -> EmailDraft:
        try:
            return self.store.approve_draft(draft_id, approved_by)
        except MailStoreError as exc:
            raise MailServiceError(str(exc)) from exc

    def reject(self, draft_id: str) -> EmailDraft:
        try:
            return self.store.reject_draft(draft_id)
        except MailStoreError as exc:
            raise MailServiceError(str(exc)) from exc

    def send_approved(self, draft_id: str) -> EmailDraft:
        draft = self.store.get_draft(draft_id)
        if not draft:
            raise MailServiceError(f"Entwurf nicht gefunden: {draft_id}")
        try:
            assert_can_send(draft.status)
        except ApprovalError as exc:
            raise MailServiceError(str(exc)) from exc

        try:
            send_message(
                self.cfg,
                to_addrs=draft.to_addrs,
                subject=draft.subject,
                body_text=draft.body_text,
            )
        except (SmtpClientError, EmailConfigError) as exc:
            self.store.mark_draft_failed(draft_id)
            raise MailServiceError(str(exc)) from exc

        return self.store.mark_draft_sent(draft_id)
