# ============================================================
# app/services/absence_service.py
# Firestore CRUD für Abwesenheiten (Sofia Handy-App)
# ============================================================

import logging
from datetime import datetime, timezone
from typing import Optional
from google.cloud import firestore

logger = logging.getLogger(__name__)

COLLECTION = "absence"

# Typ → Sofia-Text
ABSENCE_PHRASES = {
    "urlaub":      "im Urlaub",
    "meeting":     "im Meeting",
    "abwesend":    "derzeit abwesend",
    "dienstreise": "auf Dienstreise",
}


def _get_client() -> firestore.AsyncClient:
    return firestore.AsyncClient()


async def create_absence(
    absence_type: str,
    start: str,
    end: str,
    note: Optional[str] = None,
) -> dict:
    """
    Speichert eine neue Abwesenheit in Firestore.
    start / end: ISO-8601 Strings (z.B. "2026-04-25T09:00" oder "2026-04-28")
    """
    db = _get_client()
    doc_ref = db.collection(COLLECTION).document()
    data = {
        "id":         doc_ref.id,
        "type":       absence_type.lower(),
        "start":      start,
        "end":        end,
        "note":       note or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await doc_ref.set(data)
    logger.info("Abwesenheit gespeichert: %s", data)
    return data


async def get_active_absence() -> Optional[dict]:
    """
    Gibt die erste aktuell aktive Abwesenheit zurück (start ≤ jetzt ≤ end).
    Für Sofia: wird beim Gesprächsstart geprüft.
    """
    db = _get_client()
    now = datetime.now(timezone.utc).isoformat()

    docs = db.collection(COLLECTION).stream()
    async for doc in docs:
        data = doc.to_dict()
        start = data.get("start", "")
        end = data.get("end", "")
        # Einfacher String-Vergleich funktioniert für ISO-8601
        if start <= now <= end + "Z":
            return data
    return None


async def get_all_absences() -> list[dict]:
    """Alle Abwesenheiten für die App-Anzeige."""
    db = _get_client()
    result = []
    docs = db.collection(COLLECTION).order_by("start").stream()
    async for doc in docs:
        result.append(doc.to_dict())
    return result


async def delete_absence(absence_id: str) -> bool:
    """Löscht eine Abwesenheit anhand der ID."""
    db = _get_client()
    doc_ref = db.collection(COLLECTION).document(absence_id)
    doc = await doc_ref.get()
    if not doc.exists:
        return False
    await doc_ref.delete()
    logger.info("Abwesenheit gelöscht: %s", absence_id)
    return True


def build_sofia_text(absence: dict) -> str:
    """
    Gibt den Sofia-Gesprächstext für eine aktive Abwesenheit zurück.
    Wird in rag_service.py verwendet.
    """
    absence_type = absence.get("type", "abwesend")
    phrase = ABSENCE_PHRASES.get(absence_type, "derzeit abwesend")
    end = absence.get("end", "")

    if absence_type == "meeting":
        # end ist eine Uhrzeit: "2026-04-25T14:00" → "14:00"
        try:
            time_part = end.split("T")[1][:5] if "T" in end else end
            return f"Herr Müller ist gerade {phrase} und ab {time_part} Uhr wieder erreichbar."
        except Exception:
            return f"Herr Müller ist gerade {phrase}."
    else:
        # end ist ein Datum: "2026-04-28" → "28.04.2026"
        try:
            date_part = end.split("T")[0]
            d = datetime.fromisoformat(date_part)
            formatted = d.strftime("%-d. %B %Y")  # z.B. "28. April 2026"
            return f"Herr Müller ist {phrase} und ab {formatted} wieder erreichbar."
        except Exception:
            return f"Herr Müller ist {phrase}."
