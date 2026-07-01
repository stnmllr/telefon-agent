"""ElevenLabs Server-Tool-Endpoints (Cloud Run).

Dünne async HTTP-Schicht: Auth -> Validierung -> Pure-Core -> I/O -> Audit.
Firestore-Zugriffe sind in kleine, monkeypatchbare Adapter-Funktionen gekapselt.
"""
import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from google.cloud import firestore
from google.api_core import exceptions as gexc

from app.config import settings
from app.tools import phonebook, recipients, tickets
from app.tools.absence import build_sofia_text
from app.services import routing_config, email_service

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


# ── send_email ───────────────────────────────────────────────
class SendEmailReq(BaseModel):
    category: str
    subject: str
    body: str
    caller_number: str = ""
    caller_name: str = ""
    callback_requested: bool = False
    recipient_override: str | None = None
    call_id: str | None = None
    ticket_ref: str | None = None


async def _resolve_recipient(req: "SendEmailReq") -> str:
    if req.recipient_override:
        if not recipients.validate_override(req.recipient_override, phonebook.all_emails()):
            raise HTTPException(status_code=422, detail="recipient_override not in phonebook")
        return req.recipient_override
    routing = recipients.merge_routing(await routing_config.load_overrides())
    recipient = recipients.resolve_recipient(req.category, routing)
    if not recipient:
        raise HTTPException(status_code=422, detail=f"no recipient for category '{req.category}'")
    return recipient


@router.post("/send_email", dependencies=[Depends(require_tool_token)])
async def send_email(req: SendEmailReq):
    dup = await reserve(req.call_id, "send_email")
    if dup is not None:
        if dup.get("status") == "done":
            return {"sent": dup.get("email_sent", True), "recipient": dup.get("recipient"),
                    "message_id": dup.get("message_id"), "ticket_ref": req.ticket_ref}
        raise HTTPException(status_code=409, detail="request already being processed")

    recipient = await _resolve_recipient(req)
    header_rows = []
    if req.callback_requested:
        header_rows.append(("Rückruf", "Ja — bitte den Anrufer zurückrufen"))
    if req.caller_name:
        header_rows.append(("Anrufer-Name", req.caller_name))
    header_rows.append(("Anrufer", req.caller_number or "—"))
    ok, message_id = await email_service.send_email_raw(
        recipient, req.subject, req.body,
        ticket_ref=req.ticket_ref, callback=req.callback_requested,
        header_rows=header_rows)
    await finalize(req.call_id, "send_email", recipient=recipient,
                   message_id=message_id, email_sent=ok,
                   category=req.category, caller_number=req.caller_number)
    return {"sent": ok, "recipient": recipient, "message_id": message_id,
            "ticket_ref": req.ticket_ref}


# ── create_ticket ────────────────────────────────────────────
async def next_ticket_seq() -> int:
    db = _db()
    ref = db.collection("counters").document("tickets")

    @firestore.async_transactional
    async def _txn(txn):
        snap = await ref.get(transaction=txn)
        current = (snap.to_dict() or {}).get("seq", 0) if snap.exists else 0
        nxt = current + 1
        txn.set(ref, {"seq": nxt}, merge=True)
        return nxt

    return await _txn(db.transaction())


async def save_ticket(record: dict) -> None:
    await _db().collection("tickets").document(record["ticket_id"]).set(record)


class CreateTicketReq(BaseModel):
    category: str
    summary: str
    caller_number: str = ""
    caller_name: str = ""
    callback_requested: bool = False
    priority: str = "normal"
    recipient_override: str | None = None
    call_id: str | None = None


@router.post("/create_ticket", dependencies=[Depends(require_tool_token)])
async def create_ticket(req: CreateTicketReq):
    dup = await reserve(req.call_id, "create_ticket")
    if dup is not None:
        if dup.get("status") == "done":
            return {"created": True, "ticket_id": dup.get("ticket_id"),
                    "email_sent": dup.get("email_sent", False)}
        raise HTTPException(status_code=409, detail="request already being processed")

    year = datetime.now(timezone.utc).year
    seq = await next_ticket_seq()
    ticket_id = tickets.format_ticket_id(year, seq)
    # Empfänger: nennt der Anrufer eine Person, geht die Mail an DEREN (im
    # Telefonbuch validierte) Adresse; sonst Kategorie-Route. Eine halluzinierte
    # Override-Adresse wird ignoriert (nie an Fremdadressen senden), das Ticket
    # bleibt trotzdem erhalten.
    routing = recipients.merge_routing(await routing_config.load_overrides())
    recipient = None
    if req.recipient_override:
        if recipients.validate_override(req.recipient_override, phonebook.all_emails()):
            recipient = req.recipient_override
        else:
            logger.warning("create_ticket: recipient_override nicht im Telefonbuch — ignoriert")
    if not recipient:
        recipient = recipients.resolve_recipient(req.category, routing) \
            or recipients.DEFAULT_ROUTING["verwaltung"]

    # Ticket gilt ab Record-Existenz als erstellt:
    await save_ticket({
        "ticket_id": ticket_id, "category": req.category, "summary": req.summary,
        "caller_number": req.caller_number, "caller_name": req.caller_name,
        "priority": req.priority, "callback_requested": req.callback_requested,
        "recipient": recipient,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    header_rows = [
        ("Ticket", ticket_id),
        ("Kategorie", req.category),
        ("Priorität", req.priority),
        ("Rückruf", "Ja — bitte den Anrufer zurückrufen" if req.callback_requested else "Nein"),
    ]
    if req.caller_name:
        header_rows.append(("Anrufer-Name", req.caller_name))
    header_rows += [
        ("Anrufer", req.caller_number or "—"),
        ("Zeitpunkt", datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")),
    ]
    ok, message_id = await email_service.send_email_raw(
        recipient, f"Ticket {ticket_id}: {req.summary[:60]}", req.summary,
        ticket_ref=ticket_id, callback=req.callback_requested,
        header_rows=header_rows)

    await finalize(req.call_id, "create_ticket", ticket_id=ticket_id,
                   recipient=recipient, message_id=message_id, email_sent=ok,
                   category=req.category, caller_number=req.caller_number)
    return {"created": True, "ticket_id": ticket_id, "email_sent": ok}
