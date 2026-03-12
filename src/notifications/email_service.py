"""SMTP email service for ticket notifications.

Uses Python's built-in smtplib + email.mime (zero external dependencies).
All sends are logged to the email_notifications table for tracking.
If SMTP is not configured, emails are logged but not sent.
"""

from __future__ import annotations

import html
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import get_settings
from src.storage.sqlite_db import get_connection, init_database

logger = logging.getLogger(__name__)


def _is_smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_sender)


def _record_notification(
    ticket_id: str,
    recipient: str,
    subject: str,
    body_preview: str,
    status: str = "pending",
    error_message: str = "",
) -> None:
    init_database()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO email_notifications
               (ticket_id, recipient, subject, body_preview, status, sent_at, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                ticket_id,
                recipient,
                subject,
                body_preview[:500],
                status,
                datetime.now(timezone.utc).isoformat(),
                error_message,
            ),
        )


def _send_email(recipient: str, subject: str, html_body: str, text_body: str) -> None:
    """Deliver an email via SMTP. Raises on failure."""
    settings = get_settings()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_sender
    msg["To"] = recipient
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    logger.info(
        "Sending email via %s:%s from=%s to=%s",
        settings.smtp_host, settings.smtp_port, settings.smtp_sender, recipient,
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.smtp_sender, [recipient], msg.as_string())
    logger.info("Email delivered successfully to %s", recipient)


def _brand_html(inner: str) -> str:
    """Wrap content in a branded HTML email template."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;background:#f7f8fa;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#ffffff;">
    <tr>
      <td style="background:#003E7E;padding:24px 32px;text-align:center;">
        <h1 style="margin:0;color:#C9A961;font-size:22px;">HOPE AI</h1>
        <p style="margin:4px 0 0;color:rgba(255,255,255,0.7);font-size:13px;">Operation HOPE Support Intelligence</p>
      </td>
    </tr>
    <tr>
      <td style="padding:32px;">
        {inner}
      </td>
    </tr>
    <tr>
      <td style="background:#f7f8fa;padding:20px 32px;text-align:center;font-size:12px;color:#64748b;">
        Operation HOPE &copy; {datetime.now().year} &mdash; Financial dignity through smarter support
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_ticket_confirmation(
    ticket_id: str,
    recipient_email: str,
    recipient_name: str,
    subject: str,
) -> None:
    """Send a confirmation email after a public ticket is created."""
    email_subject = f"[{ticket_id}] Your support request has been received"
    safe_recipient_name = html.escape(recipient_name)
    safe_ticket_id = html.escape(ticket_id)
    safe_subject = html.escape(subject)

    inner_html = f"""\
<h2 style="margin:0 0 12px;color:#003E7E;font-size:20px;">Request Received</h2>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  Hi {safe_recipient_name},
</p>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  Thank you for contacting Operation HOPE. Your support request has been received
  and assigned to the appropriate team.
</p>
<table width="100%" style="margin:20px 0;border:2px dashed #C9A961;border-radius:10px;padding:16px;">
  <tr>
    <td style="text-align:center;">
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;">Ticket ID</span><br>
      <strong style="font-size:22px;color:#003E7E;font-family:monospace;">{safe_ticket_id}</strong>
    </td>
  </tr>
</table>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  <strong>Subject:</strong> {safe_subject}
</p>
<p style="color:#64748b;font-size:13px;line-height:1.7;">
  You will receive email updates as your request is reviewed and processed.
  Please save your ticket ID for reference.
</p>"""

    text_body = (
        f"Hi {recipient_name},\n\n"
        f"Your support request has been received.\n"
        f"Ticket ID: {ticket_id}\n"
        f"Subject: {subject}\n\n"
        f"You will receive updates as your request is processed.\n\n"
        f"-- Operation HOPE"
    )

    html_body = _brand_html(inner_html)

    if _is_smtp_configured():
        try:
            _send_email(recipient_email, email_subject, html_body, text_body)
            _record_notification(ticket_id, recipient_email, email_subject, text_body[:200], status="sent")
            logger.info("Confirmation email sent for %s to %s", ticket_id, recipient_email)
        except Exception as exc:
            _record_notification(
                ticket_id, recipient_email, email_subject, text_body[:200],
                status="failed", error_message=str(exc),
            )
            logger.warning("Failed to send confirmation email for %s: %s", ticket_id, exc)
    else:
        _record_notification(
            ticket_id, recipient_email, email_subject, text_body[:200],
            status="skipped_no_smtp",
        )
        logger.info("SMTP not configured; confirmation for %s logged but not sent", ticket_id)


def send_status_update(
    ticket_id: str,
    recipient_email: str,
    recipient_name: str,
    new_status: str,
    details: str = "",
) -> None:
    """Send a status update email when a ticket changes status."""
    normalized_status = new_status.strip().lower()
    status_label = {
        "approved": "Approved",
        "closed": "Closed",
        "sent": "Resolved & Sent",
        "rejected": "Needs More Information",
        "rerouted": "Rerouted to Another Team",
    }.get(normalized_status, normalized_status.replace("_", " ").title())

    email_subject = f"[{ticket_id}] Status update: {status_label}"

    status_color = "#059669" if normalized_status in ("approved", "closed", "sent") else "#d97706"
    safe_recipient_name = html.escape(recipient_name)
    safe_ticket_id = html.escape(ticket_id)
    safe_details = html.escape(details).replace("\n", "<br>")

    inner_html = f"""\
<h2 style="margin:0 0 12px;color:#003E7E;font-size:20px;">Ticket Update</h2>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  Hi {safe_recipient_name},
</p>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  There is an update on your support request <strong>{safe_ticket_id}</strong>:
</p>
<table width="100%" style="margin:20px 0;background:#f7f8fa;border-radius:10px;padding:16px;">
  <tr>
    <td>
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;">Status</span><br>
      <strong style="font-size:16px;color:{status_color};">{status_label}</strong>
    </td>
  </tr>
  {"<tr><td style='padding-top:12px;'><span style='font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;'>Details</span><br><span style='font-size:14px;color:#1e293b;'>" + safe_details + "</span></td></tr>" if details else ""}
</table>
<p style="color:#64748b;font-size:13px;line-height:1.7;">
  If you have questions, please reply with your ticket ID for reference.
</p>"""

    text_body = (
        f"Hi {recipient_name},\n\n"
        f"Your support request {ticket_id} has been updated.\n"
        f"Status: {status_label}\n"
        f"{('Details: ' + details + chr(10)) if details else ''}\n"
        f"-- Operation HOPE"
    )

    html_body = _brand_html(inner_html)

    if _is_smtp_configured():
        try:
            _send_email(recipient_email, email_subject, html_body, text_body)
            _record_notification(ticket_id, recipient_email, email_subject, text_body[:200], status="sent")
            logger.info("Status update email sent for %s to %s", ticket_id, recipient_email)
        except Exception as exc:
            _record_notification(
                ticket_id, recipient_email, email_subject, text_body[:200],
                status="failed", error_message=str(exc),
            )
            logger.warning("Failed to send status update for %s: %s", ticket_id, exc)
    else:
        _record_notification(
            ticket_id, recipient_email, email_subject, text_body[:200],
            status="skipped_no_smtp",
        )
        logger.info("SMTP not configured; status update for %s logged but not sent", ticket_id)


def get_notifications_for_ticket(ticket_id: str) -> list[dict]:
    """Return all email notification records for a given ticket."""
    init_database()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM email_notifications WHERE ticket_id = ? ORDER BY id ASC",
            (ticket_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "ticket_id": row["ticket_id"],
            "recipient": row["recipient"],
            "subject": row["subject"],
            "body_preview": row["body_preview"],
            "status": row["status"],
            "sent_at": row["sent_at"],
            "error_message": row["error_message"],
        }
        for row in rows
    ]


def get_submitter_email(ticket_id: str) -> tuple[str, str]:
    """Look up submitter name and email for a ticket. Returns (name, email)."""
    init_database()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT submitter, submitter_email FROM tickets WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
    if row is None:
        return ("", "")
    return (row["submitter"], row["submitter_email"] or "")
