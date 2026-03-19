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

from app.services.rag_service import answer_question
from app.utils.twiml_builder import (
    build_welcome_twiml,
    build_answer_twiml,
    build_fallback_twiml,
    build_farewell_twiml,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/call")

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
            "Willkommen beim syska ProFI Support. "
            "Wie kann ich Ihnen helfen?"
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
    # C) Normale Anfrage → RAG + LLM
    # --------------------------------------------------------
    try:
        answer = await answer_question(
            question=SpeechResult,
            call_sid=CallSid,
        )

    except Exception as exc:
        logger.exception("[TRANSCRIBE] Fehler in answer_question(): %s", exc)

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
