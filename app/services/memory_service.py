# ============================================================
# app/services/memory_service.py
# Speichert Gesprächsverlauf pro Anruf in Firestore
# Jeder Anruf (CallSid) bekommt seine eigene Konversation
# ============================================================
import logging
from google.cloud import firestore
from datetime import datetime

logger = logging.getLogger(__name__)

db = firestore.Client()

MAX_HISTORY = 6  # max. 3 Frage-Antwort-Paare merken


def get_history(call_sid: str) -> list:
    """Gesprächsverlauf für diesen Anruf laden."""
    try:
        doc = db.collection("conversations").document(call_sid).get()
        if doc.exists:
            return doc.to_dict().get("history", [])
        return []
    except Exception as e:
        logger.error("Memory laden fehlgeschlagen: %s", e)
        return []


def save_message(call_sid: str, role: str, content: str):
    """Neue Nachricht zum Gesprächsverlauf hinzufügen."""
    try:
        ref = db.collection("conversations").document(call_sid)
        doc = ref.get()
        history = doc.to_dict().get("history", []) if doc.exists else []

        history.append({"role": role, "content": content})

        # Nur die letzten MAX_HISTORY Nachrichten behalten
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]

        ref.set({
            "history": history,
            "updated_at": datetime.utcnow().isoformat(),
            "call_sid": call_sid,
        })
    except Exception as e:
        logger.error("Memory speichern fehlgeschlagen: %s", e)


def clear_history(call_sid: str):
    """Gesprächsverlauf löschen (nach Anrufende)."""
    try:
        db.collection("conversations").document(call_sid).delete()
    except Exception as e:
        logger.error("Memory löschen fehlgeschlagen: %s", e)
