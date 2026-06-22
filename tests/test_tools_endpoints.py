import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import tools_router
from app.config import settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "tool_auth_token", "secret")
    app = FastAPI()
    app.include_router(tools_router.router)
    return TestClient(app)


def test_auth_missing_token_401(client):
    r = client.post("/tools/lookup_phonebook", json={"name": "Schindler"})
    assert r.status_code == 401


def test_lookup_phonebook_match(client):
    r = client.post("/tools/lookup_phonebook",
                    json={"name": "Schindler"},
                    headers={"X-Tool-Token": "secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["matches"][0]["nachname"] == "Schindler"


def test_lookup_phonebook_no_match(client):
    r = client.post("/tools/lookup_phonebook",
                    json={"name": "Xylophon"},
                    headers={"X-Tool-Token": "secret"})
    assert r.json() == {"found": False}


def test_check_absence_active(client, monkeypatch):
    async def _fake():
        return {"type": "urlaub", "end": "2026-07-15"}
    monkeypatch.setattr(tools_router, "get_active_absence_safe", _fake)
    r = client.post("/tools/check_absence", json={"call_sid": "X"},
                    headers={"X-Tool-Token": "secret"})
    body = r.json()
    assert body["type"] == "conversation_initiation_client_data"
    assert body["dynamic_variables"]["absence_active"] == "true"
    assert "Urlaub" in body["dynamic_variables"]["absence_text"]


def test_check_absence_graceful_on_error(client, monkeypatch):
    async def _boom():
        raise RuntimeError("firestore down")
    monkeypatch.setattr(tools_router, "get_active_absence_safe", _boom)
    r = client.post("/tools/check_absence", json={"call_sid": "X"},
                    headers={"X-Tool-Token": "secret"})
    assert r.json()["dynamic_variables"]["absence_active"] == "false"
