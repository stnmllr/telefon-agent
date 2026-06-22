"""Firestore-Persistenz der Routing-Overrides (config/routing).

KEIN In-Prozess-Cache: Cloud Run ist multi-instance/scale-to-zero — pro Call
frisch laden, damit ein PWA-Edit sofort wirkt.
"""
import logging
from google.cloud import firestore

logger = logging.getLogger(__name__)


def _db() -> firestore.AsyncClient:
    return firestore.AsyncClient()


async def load_overrides() -> dict:
    try:
        doc = await _db().collection("config").document("routing").get()
        if doc.exists:
            return doc.to_dict() or {}
        return {}
    except Exception as exc:  # Graceful: nie den Call-Pfad blockieren
        logger.warning("routing_config.load_overrides fehlgeschlagen: %s", exc)
        return {}


async def save_overrides(overrides: dict) -> None:
    await _db().collection("config").document("routing").set(overrides, merge=True)


async def replace_overrides(overrides: dict) -> None:
    """Persist overrides with REPLACE semantics (merge=False) so removed keys are deleted."""
    await _db().collection("config").document("routing").set(overrides, merge=False)
