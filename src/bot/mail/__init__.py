"""E-Mail: IMAP lesen, Entwürfe mit Freigabe, SMTP senden."""

from bot.mail.config import EmailConfig, EmailConfigError, load_email_config
from bot.mail.service import MailService, MailServiceError

__all__ = [
    "EmailConfig",
    "EmailConfigError",
    "load_email_config",
    "MailService",
    "MailServiceError",
]
