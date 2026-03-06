# ============================================================
# app/services/tts_service.py
# Text-to-Speech via Google Cloud TTS Neural2
# Hinweis: Bei Twilio <Say> übernimmt Twilio die Sprachausgabe.
# Dieser Service liefert Audio-Bytes für WebSocket-Streaming.
# ============================================================

import logging
from google.cloud import texttospeech
from app.config import settings

logger = logging.getLogger(__name__)


async def synthesize_speech(text: str) -> bytes:
    """
    Wandelt Text in Audio (MP3) um – Google Cloud TTS Neural2.
    Gibt Audio-Bytes zurück, die direkt gestreamt werden können.
    """
    try:
        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code="de-DE",
            name=settings.tts_voice,              # de-DE-Neural2-F
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=settings.tts_speaking_rate,
            pitch=0.0,
        )

        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )

        logger.info("TTS synthetisiert: %d Zeichen → %d Bytes Audio", len(text), len(response.audio_content))
        return response.audio_content

    except Exception as e:
        logger.error("TTS Fehler: %s", e)
        return b""
