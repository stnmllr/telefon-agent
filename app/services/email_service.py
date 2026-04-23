"""
Email Service — SendGrid Integration
Sendet Benachrichtigungs-E-Mails bei Anruf-Weiterleitungen.
"""

import os
import logging
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.services.rag_service import summarize_conversation

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "ki-agent@sopra-system.com")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Sofia – Assistent Stephan Müller")

CATEGORY_EMAILS = {
    "erp":        ("ERP-Support",   "erp-support@sopra-system.com"),
    "evs":        ("EVS-Support",   "evs-support@sopra-system.com"),
    "hr":         ("HR-Support",    "hr-support@sopra-system.com"),
    "it":         ("IT-Support",    "it-support@sopra-system.com"),
    "verwaltung": ("Verwaltung",    "Stephan.Mueller@sopra-system.com"),
    "nachricht":  ("Stephan Müller", "Stephan.Mueller@sopra-system.com"),
}


async def send_routing_email(
    category: str,
    caller_number: str,
    user_question: str,
    conversation_history: list[dict],
    call_sid: str = "",
    caller_contact: dict | None = None,
    recipient_override: str | None = None,
    team_name_override: str | None = None,
) -> bool:
    """
    Sendet eine Benachrichtigungs-E-Mail nach Anruf-Weiterleitung.

    Args:
        category:             Routing-Kategorie (erp, evs, hr, it, verwaltung, phonebook)
        caller_number:        Twilio From-Nummer des Anrufers
        user_question:        Originale Frage des Anrufers
        conversation_history: Liste von {"role": "user"|"assistant", "content": "..."}
        call_sid:             Twilio Call-SID (für Referenz)
        recipient_override:   Direkter Empfänger (z.B. Telefonbuch-Person)
        team_name_override:   Anrede des Empfängers (z.B. "Müller, Stephan")

    Returns:
        True bei Erfolg, False bei Fehler
    """
    if not SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY nicht gesetzt — E-Mail wird nicht gesendet")
        return False

    if recipient_override:
        recipient_email = recipient_override
        team_name = team_name_override or "Empfänger"
    elif category not in CATEGORY_EMAILS:
        logger.warning("Unbekannte Kategorie für E-Mail: %s", category)
        return False
    else:
        team_name, recipient_email = CATEGORY_EMAILS[category]
    now = datetime.now().strftime("%d.%m.%Y %H:%M Uhr")
    contact = caller_contact or {}
    extracted_phone = contact.get("phone", "")
    digits = "".join(c for c in extracted_phone if c.isdigit())
    display_phone = extracted_phone if len(digits) >= 6 else f"{caller_number} (Anrufer-Nummer)"

    summary = await summarize_conversation(conversation_history)

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
Rückruf:    {display_phone}
Zeitpunkt:  {now}
Kategorie:  {category_label}
Call-SID:   {call_sid or '—'}

GESPRÄCHSZUSAMMENFASSUNG
─────────────────────────────────────────
{summary}

─────────────────────────────────────────
Bitte nehmen Sie bei Bedarf Kontakt mit dem Anrufer auf.

Mit freundlichen Grüßen
KI-Telefon-Agent — SOPRA System GmbH
"""

    html_body = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:0 auto">

<div style="background:#003366;color:white;padding:16px 24px;border-radius:6px 6px 0 0">
  <h2 style="margin:0;font-size:18px">Sofia – Anruf-Weiterleitung</h2>
  <p style="margin:4px 0 0;font-size:13px;opacity:0.8">Digitaler Assistent von Stephan Müller</p>
</div>

<div style="border:1px solid #ddd;border-top:none;padding:20px 24px;border-radius:0 0 6px 6px">

  <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
    <tr><td style="padding:6px 0;color:#888;width:120px">Anrufer</td>
        <td style="padding:6px 0;font-weight:bold">{caller_number}</td></tr>
    <tr><td style="padding:6px 0;color:#888">Rückruf</td>
        <td style="padding:6px 0">{display_phone}</td></tr>
    <tr><td style="padding:6px 0;color:#888">Zeitpunkt</td>
        <td style="padding:6px 0">{now}</td></tr>
    <tr><td style="padding:6px 0;color:#888">Kategorie</td>
        <td style="padding:6px 0"><span style="background:#e8f0fe;color:#1a56db;padding:2px 10px;border-radius:12px;font-size:13px">{category_label}</span></td></tr>
    <tr><td style="padding:6px 0;color:#888">Call-SID</td>
        <td style="padding:6px 0;font-size:12px;color:#999">{call_sid or '—'}</td></tr>
  </table>

  <h3 style="font-size:14px;color:#555;margin-bottom:8px">Gesprächszusammenfassung</h3>
  <p style="font-size:14px;line-height:1.6;background:#f9f9f9;padding:12px 16px;border-radius:4px;border:1px solid #eee">{summary}</p>

  <p style="margin-top:24px;font-size:13px;color:#888">
    Diese E-Mail wurde automatisch von Sofia, dem digitalen Assistenten von Stephan Müller, generiert.
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
