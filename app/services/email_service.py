"""
Email Service — Resend Integration
Sendet Benachrichtigungs-E-Mails bei Anruf-Weiterleitungen.

Versand über die Resend-HTTP-API (raw httpx, kein SDK). Der API-Key wird vor
dem Header-Bau defensiv ge-strippt (CR/LF/Whitespace), damit ein Secret mit
Trailing-Newline den Authorization-Header nicht zerstört. Im Fehlerfall werden
ausschließlich Statuscode + Resend-Fehlertext geloggt — niemals der Key oder
der Authorization-Header.
"""

import os
import html
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_URL = "https://api.resend.com/emails"
# Absender muss eine in Resend verifizierte Domain sein. Default = Resend-Sandbox
# für lokale Tests; produktiv via EMAIL_FROM (z.B. sofia@stnmllr.com) gesetzt.
EMAIL_FROM = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Sofia – Assistent Stephan Müller")

CATEGORY_EMAILS = {
    "erp":        ("ERP-Support",   "erp-support@sopra-system.com"),
    "evs":        ("EVS-Support",   "evs-support@sopra-system.com"),
    "hr":         ("HR-Support",    "hr-support@sopra-system.com"),
    "it":         ("IT-Support",    "it-support@sopra-system.com"),
    "verwaltung": ("Verwaltung",    "Stephan.Mueller@sopra-system.com"),
    "nachricht":  ("Stephan Müller", "Stephan.Mueller@sopra-system.com"),
}


def _client() -> httpx.AsyncClient:
    """Test-Seam: in Tests durch einen Client mit MockTransport ersetzt."""
    return httpx.AsyncClient(timeout=15.0)


async def _resend_send(
    recipient_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    cc: list[str] | None = None,
) -> tuple[bool, str]:
    """Versendet eine E-Mail über die Resend-API. Returns (ok, message_id)."""
    key = RESEND_API_KEY.strip()
    if not key:
        logger.warning("RESEND_API_KEY nicht gesetzt — E-Mail wird nicht gesendet")
        return False, ""

    payload = {
        "from": f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>",
        "to": [recipient_email],
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }
    if cc:
        payload["cc"] = cc
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    try:
        async with _client() as c:
            r = await c.post(RESEND_URL, headers=headers, json=payload)
    except Exception as e:
        # NICHT str(e)/e loggen — könnte den Authorization-Header inkl. Key enthalten.
        logger.error("Resend-Request fehlgeschlagen: %s", type(e).__name__)
        return False, ""

    if r.status_code in (200, 201):
        try:
            message_id = (r.json() or {}).get("id", "")
        except Exception:
            message_id = ""
        logger.info("E-Mail via Resend gesendet an %s (Status %d)",
                    recipient_email, r.status_code)
        return True, message_id

    # r.text = Resend-Fehler-JSON (enthält den Key NICHT) → loggen ist sicher.
    logger.error("Resend-Fehler: Status %d — %s", r.status_code, r.text[:300])
    return False, ""


async def send_routing_email(
    category: str,
    caller_number: str,
    user_question: str,
    conversation_history: list[dict],
    call_sid: str = "",
    caller_contact: dict | None = None,
    recipient_override: str | None = None,
    team_name_override: str | None = None,
    caller_name: str = "",
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
    if recipient_override:
        recipient_email = recipient_override
        team_name = team_name_override or "Empfänger"
    elif category not in CATEGORY_EMAILS:
        logger.warning("Unbekannte Kategorie für E-Mail: %s", category)
        return False
    else:
        team_name, recipient_email = CATEGORY_EMAILS[category]
    is_callback = user_question.startswith("[RÜCKRUF ERWÜNSCHT]")
    now = datetime.now().strftime("%d.%m.%Y %H:%M Uhr")
    contact = caller_contact or {}
    extracted_phone = contact.get("phone", "")
    digits = "".join(c for c in extracted_phone if c.isdigit())
    display_phone = extracted_phone if len(digits) >= 6 else f"{caller_number} (Anrufer-Nummer)"

    from app.services.rag_service import summarize_conversation
    summary = await summarize_conversation(conversation_history)

    category_label = {
        "erp":        "ERP-Anfrage",
        "evs":        "EVS-Anfrage",
        "hr":         "HR-Anfrage",
        "it":         "IT-Anfrage",
        "verwaltung": "Verwaltungs-Anfrage",
    }.get(category, "Anfrage")

    if is_callback:
        subject = f"[KI-Agent] Rückrufbitte von {caller_number} — {category_label}"
    else:
        subject = f"[KI-Agent] Anruf von {caller_number} — {category_label}"

    callback_note = "\n*** RÜCKRUF ERBETEN — bitte den Anrufer zurückrufen ***\n" if is_callback else ""
    name_line = f"Name:       {caller_name}\n" if caller_name else ""
    body = f"""Hallo {team_name},
{callback_note}
der KI-Telefon-Agent hat einen Anruf weitergeleitet, der Ihr Team betrifft.

─────────────────────────────────────────
ANRUF-DETAILS
─────────────────────────────────────────
Anrufer:    {caller_number}
{name_line}Rückruf:    {display_phone}
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

    callback_badge = (
        '<div style="background:#c0392b;color:white;padding:10px 24px;font-weight:bold;font-size:14px">'
        '&#128222; RÜCKRUF ERBETEN — bitte den Anrufer zurückrufen'
        '</div>'
    ) if is_callback else ""
    name_row = (
        f'<tr><td style="padding:6px 0;color:#888;width:120px">Anrufer-Name</td>'
        f'<td style="padding:6px 0;font-weight:bold">{caller_name}</td></tr>'
    ) if caller_name else ""

    html_body = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:0 auto">

<div style="background:#003366;color:white;padding:16px 24px;border-radius:6px 6px 0 0">
  <h2 style="margin:0;font-size:18px">Sofia – Anruf-Weiterleitung</h2>
  <p style="margin:4px 0 0;font-size:13px;opacity:0.8">Digitaler Assistent von Stephan Müller</p>
</div>
{callback_badge}

<div style="border:1px solid #ddd;border-top:none;padding:20px 24px;border-radius:0 0 6px 6px">

  <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
    <tr><td style="padding:6px 0;color:#888;width:120px">Anrufer</td>
        <td style="padding:6px 0;font-weight:bold">{caller_number}</td></tr>
    {name_row}
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

    ok, _message_id = await _resend_send(recipient_email, subject, html_body, body)
    return ok


async def send_email_raw(
    recipient_email: str,
    subject: str,
    plain_body: str,
    ticket_ref: str | None = None,
    callback: bool = False,
    header_rows: list[tuple[str, str]] | None = None,
    cc: list[str] | None = None,
) -> tuple[bool, str]:
    """Versendet eine vom Agenten formulierte E-Mail direkt (ohne RAG-Summary).

    header_rows: optionaler strukturierter Kopfblock (Label, Wert), der VOR dem
    Body in Text und HTML gerendert wird — z.B. Ticket-ID/Kategorie/Anrufer bei
    create_ticket. Ohne header_rows bleibt die Mail schlank (Personen-Mail).

    Returns (ok, message_id).
    """
    full_subject = f"[{ticket_ref}] {subject}" if ticket_ref else subject
    callback_note = "\n*** RÜCKRUF ERBETEN ***\n" if callback else ""

    plain_header, html_header = "", ""
    if header_rows:
        plain_header = "\n".join(f"{label}: {value}" for label, value in header_rows) \
            + "\n" + "─" * 42 + "\n\n"
        # Nutzer-/LLM-Werte werden im HTML escaped (kein Markup-Bruch/-Injection);
        # der Plain-Text-Teil oben bleibt bewusst unescaped.
        rows_html = "".join(
            f'<tr><td style="padding:4px 16px 4px 0;color:#888;white-space:nowrap">{html.escape(str(label))}</td>'
            f'<td style="padding:4px 0;font-weight:bold">{html.escape(str(value))}</td></tr>'
            for label, value in header_rows
        )
        html_header = (
            '<table style="border-collapse:collapse;margin-bottom:16px;'
            f'border-bottom:1px solid #eee;padding-bottom:8px">{rows_html}</table>'
        )

    plain = f"{callback_note}{plain_header}{plain_body}\n\n— Sofia, digitaler Assistent von Stephan Müller"
    html_out = (
        '<html><body style="font-family:Arial,sans-serif;color:#333">'
        + ('<div style="background:#c0392b;color:#fff;padding:8px 16px;font-weight:bold">'
           '&#128222; RÜCKRUF ERBETEN</div>' if callback else "")
        + f'<div style="padding:16px">{html_header}'
        + f'<div style="white-space:pre-wrap">{html.escape(plain_body)}</div></div>'
        '<p style="font-size:12px;color:#888;padding:0 16px">'
        'Automatisch von Sofia generiert.</p></body></html>'
    )
    return await _resend_send(recipient_email, full_subject, html_out, plain, cc=cc)
