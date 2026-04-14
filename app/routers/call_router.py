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

from app.services.rag_service import answer_question
from app.services import phonebook_service
from app.utils.twiml_builder import (
    build_welcome_twiml,
    build_answer_twiml,
    build_fallback_twiml,
    build_farewell_twiml,
)

db = firestore.Client()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/call")

PHONEBOOK_KEYWORDS = [
    "sprechen",
    "verbinden",
    "durchwahl",
    "erreichen",
    "durchstellen",
    "weitergeben",
]

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
            "Guten Tag, Sie sind verbunden mit dem SOPRA System Assistenten. "
            "Ich bin ein Künstliche Intelligenz Assistent und helfe Ihnen gerne weiter. "
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
        })
    except Exception as exc:
        logger.exception("[TRANSCRIBE] Firestore-Speichern fehlgeschlagen: %s", exc)

    is_long_input = len(SpeechResult.split()) > 5

    if is_long_input:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="de-DE" voice="Google.de-DE-Neural2-F">Einen Moment bitte, ich schaue das für Sie nach.</Say>
  <Redirect method="POST">/call/process</Redirect>
</Response>"""
    else:
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
):
    """
    Liest SpeechResult aus Firestore, ruft RAG/LLM auf und
    gibt die eigentliche Antwort zurück.
    """

    logger.info("[PROCESS] CallSid=%s", CallSid)

    # --------------------------------------------------------
    # A) SpeechResult aus Firestore laden und löschen
    # --------------------------------------------------------
    speech_result = ""
    try:
        ref = db.collection("pending").document(CallSid)
        doc = ref.get()
        if doc.exists:
            speech_result = doc.to_dict().get("speech_result", "")
            ref.delete()
        else:
            logger.warning("[PROCESS] Kein pending-Eintrag für CallSid=%s", CallSid)
    except Exception as exc:
        logger.exception("[PROCESS] Firestore-Lesen fehlgeschlagen: %s", exc)

    if not speech_result:
        twiml = build_fallback_twiml(
            message="Entschuldigung, ich konnte Ihre Frage nicht abrufen. Bitte wiederholen Sie.",
            transcribe_url="/call/transcribe",
        )
        return Response(content=twiml, media_type="application/xml")

    # --------------------------------------------------------
    # B) Telefonbuch-Shortcut (ohne LLM)
    # --------------------------------------------------------
    text_lower = speech_result.lower()
    if any(kw in text_lower for kw in PHONEBOOK_KEYWORDS):
        entry = phonebook_service.find_in_text(speech_result)
        if entry:
            ext_tts = "-".join(entry["durchwahl"])
            answer = (
                f"{entry['name']} erreichen Sie unter Durchwahl {ext_tts}. "
                f"Ich kann leider keine direkte Weiterleitung vornehmen. "
                f"Kann ich Ihnen sonst noch helfen?"
            )
            logger.info("[PROCESS] Telefonbuch-Shortcut | %s → %s", entry["name"], entry["durchwahl"])
            twiml = build_answer_twiml(answer=answer, transcribe_url="/call/transcribe")
            return Response(content=twiml, media_type="application/xml")

    # --------------------------------------------------------
    # C) RAG + LLM
    # --------------------------------------------------------
    try:
        answer = await answer_question(
            question=speech_result,
            call_sid=CallSid,
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

    return Response(content=twiml, media_type="application/xml")
