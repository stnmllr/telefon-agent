import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import tools_router
from app.config import settings
from app.services import email_service, routing_config


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "tool_auth_token", "secret")

    async def _no_overrides():
        return {}
    monkeypatch.setattr(routing_config, "load_overrides", _no_overrides)

    async def _seq():
        return 123
    monkeypatch.setattr(tools_router, "next_ticket_seq", _seq)

    saved = []
    async def _save(record):
        saved.append(record)
    monkeypatch.setattr(tools_router, "save_ticket", _save)

    async def _reserve(call_id, tool):
        return None
    async def _finalize(call_id, tool, **fields):
        return None
    monkeypatch.setattr(tools_router, "reserve", _reserve)
    monkeypatch.setattr(tools_router, "finalize", _finalize)

    app = FastAPI()
    app.include_router(tools_router.router)
    c = TestClient(app)
    c._saved = saved
    return c


def _h():
    return {"X-Tool-Token": "secret"}


def test_create_ticket_success(client, monkeypatch):
    async def _send(*a, **k):
        return True, "msg-9"
    monkeypatch.setattr(email_service, "send_email_raw", _send)
    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "erp", "summary": "Drucker kaputt", "caller_number": "+49..."})
    body = r.json()
    assert body["created"] is True
    assert body["ticket_id"].startswith("SOF-") and body["ticket_id"].endswith("000123")
    assert body["email_sent"] is True
    assert client._saved and client._saved[0]["ticket_id"] == body["ticket_id"]


def test_create_ticket_email_carries_header_rows(client, monkeypatch):
    """Die Ticket-Mail bekommt einen strukturierten Kopfblock mit den Kern-Feldern."""
    captured = {}

    async def _send(recipient, subject, body, **k):
        captured["recipient"] = recipient
        captured["subject"] = subject
        captured["kwargs"] = k
        return True, "msg-h"
    monkeypatch.setattr(email_service, "send_email_raw", _send)

    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "Fibu", "summary": "Kunde XY braucht Hilfe.",
        "caller_number": "+4989123", "callback_requested": True, "priority": "hoch"})
    assert r.status_code == 200
    hr = dict(captured["kwargs"]["header_rows"])
    assert hr["Ticket"].startswith("SOF-") and hr["Ticket"].endswith("000123")
    assert hr["Kategorie"] == "Fibu"
    assert hr["Priorität"] == "hoch"
    assert hr["Anrufer"] == "+4989123"
    assert "Rückruf" in hr and "Zeitpunkt" in hr


def test_create_ticket_recipient_override_routes_to_person(client, monkeypatch):
    """Nennt der Anrufer eine Person, geht die Mail an DEREN Adresse (aus dem
    Telefonbuch), nicht ans Kategorie-Team."""
    captured = {}

    async def _send(recipient, subject, body, **k):
        captured["recipient"] = recipient
        return True, "m"
    monkeypatch.setattr(email_service, "send_email_raw", _send)

    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "it", "summary": "X", "caller_number": "+49",
        "recipient_override": "Stephan.Mueller@sopra-system.com"})
    assert r.status_code == 200
    assert captured["recipient"] == "Stephan.Mueller@sopra-system.com"


def test_create_ticket_invalid_override_falls_back_to_category(client, monkeypatch):
    """Halluzinierte Override-Adresse wird NICHT verwendet -> Kategorie-Route,
    Ticket trotzdem erstellt."""
    captured = {}

    async def _send(recipient, subject, body, **k):
        captured["recipient"] = recipient
        return True, "m"
    monkeypatch.setattr(email_service, "send_email_raw", _send)

    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "it", "summary": "X", "recipient_override": "hallu@x.de"})
    assert r.status_code == 200
    assert captured["recipient"] == "it-support@sopra-system.com"


def test_create_ticket_caller_name_in_header(client, monkeypatch):
    captured = {}

    async def _send(recipient, subject, body, **k):
        captured["kwargs"] = k
        return True, "m"
    monkeypatch.setattr(email_service, "send_email_raw", _send)

    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "it", "summary": "X", "caller_name": "Frau Meier, Muster GmbH"})
    assert r.status_code == 200
    hr = dict(captured["kwargs"]["header_rows"])
    assert hr["Anrufer-Name"] == "Frau Meier, Muster GmbH"


def test_create_ticket_partial_fail_email(client, monkeypatch):
    async def _send_fail(*a, **k):
        return False, ""
    monkeypatch.setattr(email_service, "send_email_raw", _send_fail)
    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "erp", "summary": "X", "caller_number": "+49..."})
    body = r.json()
    assert body["created"] is True          # Ticket gilt trotzdem als erstellt
    assert body["email_sent"] is False      # Mail fehlgeschlagen


def test_create_ticket_in_progress_returns_409(client, monkeypatch):
    """FIX 1: concurrent retry with in_progress dup must return 409."""
    seq_calls = []
    saved_calls = []

    async def _in_progress(call_id, tool):
        return {"status": "in_progress"}
    monkeypatch.setattr(tools_router, "reserve", _in_progress)

    async def _seq():
        seq_calls.append(1)
        return 99
    monkeypatch.setattr(tools_router, "next_ticket_seq", _seq)

    async def _save(record):
        saved_calls.append(record)
    monkeypatch.setattr(tools_router, "save_ticket", _save)

    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "erp", "summary": "X", "call_id": "C3"})
    assert r.status_code == 409
    assert seq_calls == []   # next_ticket_seq must NOT have been called
    assert saved_calls == []  # save_ticket must NOT have been called


def test_create_ticket_done_duplicate_skips_creation(client, monkeypatch):
    """M4: reserve returns done dup -> return cached ticket_id, no seq/save."""
    seq_calls = []
    saved_calls = []

    async def _done_dup(call_id, tool):
        return {"status": "done", "ticket_id": "SOF-2026-000042", "email_sent": True}
    monkeypatch.setattr(tools_router, "reserve", _done_dup)

    async def _seq():
        seq_calls.append(1)
        return 99
    monkeypatch.setattr(tools_router, "next_ticket_seq", _seq)

    async def _save(record):
        saved_calls.append(record)
    monkeypatch.setattr(tools_router, "save_ticket", _save)

    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "erp", "summary": "X", "call_id": "C4"})
    assert r.status_code == 200
    body = r.json()
    assert body["ticket_id"] == "SOF-2026-000042"
    assert body["email_sent"] is True
    assert seq_calls == []   # next_ticket_seq must NOT have been called
    assert saved_calls == []  # save_ticket must NOT have been called
