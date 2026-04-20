# ============================================================
# app/routers/call_router.py
# NEUE, KOMPLETT ÜBERARBEITETE VERSION (2026-03)
# Twilio Webhooks:
#   POST /call/incoming   – Start eines Anrufs → Begrüßung, STT aktivieren
#   POST /call/transcribe – Benutzeräußerung → RAG/LLM → Antwort per TTS
# ============================================================

import logging
from fastapi import APIRouter, Form
from fastapi.responses import Response
from google.cloud import firestore

from app.services.rag_service import answer_question, extract_contact_data
from app.services.memory_service import (
    get_history,
    save_pending_contact,
    get_pending_contact,
    update_pending_contact,
    get_and_delete_pending_contact,
)
from app.services.email_service import send_routing_email
from app.config import settings
from app.utils.latency_logger import LatencyLogger
from app.utils.twiml_builder import (
    build_welcome_twiml,
    build_answer_twiml,
    build_fallback_twiml,
    build_farewell_twiml,
)

db = firestore.Client()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/call")

_ERP_KEYWORDS = {"erp", "warenwirtschaft", "auftrag", "lieferschein", "artikel",
                  "kulimi", "kundenverwaltung", "produktion", "inventur", "lager"}
_EVS_KEYWORDS = {"evs", "zeiterfassung"}
_HR_KEYWORDS = {"hr", "personal", "urlaub", "gehalt", "arbeitsvertrag", "krankmeldung"}
_IT_KEYWORDS = {"computer", "netzwerk", "drucker", "internet", "it-support",
                 "software", "login", "passwort", "bildschirm", "laptop", "server"}
_VERWALTUNG_KEYWORDS = {"vertrag", "rechnung", "preis", "angebot", "wartung",
                         "lizenz", "abrechnung", "verwaltung"}


def _detect_routing_category(text: str) -> str | None:
    lower = text.lower()
    if any(kw in lower for kw in _ERP_KEYWORDS):
        return "erp"
    if any(kw in lower for kw in _EVS_KEYWORDS):
        return "evs"
    if any(kw in lower for kw in _HR_KEYWORDS):
        return "hr"
    if any(kw in lower for kw in _IT_KEYWORDS):
        return "it"
    if any(kw in lower for kw in _VERWALTUNG_KEYWORDS):
        return "verwaltung"
    return None


_CATEGORY_LABELS = {
    "erp":        "ERP-Themen",
    "evs":        "Zeiterfassung",
    "hr":         "Personal-Themen",
    "it":         "IT-Support",
    "verwaltung": "Verwaltungsthemen",
}

_CATEGORY_EXTENSIONS = {
    "erp":        ("ERP-Support",  "eins eins zwei"),
    "evs":        ("EVS-Support",  "zwei null"),
    "hr":         ("HR-Support",   "eins eins sechs"),
    "it":         ("IT-Support",   "eins eins fünf"),
    "verwaltung": ("Verwaltung",   "zwei sechs"),
}

_REFUSAL_KEYWORDS = {
    "nein", "nö", "nicht nötig", "lieber nicht",
    "ich ruf selbst", "kein bedarf", "nein danke", "danke nein",
}


def _is_refusal(text: str) -> bool:
    lower = text.strip().lower()
    return any(kw in lower for kw in _REFUSAL_KEYWORDS)


def _build_anliegen_request_twiml(category: str) -> str:
    label = _CATEGORY_LABELS.get(category, "Ihr Anliegen")
    msg = (
        f"Ich verstehe, es geht um {label}. "
        "Können Sie mir Ihr Anliegen kurz schildern, damit ich es weiterleiten kann?"
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="/call/transcribe" method="POST"
          language="de-DE" speechTimeout="7">
    <Say language="de-DE" voice="Google.de-DE-Neural2-F">{msg}</Say>
  </Gather>
  <Redirect method="POST">/call/transcribe</Redirect>
</Response>"""


def _build_contact_offer_twiml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="/call/process_contact" method="POST"
          language="de-DE" speechTimeout="7">
    <Say language="de-DE" voice="Google.de-DE-Neural2-F">Darf ich Ihre Rückruf-Nummer und E-Mail-Adresse notieren, damit wir uns bei Ihnen melden?</Say>
  </Gather>
  <Redirect method="POST">/call/process_contact</Redirect>
</Response>"""


FAREWELL_KEYWORDS = [
    "nein danke",
    "danke das war’s",
    "tschuess",
    "tschüss",
    "auf wiederhören",
    "auf wieder hoeren",
    "beenden",
    "schluss",
    "ende",
]


# ============================================================
# 1) Eingang eines Anrufs
# ============================================================
@router.post("/incoming")
async def incoming_call():
    """
    Wird von Twilio beim Start eines Anrufs ausgelöst.
    Erstellt ein TwiML, das sofort Text-to-Speech abspielt und
    anschließend Speech-to-Text aktiviert.
    """

    logger.info("[INCOMING] Neuer Anruf gestartet.")

    twiml = build_welcome_twiml(
        message=(
            "Hallo, mein Name ist Sofia, ich bin der digitale Assistent von Stephan Müller. "
            "Was kann ich für Sie tun?"
        ),
        transcribe_url="/call/transcribe",
    )

    return Response(content=twiml, media_type="application/xml")


# ============================================================
# 2) Twilio Speech-to-Text liefert ein Ergebnis
# ============================================================
@router.post("/transcribe")
async def transcribe(
    SpeechResult: str = Form(default=""),
    Confidence: float = Form(default=0.0),
    CallSid: str = Form(default=""),
    From: str = Form(default=""),
):
    """
    Twilio liefert hier das STT-Ergebnis. Diese Funktion entscheidet:
      - Wiederholen? (schlechte Confidence)
      - Verabschiedung?
      - Normale Anfrage → RAG/LLM antwortet
    """

    logger.info(
        "[TRANSCRIBE] CallSid=%s | Text='%s' | Confidence=%.2f",
        CallSid,
        SpeechResult,
        Confidence,
    )
    lat_logger = LatencyLogger(CallSid, flow="transcribe") if settings.latency_logging else None
    if lat_logger:
        lat_logger.mark("stt_done")

    # --------------------------------------------------------
    # A) Qualitätsprüfung STT
    # --------------------------------------------------------
    if not SpeechResult or Confidence < 0.40:
        logger.warning(
            "[TRANSCRIBE] Schlechte STT-Qualität oder leere Eingabe."
        )

        twiml = build_fallback_twiml(
            message="Ich habe Sie leider nicht gut verstanden. "
                    "Bitte wiederholen Sie Ihre Frage.",
            transcribe_url="/call/transcribe",
        )
        return Response(content=twiml, media_type="application/xml")

    user_text = SpeechResult.strip().lower()

    # --------------------------------------------------------
    # B) Verabschiedung erkennen
    # --------------------------------------------------------
    if any(keyword in user_text for keyword in FAREWELL_KEYWORDS):
        logger.info("[TRANSCRIBE] Verabschiedung erkannt. CallSid=%s", CallSid)

        twiml = build_farewell_twiml()
        return Response(content=twiml, media_type="application/xml")

    # --------------------------------------------------------
    # C) SpeechResult in Firestore zwischenspeichern → Redirect
    # --------------------------------------------------------
    try:
        db.collection("pending").document(CallSid).set({
            "speech_result": SpeechResult,
            "from_number": From,
        })
    except Exception as exc:
        logger.exception("[TRANSCRIBE] Firestore-Speichern fehlgeschlagen: %s", exc)

    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Redirect method="POST">/call/process</Redirect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


# ============================================================
# 3) LLM-Verarbeitung nach Zwischenantwort
# ============================================================
@router.post("/process")
async def process(
    CallSid: str = Form(default=""),
    SpeechResult: str = Form(default=""),
    From: str = Form(default=""),
):
    """
    Liest SpeechResult aus Firestore, ruft RAG/LLM auf und
    gibt die eigentliche Antwort zurück.
    Fallback: Falls kein Firestore-Eintrag existiert, wird ein direkt
    übergebener SpeechResult-Parameter verwendet (nützlich für Tests).
    """

    logger.info("[PROCESS] CallSid=%s", CallSid)
    logger.info("[PROCESS] SpeechResult-Parameter direkt=%s", repr(SpeechResult))
    lat_logger = LatencyLogger(CallSid, flow="process") if settings.latency_logging else None
    if lat_logger:
        lat_logger.mark("process_start")

    # --------------------------------------------------------
    # A) SpeechResult aus Firestore laden und löschen
    # --------------------------------------------------------
    speech_result = ""
    from_number = From
    try:
        ref = db.collection("pending").document(CallSid)
        doc = ref.get()
        if doc.exists:
            data = doc.to_dict()
            speech_result = data.get("speech_result", "")
            from_number = data.get("from_number", From)
            ref.delete()
        else:
            logger.warning("[PROCESS] Kein pending-Eintrag für CallSid=%s", CallSid)
            if SpeechResult:
                logger.info("[PROCESS] Nutze direkt übergebenen SpeechResult-Parameter (Test-Fallback).")
                speech_result = SpeechResult
    except Exception as exc:
        logger.exception("[PROCESS] Firestore-Lesen fehlgeschlagen: %s", exc)
    if lat_logger:
        lat_logger.mark("firestore_read")

    if not speech_result:
        twiml = build_fallback_twiml(
            message="Entschuldigung, ich konnte Ihre Frage nicht abrufen. Bitte wiederholen Sie.",
            transcribe_url="/call/transcribe",
        )
        return Response(content=twiml, media_type="application/xml")

    # --------------------------------------------------------
    # B) Routing-Flow (stage-basiert, vor RAG/LLM)
    # --------------------------------------------------------
    pending = get_pending_contact(CallSid)

    if pending and pending.get("stage") == "anliegen":
        # Schritt 2: Anliegen erhalten → Kontaktdaten anbieten
        logger.info("[PROCESS] Stage=anliegen, speichere Anliegen und biete Kontaktdaten an. CallSid=%s", CallSid)
        try:
            update_pending_contact(CallSid, anliegen=speech_result, stage="kontakt")
        except Exception as exc:
            logger.warning("[PROCESS] update_pending_contact fehlgeschlagen: %s", exc)
        if lat_logger:
            lat_logger.mark("routing_stage2")
            lat_logger.finish()
        return Response(content=_build_contact_offer_twiml(), media_type="application/xml")

    # Schritt 1: Neue Kategorie erkennen
    category = _detect_routing_category(speech_result)
    if category:
        logger.info("[PROCESS] Kategorie erkannt: %s — frage Anliegen ab. CallSid=%s", category, CallSid)
        try:
            save_pending_contact(CallSid, category, speech_result, from_number, stage="anliegen")
        except Exception as exc:
            logger.warning("[PROCESS] save_pending_contact fehlgeschlagen: %s", exc)
        if lat_logger:
            lat_logger.mark("routing_stage1")
            lat_logger.finish()
        return Response(content=_build_anliegen_request_twiml(category), media_type="application/xml")

    logger.info("[PROCESS] Kein Routing-Match, gehe zu RAG")

    # --------------------------------------------------------
    # C) RAG + LLM
    # --------------------------------------------------------
    try:
        answer = await answer_question(
            question=speech_result,
            call_sid=CallSid,
            lat_logger=lat_logger,
        )
    except Exception as exc:
        logger.exception("[PROCESS] Fehler in answer_question(): %s", exc)

        twiml = build_fallback_twiml(
            message=(
                "Entschuldigung, das hat gerade nicht geklappt. "
                "Bitte formulieren Sie Ihre Frage noch einmal."
            ),
            transcribe_url="/call/transcribe",
        )
        return Response(content=twiml, media_type="application/xml")

    # --------------------------------------------------------
    # D) Antwort als TwiML zurückgeben
    # --------------------------------------------------------
    twiml = build_answer_twiml(
        answer=answer,
        transcribe_url="/call/transcribe",
    )

    if lat_logger:
        lat_logger.mark("tts_ready")
        lat_logger.finish()

    return Response(content=twiml, media_type="application/xml")


# ============================================================
# 4) Kontaktdaten entgegennehmen und E-Mail senden
# ============================================================
@router.post("/process_contact")
async def process_contact(
    CallSid: str = Form(default=""),
    SpeechResult: str = Form(default=""),
):
    logger.info("[PROCESS_CONTACT] CallSid=%s | SpeechResult='%s'", CallSid, SpeechResult)

    # A) Routing-Kontext aus Firestore laden
    pending = get_and_delete_pending_contact(CallSid)
    if not pending:
        logger.warning("[PROCESS_CONTACT] Kein pending_contact für CallSid=%s", CallSid)
        twiml = build_fallback_twiml(
            message="Entschuldigung, es ist ein Fehler aufgetreten.",
            transcribe_url="/call/transcribe",
        )
        return Response(content=twiml, media_type="application/xml")

    category = pending["category"]

    # B) Ablehnung erkennen → Durchwahl nennen (Schritt 3b)
    if _is_refusal(SpeechResult):
        logger.info("[PROCESS_CONTACT] Ablehnung erkannt, nenne Durchwahl. CallSid=%s", CallSid)
        team_name, ext_words = _CATEGORY_EXTENSIONS.get(category, ("dem Support-Team", ""))
        if ext_words:
            msg = f"Kein Problem. Sie erreichen {team_name} direkt unter Durchwahl {ext_words}. Auf Wiederhören."
        else:
            msg = f"Kein Problem. Bitte wenden Sie sich direkt an {team_name}. Auf Wiederhören."
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="de-DE" voice="Google.de-DE-Neural2-F">{msg}</Say>
  <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    # C) Kontaktdaten per Gemini extrahieren (Schritt 3a)
    caller_contact = await extract_contact_data(SpeechResult)
    logger.info("[PROCESS_CONTACT] Extrahiert: %s", caller_contact)

    # D) E-Mail senden — Anliegen aus pending, Kontaktdaten aus Gemini-Extraktion
    anliegen = pending.get("anliegen") or pending.get("speech_result", "")
    history = get_history(CallSid)
    await send_routing_email(
        category=category,
        caller_number=pending.get("from_number") or "Unbekannt",
        user_question=anliegen,
        conversation_history=history,
        call_sid=CallSid,
        caller_contact=caller_contact,
    )

    # E) Bestätigung + Verabschiedung
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="de-DE" voice="Google.de-DE-Neural2-F">Vielen Dank. Ihre Anfrage wurde weitergeleitet. Sie werden sich in Kürze bei Ihnen melden. Auf Wiederhören.</Say>
  <Hangup/>
</Response>"""
    return Response(content=twiml, media_type="application/xml")
