import logging
import smtplib
from email.message import EmailMessage

from ..config import get_settings

log = logging.getLogger("visualfind.email")


def send_email(to: str, subject: str, body: str) -> bool:
    """Returns True if sent via SMTP. Without SMTP configuration nothing is sent."""
    s = get_settings()
    if not s.smtp_configured:
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:
        log.exception("SMTP send failed")
        return False
