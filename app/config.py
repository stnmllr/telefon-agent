# ============================================================
# app/config.py
# Alle Konfigurationswerte aus Umgebungsvariablen /
# GCP Secret Manager (via .env im lokalen Dev)
# ============================================================

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"

    # GCP
    gcp_project_id: str = "my-gcp-project"
    gcp_location: str = "europe-west3"           # Frankfurt – DSGVO

    # Vertex AI
    gemini_model: str = "gemini-1.5-pro-002"
    vertex_search_datastore: str = "projects/{project}/locations/global/collections/default_collection/dataStores/handbuecher"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # STT
    stt_language: str = "de-DE"
    stt_model: str = "chirp"

    # TTS
    tts_voice: str = "de-DE-Neural2-F"
    tts_speaking_rate: float = 1.0

    # RAG
    rag_top_k: int = 5
    rag_max_tokens: int = 200
    llm_temperature: float = 0.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
