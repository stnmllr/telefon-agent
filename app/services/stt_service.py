# ============================================================
# app/services/stt_service.py
# Speech-to-Text via Google Cloud STT v2 (Chirp)
# Hinweis: Bei Twilio-Integration übernimmt Twilio die STT
# direkt (<Gather input="speech">) – dieser Service wird für
# direkte Audio-Uploads / eigene Streaming-Pipelines genutzt.
# ============================================================

import logging
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import (
    AutoDetectDecodingConfig,
    RecognizeRequest,
    RecognitionConfig,
    RecognitionFeatures,
)
from app.config import settings

logger = logging.getLogger(__name__)


async def transcribe_recording(audio_bytes: bytes, sample_rate: int = 8000) -> str:
    """
    Transkribiert Audio-Bytes mit Cloud STT v2 (Chirp-Modell).
    Wird genutzt wenn Audio direkt als Bytes vorliegt
    (z.B. Twilio Recording-Callback oder WebSocket-Stream).
    """
    try:
        client = SpeechClient()

        config = RecognitionConfig(
            auto_decoding_config=AutoDetectDecodingConfig(),
            language_codes=[settings.stt_language],
            model=settings.stt_model,              # "chirp"
            features=RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_spoken_punctuation=False,
            ),
        )

        recognizer = f"projects/{settings.gcp_project_id}/locations/{settings.gcp_location}/recognizers/_"

        request = RecognizeRequest(
            recognizer=recognizer,
            config=config,
            content=audio_bytes,
        )

        response = client.recognize(request=request)

        if not response.results:
            logger.warning("STT: Keine Ergebnisse zurückgegeben.")
            return ""

        transcript = response.results[0].alternatives[0].transcript
        confidence = response.results[0].alternatives[0].confidence
        logger.info("STT Transkript='%s' (Confidence=%.2f)", transcript, confidence)
        return transcript

    except Exception as e:
        logger.error("STT Fehler: %s", e)
        return ""
