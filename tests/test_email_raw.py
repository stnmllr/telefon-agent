"""Tests für den Resend-basierten Mail-Versand (send_email_raw + send_routing_email).

Seam: email_service._client() liefert den httpx.AsyncClient. Die Tests ersetzen
ihn durch einen Client mit httpx.MockTransport, der den Request abfängt — so
lassen sich Header (z.B. Authorization) und Body ohne echten Netzwerkruf prüfen.
"""
import httpx
import pytest

from app.services import email_service


def _mock_client(handler):
    """Factory, die email_service._client ersetzt: AsyncClient mit MockTransport."""
    def _factory():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return _factory


@pytest.mark.asyncio
async def test_send_email_raw_success(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"id": "re_abc123"})

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_live_key")
    monkeypatch.setattr(email_service, "_client", _mock_client(handler))

    ok, message_id = await email_service.send_email_raw(
        "a@b.de", "Betreff", "Inhalt", ticket_ref="SOF-2026-000001")

    assert ok is True
    assert message_id == "re_abc123"
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["json"]["to"] == ["a@b.de"]
    assert "SOF-2026-000001" in captured["json"]["subject"]


@pytest.mark.asyncio
async def test_send_email_raw_renders_header_rows(monkeypatch):
    """Optionale header_rows erscheinen als Kopfblock in Text UND HTML, vor dem Body."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"id": "re_h"})

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_live_key")
    monkeypatch.setattr(email_service, "_client", _mock_client(handler))

    ok, _ = await email_service.send_email_raw(
        "a@b.de", "Betreff", "Der eigentliche Body-Text.",
        ticket_ref="SOF-2026-000003",
        header_rows=[("Ticket", "SOF-2026-000003"), ("Kategorie", "fibu")])

    assert ok is True
    text = captured["json"]["text"]
    html = captured["json"]["html"]
    assert "Ticket: SOF-2026-000003" in text
    assert "Kategorie: fibu" in text
    assert "Der eigentliche Body-Text." in text
    assert "SOF-2026-000003" in html and "Kategorie" in html


@pytest.mark.asyncio
async def test_send_email_raw_no_header_rows_unchanged(monkeypatch):
    """Ohne header_rows kein Kopfblock (send_email-Personenmail bleibt schlank)."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"id": "re_n"})

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_live_key")
    monkeypatch.setattr(email_service, "_client", _mock_client(handler))

    ok, _ = await email_service.send_email_raw("a@b.de", "B", "Nur Body.")
    assert ok is True
    assert "Nur Body." in captured["json"]["text"]
    assert "Kategorie" not in captured["json"]["text"]


@pytest.mark.asyncio
async def test_send_email_raw_strips_trailing_whitespace(monkeypatch):
    """Key mit Trailing \\r\\n darf den Authorization-Header NICHT zerstören."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"id": "re_x"})

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_clean_key\r\n")
    monkeypatch.setattr(email_service, "_client", _mock_client(handler))

    ok, _ = await email_service.send_email_raw("a@b.de", "B", "I")

    assert ok is True
    assert captured["auth"] == "Bearer re_clean_key"


@pytest.mark.asyncio
async def test_send_email_raw_error_does_not_leak_key(monkeypatch, caplog):
    secret = "re_SECRET_MUST_NOT_LEAK"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Invalid API key"})

    monkeypatch.setattr(email_service, "RESEND_API_KEY", secret)
    monkeypatch.setattr(email_service, "_client", _mock_client(handler))

    with caplog.at_level("ERROR"):
        ok, message_id = await email_service.send_email_raw("a@b.de", "B", "I")

    assert ok is False
    assert message_id == ""
    assert secret not in caplog.text
    assert "Bearer" not in caplog.text


@pytest.mark.asyncio
async def test_send_email_raw_no_key(monkeypatch):
    monkeypatch.setattr(email_service, "RESEND_API_KEY", "")
    ok, message_id = await email_service.send_email_raw("a@b.de", "B", "I")
    assert ok is False
    assert message_id == ""


@pytest.mark.asyncio
async def test_send_routing_email_uses_resend_and_category(monkeypatch):
    """Die zweite Sende-Funktion läuft ebenfalls über Resend; Routing nach category."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"id": "re_routing"})

    async def _fake_summary(history):
        return "Zusammenfassung"

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_live_key")
    monkeypatch.setattr(email_service, "_client", _mock_client(handler))
    monkeypatch.setattr(
        "app.services.rag_service.summarize_conversation", _fake_summary)

    ok = await email_service.send_routing_email(
        category="erp", caller_number="+49123", user_question="Frage",
        conversation_history=[{"role": "user", "content": "Hi"}])

    assert ok is True
    assert captured["json"]["to"] == ["erp-support@sopra-system.com"]
