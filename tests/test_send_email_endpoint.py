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

    sent = []

    async def _fake_send(recipient, subject, body, ticket_ref=None, callback=False):
        sent.append({"recipient": recipient, "ticket_ref": ticket_ref})
        return True, "msg-1"
    monkeypatch.setattr(email_service, "send_email_raw", _fake_send)

    async def _reserve(call_id, tool):
        return None
    async def _finalize(call_id, tool, **fields):
        return None
    monkeypatch.setattr(tools_router, "reserve", _reserve)
    monkeypatch.setattr(tools_router, "finalize", _finalize)

    app = FastAPI()
    app.include_router(tools_router.router)
    c = TestClient(app)
    c._sent = sent
    return c


def _h():
    return {"X-Tool-Token": "secret"}


def test_send_email_category_routing(client):
    r = client.post("/tools/send_email", headers=_h(), json={
        "category": "erp", "subject": "S", "body": "B"})
    assert r.status_code == 200
    assert r.json()["recipient"] == "erp-support@sopra-system.com"
    assert r.json()["sent"] is True


def test_send_email_override_guard_rejects_hallucination(client):
    r = client.post("/tools/send_email", headers=_h(), json={
        "category": "phonebook", "subject": "S", "body": "B",
        "recipient_override": "halluziniert@x.de"})
    assert r.status_code == 422


def test_send_email_override_accepts_phonebook_email(client):
    r = client.post("/tools/send_email", headers=_h(), json={
        "category": "phonebook", "subject": "S", "body": "B",
        "recipient_override": "Severin.Schindler@sopra-system.com"})
    assert r.status_code == 200
    assert r.json()["recipient"] == "Severin.Schindler@sopra-system.com"


def test_send_email_idempotent_duplicate_skips_send(client, monkeypatch):
    async def _dup(call_id, tool):
        return {"status": "done", "recipient": "erp-support@sopra-system.com",
                "message_id": "old", "email_sent": True}
    monkeypatch.setattr(tools_router, "reserve", _dup)
    r = client.post("/tools/send_email", headers=_h(), json={
        "category": "erp", "subject": "S", "body": "B", "call_id": "C1"})
    assert r.status_code == 200
    assert r.json()["message_id"] == "old"
    assert client._sent == []   # kein erneuter Versand


def test_send_email_in_progress_returns_409(client, monkeypatch):
    """FIX 1: concurrent retry with in_progress dup must return 409, not re-send."""
    async def _in_progress(call_id, tool):
        return {"status": "in_progress"}
    monkeypatch.setattr(tools_router, "reserve", _in_progress)
    r = client.post("/tools/send_email", headers=_h(), json={
        "category": "erp", "subject": "S", "body": "B", "call_id": "C2"})
    assert r.status_code == 409
    assert client._sent == []   # no send must have occurred
