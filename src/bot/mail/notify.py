"""Interne Agent-Benachrichtigung bei neuen E-Mail-Threads."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from bot.config.loader import discover_teams
from bot.mail.store import EmailThread
from bot.messages.mailbox import Mailbox
from bot.messages.models import new_message

logger = logging.getLogger(__name__)


def notify_new_mail_threads(
    root: Path,
    team_id: str,
    threads: list[EmailThread],
    *,
    notify_agents: bool = True,
) -> int:
    """Legt pro neuem Thread eine Message beim Orchestrator ab. Rückgabe: Anzahl."""
    if not notify_agents or not threads:
        return 0

    teams = discover_teams(root / "teams")
    bundle = teams.get(team_id)
    if not bundle:
        logger.warning("Team %s nicht gefunden — keine Mail-Notify", team_id)
        return 0

    from bot.config import ConfigStore

    orch_id = bundle.team.team.orchestrator_id
    inbox_template = ConfigStore(root).get().system.system.communication.inbox_base
    mailbox = Mailbox(root, team_id, orch_id, inbox_template)
    mailbox.ensure_dirs()

    count = 0
    for thread in threads:
        payload = {
            "thread_id": thread.id,
            "from_addr": thread.from_addr,
            "subject": thread.subject,
        }
        msg = new_message(
            team_id=team_id,
            from_agent="system",
            to_agent=orch_id,
            subject=f"E-Mail: {thread.subject}",
            content=json.dumps(payload, ensure_ascii=False),
            type="email.incoming",
            task_category="planning",
        )
        try:
            mailbox.receive(msg)
            count += 1
        except Exception as exc:
            logger.warning("Mail-Notify fehlgeschlagen für %s: %s", thread.id, exc)
    return count
