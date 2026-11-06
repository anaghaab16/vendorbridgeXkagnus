import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("vendorbridge.mail")


class MailNotConfigured(Exception):
    pass


class MailFailed(Exception):
    pass


def email_enabled() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def send_invoice_email(to: str, invoice_number: str, vendor_name: str, total_text: str, due_text: str, pdf: bytes):
    """Send the invoice PDF through the SMTP server named in the settings."""
    if not email_enabled():
        raise MailNotConfigured(
            "Email is not configured on the server. Set the SMTP_ settings in .env.")
    msg = EmailMessage()
    msg["Subject"] = f"Invoice {invoice_number} from {settings.company_name}"
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(
        f"Hello {vendor_name},\n\nPlease find invoice {invoice_number} attached.\n"
        f"Amount: {total_text}\nDue date: {due_text}\n\nRegards,\n{settings.company_name}\n"
    )
    msg.add_attachment(pdf, maintype="application",
                       subtype="pdf", filename=f"{invoice_number}.pdf")
    try:
        smtp_cls = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
        with smtp_cls(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if smtp_cls is smtplib.SMTP:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        # details stay in the server log, not in the reply
        log.warning("invoice email failed: %s", exc)
        raise MailFailed(type(exc).__name__) from exc
