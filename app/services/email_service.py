"""
Email Service — SendGrid Integration
Sendet Benachrichtigungs-E-Mails bei Anruf-Weiterleitungen.
"""

import os
import logging
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "ki-agent@sopra-system.com")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "KI-Agent SOPRA System")

CATEGORY_EMAILS = {
    "erp":        ("ERP-Support",   "erp-support@sopra-system.com"),
    "evs":        ("EVS-Support",   "evs-support@sopra-system.com"),
    "hr":         ("HR-Support",    "hr-support@sopra-system.com"),
    "it":         ("IT-Support",    "it-support@sopra-system.com"),
    "verwaltung": ("Verwaltung",    "Stephan.Mueller@sopra-system.com"),
}


def send_routing_email(
    category: str,
    caller_number: str,
    user_question: str,
    conversation_history: list[dict],
    call_sid: str = "",
    caller_contact: dict | None = None,
) -> bool:
    """
    Sendet eine Benachrichtigungs-E-Mail nach Anruf-Weiterleitung.

    Args:
        category:             Routing-Kategorie (erp, evs, hr, it, verwaltung)
        caller_number:        Twilio From-Nummer des Anrufers
        user_question:        Originale Frage des Anrufers
        conversation_history: Liste von {"role": "user"|"assistant", "content": "..."}
        call_sid:             Twilio Call-SID (für Referenz)

    Returns:
        True bei Erfolg, False bei Fehler
    """
    if not SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY nicht gesetzt — E-Mail wird nicht gesendet")
        return False

    if category not in CATEGORY_EMAILS:
        logger.warning("Unbekannte Kategorie für E-Mail: %s", category)
        return False

    team_name, recipient_email = CATEGORY_EMAILS[category]
    now = datetime.now().strftime("%d.%m.%Y %H:%M Uhr")
    contact = caller_contact or {}
    contact_phone = contact.get("phone") or "nicht angegeben"
    contact_email = contact.get("email") or "nicht angegeben"

    protocol_lines = []
    for i, turn in enumerate(conversation_history, start=1):
        role = "Anrufer" if turn.get("role") == "user" else "Agent  "
        content = turn.get("content", "").strip()
        if content:
            protocol_lines.append(f"[{i}] {role}: {content}")

    protocol_text = "\n".join(protocol_lines) if protocol_lines else "(kein Protokoll verfügbar)"

    category_label = {
        "erp":        "ERP-Anfrage",
        "evs":        "EVS-Anfrage",
        "hr":         "HR-Anfrage",
        "it":         "IT-Anfrage",
        "verwaltung": "Verwaltungs-Anfrage",
    }.get(category, "Anfrage")

    subject = f"[KI-Agent] Anruf von {caller_number} — {category_label}"

    body = f"""Hallo {team_name},

der KI-Telefon-Agent hat einen Anruf weitergeleitet, der Ihr Team betrifft.

─────────────────────────────────────────
ANRUF-DETAILS
─────────────────────────────────────────
Anrufer:    {caller_number}
Rückruf:    {contact_phone}
E-Mail:     {contact_email}
Zeitpunkt:  {now}
Kategorie:  {category_label}
Call-SID:   {call_sid or '—'}

ANLIEGEN DES ANRUFERS:
{user_question}

─────────────────────────────────────────
GESPRÄCHSPROTOKOLL
─────────────────────────────────────────
{protocol_text}

─────────────────────────────────────────
Bitte nehmen Sie bei Bedarf Kontakt mit dem Anrufer auf.

Mit freundlichen Grüßen
KI-Telefon-Agent — SOPRA System GmbH
"""

    protocol_html = "".join(
        f"<tr style='background:{'#f9f9f9' if i % 2 == 0 else '#ffffff'}'>"
        f"<td style='padding:6px 12px;color:#888;font-size:12px;white-space:nowrap'>[{i}]</td>"
        f"<td style='padding:6px 12px;font-weight:bold;white-space:nowrap'>{'Anrufer' if t.get('role') == 'user' else 'Agent'}</td>"
        f"<td style='padding:6px 12px'>{t.get('content', '').strip()}</td>"
        f"</tr>"
        for i, t in enumerate(conversation_history, start=1)
        if t.get("content", "").strip()
    )

    html_body = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:0 auto">

<div style="background:#003366;color:white;padding:16px 24px;border-radius:6px 6px 0 0">
  <h2 style="margin:0;font-size:18px">KI-Telefon-Agent — Anruf-Weiterleitung</h2>
  <p style="margin:4px 0 0;font-size:13px;opacity:0.8">SOPRA System GmbH</p>
</div>

<div style="border:1px solid #ddd;border-top:none;padding:20px 24px;border-radius:0 0 6px 6px">

  <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
    <tr><td style="padding:6px 0;color:#888;width:120px">Anrufer</td>
        <td style="padding:6px 0;font-weight:bold">{caller_number}</td></tr>
    <tr><td style="padding:6px 0;color:#888">Rückruf</td>
        <td style="padding:6px 0">{contact_phone}</td></tr>
    <tr><td style="padding:6px 0;color:#888">E-Mail</td>
        <td style="padding:6px 0">{contact_email}</td></tr>
    <tr><td style="padding:6px 0;color:#888">Zeitpunkt</td>
        <td style="padding:6px 0">{now}</td></tr>
    <tr><td style="padding:6px 0;color:#888">Kategorie</td>
        <td style="padding:6px 0"><span style="background:#e8f0fe;color:#1a56db;padding:2px 10px;border-radius:12px;font-size:13px">{category_label}</span></td></tr>
    <tr><td style="padding:6px 0;color:#888">Call-SID</td>
        <td style="padding:6px 0;font-size:12px;color:#999">{call_sid or '—'}</td></tr>
  </table>

  <div style="background:#f5f5f5;border-left:4px solid #003366;padding:12px 16px;margin-bottom:20px;border-radius:0 4px 4px 0">
    <p style="margin:0;font-size:13px;color:#888">Anliegen des Anrufers:</p>
    <p style="margin:6px 0 0;font-size:15px">{user_question}</p>
  </div>

  <h3 style="font-size:14px;color:#555;margin-bottom:8px">Gesprächsprotokoll</h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px;border:1px solid #eee;border-radius:4px">
    {protocol_html if protocol_html else '<tr><td style="padding:12px;color:#999">Kein Protokoll verfügbar</td></tr>'}
  </table>

  <p style="margin-top:24px;font-size:13px;color:#888">
    Diese E-Mail wurde automatisch vom KI-Telefon-Agenten der SOPRA System GmbH generiert.
  </p>
</div>
</body></html>
"""

    try:
        message = Mail(
            from_email=(EMAIL_FROM, EMAIL_FROM_NAME),
            to_emails=recipient_email,
            subject=subject,
            plain_text_content=body,
            html_content=html_body,
        )

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        if response.status_code in (200, 202):
            logger.info("E-Mail gesendet an %s (Status %d)", recipient_email, response.status_code)
            return True
        else:
            logger.error("SendGrid Fehler: Status %d", response.status_code)
            return False

    except Exception as e:
        logger.error("E-Mail senden fehlgeschlagen: %s", e)
        return False
