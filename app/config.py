# ============================================================
# app/config.py
# ============================================================
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"

    # GCP
    gcp_project_id: str = "boxwood-mantra-489408-c0"   # echtes Projekt als Fallback
    gcp_location: str = "us-central1"                   # Gemini-Region

    # Vertex AI Search — immer global, separate Variable
    vertex_search_location: str = "global"
    vertex_search_engine_id: str = "handbuecher-engine"
    vertex_search_datastore: str = "handbuecher-v2"

    # Vertex AI / Gemini
    gemini_model: str = "gemini-2.0-flash-001"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # STT
    stt_language: str = "de-DE"
    stt_model: str = "chirp"

    # TTS
    tts_voice: str = "de-DE-Journey-F"
    tts_speaking_rate: float = 1.0

    # RAG
    rag_top_k: int = 3
    rag_max_tokens: int = 1200
    llm_temperature: float = 0.0

    # Latenz-Logging
    latency_logging: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
