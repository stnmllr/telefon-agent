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


def test_create_ticket_partial_fail_email(client, monkeypatch):
    async def _send_fail(*a, **k):
        return False, ""
    monkeypatch.setattr(email_service, "send_email_raw", _send_fail)
    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "erp", "summary": "X", "caller_number": "+49..."})
    body = r.json()
    assert body["created"] is True          # Ticket gilt trotzdem als erstellt
    assert body["email_sent"] is False      # Mail fehlgeschlagen
