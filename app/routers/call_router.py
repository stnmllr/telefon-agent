# ============================================================
# app/routers/call_router.py
# Twilio Webhook-Endpunkte:
#   POST /call/incoming  – neuer Anruf
#   POST /call/transcribe – Spracheingabe verarbeiten
# ============================================================
import logging
from fastapi import APIRouter, Form, Request
from fastapi.responses import Response
from app.services.stt_service import transcribe_recording
from app.services.rag_service import answer_question
from app.services.tts_service import synthesize_speech
from app.utils.twiml_builder import (
    build_welcome_twiml,
    build_answer_twiml,
    build_fallback_twiml,
    build_farewell_twiml,
)

logger = logging.getLogger(__name__)
router = APIRouter()

FAREWELL_KEYWORDS = ["nein danke", "tschüss", "auf wiederhören", "beenden", "kein weiteres"]


@router.post("/incoming")
async def incoming_call(request: Request):
    logger.info("Eingehender Anruf empfangen.")
    twiml = build_welcome_twiml(
        message="Willkommen beim syska ProFI Support. Wie kann ich Ihnen helfen?",
        transcribe_url="/call/transcribe",
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/transcribe")
async def transcribe(
    SpeechResult: str = Form(default=""),
    Confidence: float = Form(default=0.0),
    CallSid: str = Form(default=""),
):
    logger.info("CallSid=%s | STT='%s' (Confidence=%.2f)", CallSid, SpeechResult, Confidence)

    if not SpeechResult or Confidence < 0.4:
        logger.warning("Schlechte STT-Qualität oder leere Eingabe.")
        twiml = build_fallback_twiml(
            message="Entschuldigung, ich habe Sie nicht verstanden. Bitte wiederholen Sie Ihre Frage.",
            transcribe_url="/call/transcribe",
        )
        return Response(content=twiml, media_type="application/xml")

    speech_lower = SpeechResult.lower().strip()
    if any(keyword in speech_lower for keyword in FAREWELL_KEYWORDS):
        logger.info("CallSid=%s | Abschied erkannt.", CallSid)
        twiml = build_farewell_twiml()
        return Response(content=twiml, media_type="application/xml")

    answer = await answer_question(question=SpeechResult, call_sid=CallSid)
    twiml = build_answer_twiml(
        answer=answer,
        transcribe_url="/call/transcribe",
    )
    return Response(content=twiml, media_type="application/xml")
