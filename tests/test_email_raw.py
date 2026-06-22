import pytest
from app.services import email_service


class _FakeResponse:
    status_code = 202
    headers = {"X-Message-Id": "msg-123"}


class _FakeSG:
    def __init__(self, *a, **k):
        pass

    def send(self, message):
        return _FakeResponse()


@pytest.mark.asyncio
async def test_send_email_raw_success(monkeypatch):
    monkeypatch.setattr(email_service, "SENDGRID_API_KEY", "SG.test")
    monkeypatch.setattr(email_service, "SendGridAPIClient", _FakeSG)
    ok, message_id = await email_service.send_email_raw(
        "a@b.de", "Betreff", "Inhalt", ticket_ref="SOF-2026-000001")
    assert ok is True
    assert message_id == "msg-123"


@pytest.mark.asyncio
async def test_send_email_raw_no_key(monkeypatch):
    monkeypatch.setattr(email_service, "SENDGRID_API_KEY", "")
    ok, message_id = await email_service.send_email_raw("a@b.de", "B", "I")
    assert ok is False
    assert message_id == ""
