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

# Nach der Farewell-Prüfung, vor dem RAG-Aufruf einfügen:

# Kurze Antworten (Ja/Nein/OK) nur mit Gesprächshistory verarbeiten
SHORT_RESPONSES = ["ja", "nein", "ok", "okay", "erledigt", "gemacht", "nicht", 
                   "klappt nicht", "funktioniert nicht", "verstanden"]

if any(speech_lower == keyword or speech_lower.startswith(keyword) 
       for keyword in SHORT_RESPONSES) and len(SpeechResult.split()) <= 4:
    logger.info("CallSid=%s | Kurze Antwort erkannt, nutze Konversationskontext.", CallSid)
    answer = await answer_question(
        question=f"Der User antwortet auf deine letzte Aussage: '{SpeechResult}'",
        call_sid=CallSid
    )
    twiml = build_answer_twiml(answer=answer, transcribe_url="/call/transcribe")
    return Response(content=twiml, media_type="application/xml")

@router.post("/incoming")
async def incoming_call(request: Request):
    """
    Twilio ruft diesen Endpoint auf, sobald ein Anruf eingeht.
    Wir begrüßen den Anrufer und starten die Spracheingabe.
    """
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
    """
    Twilio liefert hier das STT-Ergebnis (SpeechResult).
    Wir leiten es an die RAG-Pipeline weiter und antworten per TTS.
    """
    logger.info("CallSid=%s | STT='%s' (Confidence=%.2f)", CallSid, SpeechResult, Confidence)

    if not SpeechResult or Confidence < 0.4:
        logger.warning("Schlechte STT-Qualität oder leere Eingabe.")
        twiml = build_fallback_twiml(
            message="Entschuldigung, ich habe Sie nicht verstanden. Bitte wiederholen Sie Ihre Frage.",
            transcribe_url="/call/transcribe",
        )
        return Response(content=twiml, media_type="application/xml")

    # Nur Abschied abfangen — alles andere geht in die RAG-Pipeline
    speech_lower = SpeechResult.lower().strip()
    if any(keyword in speech_lower for keyword in FAREWELL_KEYWORDS):
        logger.info("CallSid=%s | Abschied erkannt.", CallSid)
        twiml = build_farewell_twiml()
        return Response(content=twiml, media_type="application/xml")

    # RAG → LLM — auch "Ja" und "Weiter" landen hier
    # Gemini nutzt den Gesprächsverlauf aus Firestore und weiß wo wir waren
    answer = await answer_question(question=SpeechResult, call_sid=CallSid)
    twiml = build_answer_twiml(
        answer=answer,
        transcribe_url="/call/transcribe",
    )
    return Response(content=twiml, media_type="application/xml")
