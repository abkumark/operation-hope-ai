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
    """Check if SMTP is actually configured (not just defaults).

    Requires smtp_username to be set, because the default smtp_host='localhost'
    and smtp_sender='noreply@...' would make this return True without a real server.
    """
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_sender and settings.smtp_username)


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
    """Deliver an email via SMTP. Raises on failure.

    The configured ``escalation_email`` is automatically BCC'd on every
    outgoing message so the central mailbox stays in the loop.
    """
    settings = get_settings()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_sender
    msg["To"] = recipient
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Build envelope recipients: always BCC the escalation mailbox so the
    # central inbox gets a copy of every email the system sends.
    envelope_recipients = [recipient]
    bcc_addr = settings.escalation_email
    if bcc_addr and bcc_addr.lower() != recipient.lower():
        envelope_recipients.append(bcc_addr)

    logger.info(
        "Sending email via %s:%s from=%s to=%s bcc=%s",
        settings.smtp_host, settings.smtp_port, settings.smtp_sender,
        recipient, bcc_addr or "(none)",
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.smtp_sender, envelope_recipients, msg.as_string())
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
    language: str = "en",
) -> None:
    """Send a confirmation email after a public ticket is created."""
    is_es = (language or "").strip().lower() in ("es", "spanish")

    email_subject = (
        f"[{ticket_id}] Su solicitud de soporte ha sido recibida"
        if is_es
        else f"[{ticket_id}] Your support request has been received"
    )
    safe_recipient_name = html.escape(recipient_name)
    safe_ticket_id = html.escape(ticket_id)
    safe_subject = html.escape(subject)

    if is_es:
        inner_html = f"""\
<h2 style="margin:0 0 12px;color:#003E7E;font-size:20px;">Solicitud Recibida</h2>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  Hola {safe_recipient_name},
</p>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  Gracias por contactar a Operation HOPE. Su solicitud de soporte ha sido recibida
  y asignada al equipo correspondiente.
</p>
<table width="100%" style="margin:20px 0;border:2px dashed #C9A961;border-radius:10px;padding:16px;">
  <tr>
    <td style="text-align:center;">
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;">ID del Ticket</span><br>
      <strong style="font-size:22px;color:#003E7E;font-family:monospace;">{safe_ticket_id}</strong>
    </td>
  </tr>
</table>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  <strong>Asunto:</strong> {safe_subject}
</p>
<p style="color:#64748b;font-size:13px;line-height:1.7;">
  Recibirá actualizaciones por correo electrónico a medida que su solicitud sea
  revisada y procesada. Por favor guarde su ID de ticket como referencia.
</p>"""

        text_body = (
            f"Hola {recipient_name},\n\n"
            f"Su solicitud de soporte ha sido recibida.\n"
            f"ID del Ticket: {ticket_id}\n"
            f"Asunto: {subject}\n\n"
            f"Recibirá actualizaciones a medida que su solicitud sea procesada.\n\n"
            f"-- Operation HOPE"
        )
    else:
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
        "completed": "Completed",
        "closed": "Closed",
        "sent": "Resolved & Sent",
        "rejected": "Needs More Information",
        "rerouted": "Rerouted to Another Team",
        "workinprogress": "Work In Progress",
        "in_review": "Under Review",
    }.get(normalized_status, normalized_status.replace("_", " ").title())

    email_subject = f"[{ticket_id}] Status update: {status_label}"

    status_color = "#059669" if normalized_status in ("approved", "closed", "sent", "completed") else "#d97706"
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


def send_case_closed_email(
    ticket_id: str,
    recipient_email: str,
    recipient_name: str,
    resolution_text: str = "",
    language: str = "en",
) -> None:
    """Send a branded case-closed email when a ticket is resolved/closed."""
    is_es = (language or "").strip().lower() in ("es", "spanish")

    email_subject = (
        f"[{ticket_id}] Su solicitud de soporte ha sido resuelta"
        if is_es
        else f"[{ticket_id}] Your support request has been resolved"
    )
    safe_recipient_name = html.escape(recipient_name)
    safe_ticket_id = html.escape(ticket_id)
    safe_resolution = html.escape(resolution_text).replace("\n", "<br>") if resolution_text else ""

    if is_es:
        inner_html = f"""\
<h2 style="margin:0 0 12px;color:#003E7E;font-size:20px;">Caso Resuelto</h2>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  Hola {safe_recipient_name},
</p>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  ¡Buenas noticias! Su solicitud de soporte <strong>{safe_ticket_id}</strong> ha sido resuelta
  y ahora está cerrada.
</p>
{"<table width='100%' style='margin:20px 0;background:#f0fdf4;border-left:4px solid #059669;border-radius:6px;padding:16px;'><tr><td><span style='font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#059669;'>Resolución</span><br><span style='font-size:14px;color:#1e293b;line-height:1.7;'>" + safe_resolution + "</span></td></tr></table>" if resolution_text else ""}
<p style="color:#64748b;font-size:13px;line-height:1.7;">
  Si esto no resolvió completamente su problema, o si tiene preguntas adicionales,
  responda con su ID de ticket <strong>{safe_ticket_id}</strong> y reabriremos su caso.
</p>
<p style="color:#64748b;font-size:13px;line-height:1.7;">
  Gracias por su paciencia y por ser parte de la comunidad de Operation HOPE.
</p>"""

        text_body = (
            f"Hola {recipient_name},\n\n"
            f"Su solicitud de soporte {ticket_id} ha sido resuelta y ahora está cerrada.\n\n"
            f"{('Resolución: ' + resolution_text + chr(10) + chr(10)) if resolution_text else ''}"
            f"Si esto no resolvió completamente su problema, responda con su ID de ticket "
            f"y reabriremos su caso.\n\n"
            f"Gracias,\n"
            f"-- Operation HOPE"
        )
    else:
        inner_html = f"""\
<h2 style="margin:0 0 12px;color:#003E7E;font-size:20px;">Case Resolved</h2>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  Hi {safe_recipient_name},
</p>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  Great news! Your support request <strong>{safe_ticket_id}</strong> has been resolved
  and is now closed.
</p>
{"<table width='100%' style='margin:20px 0;background:#f0fdf4;border-left:4px solid #059669;border-radius:6px;padding:16px;'><tr><td><span style='font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#059669;'>Resolution</span><br><span style='font-size:14px;color:#1e293b;line-height:1.7;'>" + safe_resolution + "</span></td></tr></table>" if resolution_text else ""}
<p style="color:#64748b;font-size:13px;line-height:1.7;">
  If this did not fully resolve your issue, or if you have additional questions,
  please reply with your ticket ID <strong>{safe_ticket_id}</strong> and we will reopen your case.
</p>
<p style="color:#64748b;font-size:13px;line-height:1.7;">
  Thank you for your patience and for being part of the Operation HOPE community.
</p>"""

    text_body = (
        f"Hi {recipient_name},\n\n"
        f"Your support request {ticket_id} has been resolved and is now closed.\n\n"
        f"{('Resolution: ' + resolution_text + chr(10) + chr(10)) if resolution_text else ''}"
        f"If this did not fully resolve your issue, please reply with your ticket ID "
        f"and we will reopen your case.\n\n"
        f"Thank you,\n"
        f"-- Operation HOPE"
    )

    html_body = _brand_html(inner_html)

    if _is_smtp_configured():
        try:
            _send_email(recipient_email, email_subject, html_body, text_body)
            _record_notification(ticket_id, recipient_email, email_subject, text_body[:200], status="sent")
            logger.info("Case-closed email sent for %s to %s", ticket_id, recipient_email)
        except Exception as exc:
            _record_notification(
                ticket_id, recipient_email, email_subject, text_body[:200],
                status="failed", error_message=str(exc),
            )
            logger.warning("Failed to send case-closed email for %s: %s", ticket_id, exc)
    else:
        _record_notification(
            ticket_id, recipient_email, email_subject, text_body[:200],
            status="skipped_no_smtp",
        )
        logger.info("SMTP not configured; case-closed email for %s logged but not sent", ticket_id)


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


def send_new_ticket_queue_notification(
    ticket_id: str,
    subject: str,
    submitter_name: str,
    queue_name: str,
    category_name: str,
    recipients: list[tuple[str, str]],
) -> None:
    """Notify all queue/mailer members when a new ticket is created.

    Args:
        ticket_id: The ticket ID
        subject: The ticket subject
        submitter_name: Who submitted the ticket
        queue_name: The queue the ticket was routed to
        category_name: The AI-classified category
        recipients: List of (display_name, email) tuples for queue members
    """
    if not recipients:
        logger.info("No recipients to notify for new ticket %s in queue %s", ticket_id, queue_name)
        return

    import html as html_mod
    safe_ticket_id = html_mod.escape(ticket_id)
    safe_subject = html_mod.escape(subject)
    safe_submitter = html_mod.escape(submitter_name)
    safe_queue = html_mod.escape(queue_name)
    safe_category = html_mod.escape(category_name)

    email_subject = f"[{ticket_id}] New ticket assigned to {queue_name}"

    for display_name, email_addr in recipients:
        safe_name = html_mod.escape(display_name)

        inner_html = f"""\
<h2 style="margin:0 0 12px;color:#003E7E;font-size:20px;">New Ticket Alert</h2>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  Hi {safe_name},
</p>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  A new support ticket has been submitted and routed to the <strong>{safe_queue}</strong> queue.
</p>
<table width="100%" style="margin:20px 0;background:#f7f8fa;border-radius:10px;padding:16px;">
  <tr>
    <td style="padding:4px 0;">
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;">Ticket ID</span><br>
      <strong style="font-size:16px;color:#003E7E;font-family:monospace;">{safe_ticket_id}</strong>
    </td>
  </tr>
  <tr>
    <td style="padding:4px 0;">
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;">Subject</span><br>
      <span style="font-size:14px;color:#1e293b;">{safe_subject}</span>
    </td>
  </tr>
  <tr>
    <td style="padding:4px 0;">
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;">Submitted By</span><br>
      <span style="font-size:14px;color:#1e293b;">{safe_submitter}</span>
    </td>
  </tr>
  <tr>
    <td style="padding:4px 0;">
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;">Category</span><br>
      <span style="font-size:14px;color:#1e293b;">{safe_category}</span>
    </td>
  </tr>
</table>
<p style="color:#64748b;font-size:13px;line-height:1.7;">
  Please log in to the HOPE AI portal to review and take action on this ticket.
</p>"""

        text_body = (
            f"Hi {display_name},\n\n"
            f"A new support ticket has been submitted and routed to the {queue_name} queue.\n\n"
            f"Ticket ID: {ticket_id}\n"
            f"Subject: {subject}\n"
            f"Submitted By: {submitter_name}\n"
            f"Category: {category_name}\n\n"
            f"Please log in to the HOPE AI portal to review this ticket.\n\n"
            f"-- Operation HOPE"
        )

        html_body = _brand_html(inner_html)

        if _is_smtp_configured():
            try:
                _send_email(email_addr, email_subject, html_body, text_body)
                _record_notification(ticket_id, email_addr, email_subject, text_body[:200], status="sent")
                logger.info("Queue notification sent for %s to %s", ticket_id, email_addr)
            except Exception as exc:
                _record_notification(
                    ticket_id, email_addr, email_subject, text_body[:200],
                    status="failed", error_message=str(exc),
                )
                logger.warning("Failed to send queue notification for %s to %s: %s", ticket_id, email_addr, exc)
        else:
            _record_notification(
                ticket_id, email_addr, email_subject, text_body[:200],
                status="skipped_no_smtp",
            )
            logger.info("SMTP not configured; queue notification for %s to %s logged but not sent", ticket_id, email_addr)


def send_escalation_notification(
    ticket_id: str,
    subject: str,
    queue_name: str,
    hours_open: float,
    recipients: list[tuple[str, str]],
) -> None:
    """Send escalation email to queue mailer list when a ticket has been unresolved too long.

    Args:
        ticket_id: The ticket ID
        subject: The ticket subject
        queue_name: The queue the ticket belongs to
        hours_open: How many hours the ticket has been open
        recipients: List of (display_name, email) tuples for queue members
    """
    if not recipients:
        logger.info("No recipients for escalation notification for %s", ticket_id)
        return

    import html as html_mod
    safe_ticket_id = html_mod.escape(ticket_id)
    safe_subject = html_mod.escape(subject)
    safe_queue = html_mod.escape(queue_name)
    hours_str = f"{hours_open:.1f}"

    email_subject = f"⚠️ [{ticket_id}] ESCALATION: Ticket unresolved for {hours_str} hours"

    for display_name, email_addr in recipients:
        safe_name = html_mod.escape(display_name)

        inner_html = f"""\
<h2 style="margin:0 0 12px;color:#dc2626;font-size:20px;">⚠️ Escalation Alert</h2>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  Hi {safe_name},
</p>
<p style="color:#1e293b;font-size:14px;line-height:1.7;">
  The following ticket in the <strong>{safe_queue}</strong> queue has been unresolved for
  <strong>{hours_str} hours</strong> and requires immediate attention.
</p>
<table width="100%" style="margin:20px 0;background:#fef2f2;border-left:4px solid #dc2626;border-radius:6px;padding:16px;">
  <tr>
    <td>
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#dc2626;">Ticket ID</span><br>
      <strong style="font-size:16px;color:#003E7E;font-family:monospace;">{safe_ticket_id}</strong>
    </td>
  </tr>
  <tr>
    <td style="padding-top:8px;">
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#dc2626;">Subject</span><br>
      <span style="font-size:14px;color:#1e293b;">{safe_subject}</span>
    </td>
  </tr>
</table>
<p style="color:#64748b;font-size:13px;line-height:1.7;">
  Please log in to the HOPE AI portal and resolve this ticket as soon as possible.
</p>"""

        text_body = (
            f"Hi {display_name},\n\n"
            f"ESCALATION ALERT: Ticket {ticket_id} in the {queue_name} queue has been "
            f"unresolved for {hours_str} hours.\n\n"
            f"Subject: {subject}\n\n"
            f"Please log in and resolve this ticket immediately.\n\n"
            f"-- Operation HOPE"
        )

        html_body = _brand_html(inner_html)

        if _is_smtp_configured():
            try:
                _send_email(email_addr, email_subject, html_body, text_body)
                _record_notification(ticket_id, email_addr, email_subject, text_body[:200], status="sent")
                logger.info("Escalation notification sent for %s to %s", ticket_id, email_addr)
            except Exception as exc:
                _record_notification(
                    ticket_id, email_addr, email_subject, text_body[:200],
                    status="failed", error_message=str(exc),
                )
                logger.warning("Failed to send escalation notification for %s to %s: %s", ticket_id, email_addr, exc)
        else:
            _record_notification(
                ticket_id, email_addr, email_subject, text_body[:200],
                status="skipped_no_smtp",
            )
            logger.info("SMTP not configured; escalation notification for %s to %s logged but not sent", ticket_id, email_addr)
