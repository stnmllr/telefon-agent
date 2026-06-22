"""ElevenLabs Server-Tool-Endpoints (Cloud Run).

Dünne async HTTP-Schicht: Auth -> Validierung -> Pure-Core -> I/O -> Audit.
Firestore-Zugriffe sind in kleine, monkeypatchbare Adapter-Funktionen gekapselt.
"""
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from google.cloud import firestore
from google.api_core import exceptions as gexc

from app.config import settings
from app.tools import phonebook
from app.tools.absence import build_sofia_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools")


# ── Auth ─────────────────────────────────────────────────────
async def require_tool_token(x_tool_token: str = Header(default="")):
    expected = settings.tool_auth_token
    if not expected or not hmac.compare_digest(x_tool_token, expected):
        raise HTTPException(status_code=401, detail="invalid tool token")


# ── Firestore-Adapter (monkeypatchbar in Tests) ──────────────
def _db() -> firestore.AsyncClient:
    return firestore.AsyncClient()


def _audit_id(call_id: str, tool: str) -> str:
    return f"{call_id}:{tool}"


async def reserve(call_id: str | None, tool: str) -> dict | None:
    """Atomare Idempotenz-Reservierung. Returns vorhandenes Doc bei Duplikat, sonst None."""
    if not call_id:
        return None
    ref = _db().collection("tool_audit").document(_audit_id(call_id, tool))
    try:
        await ref.create({"tool": tool, "call_id": call_id, "status": "in_progress",
                          "ts": firestore.SERVER_TIMESTAMP})
        return None
    except gexc.AlreadyExists:
        doc = await ref.get()
        return doc.to_dict() if doc.exists else {"status": "in_progress"}


async def finalize(call_id: str | None, tool: str, **fields) -> None:
    data = {"tool": tool, "status": "done", "ts": firestore.SERVER_TIMESTAMP, **fields}
    if not call_id:
        await _db().collection("tool_audit").add(data)
        return
    ref = _db().collection("tool_audit").document(_audit_id(call_id, tool))
    await ref.set({"call_id": call_id, **data}, merge=True)


async def get_active_absence_safe() -> dict | None:
    from app.services.absence_service import get_active_absence
    return await get_active_absence()


# ── lookup_phonebook ─────────────────────────────────────────
class LookupReq(BaseModel):
    name: str


@router.post("/lookup_phonebook", dependencies=[Depends(require_tool_token)])
async def lookup_phonebook(req: LookupReq):
    matches = phonebook.fuzzy_lookup(req.name)
    if not matches:
        return {"found": False}
    return {"found": True, "matches": matches}


# ── check_absence (Conversation-Initiation-Webhook) ──────────
class InitWebhookReq(BaseModel):
    caller_id: str | None = None
    agent_id: str | None = None
    called_number: str | None = None
    call_sid: str | None = None


@router.post("/check_absence", dependencies=[Depends(require_tool_token)])
async def check_absence(req: InitWebhookReq):
    try:
        absence = await get_active_absence_safe()
    except Exception as exc:  # Graceful Degradation: Call-Setup nie blockieren
        logger.warning("check_absence Firestore-Fehler: %s", exc)
        absence = None
    if absence:
        dv = {"absence_active": "true", "absence_text": build_sofia_text(absence)}
    else:
        dv = {"absence_active": "false", "absence_text": ""}
    return {"type": "conversation_initiation_client_data", "dynamic_variables": dv}
