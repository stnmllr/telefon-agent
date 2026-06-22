import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import app_router
from app.services import routing_config


@pytest.fixture
def client(monkeypatch):
    # Auth umgehen: require_auth-Dependency überschreiben
    app = FastAPI()
    app.include_router(app_router.router)
    app.dependency_overrides[app_router.require_auth] = lambda: "stn.mueller@gmail.com"

    store = {"data": {}}

    async def _load():
        return dict(store["data"])
    async def _save(overrides):
        store["data"].update(overrides)
    monkeypatch.setattr(routing_config, "load_overrides", _load)
    monkeypatch.setattr(routing_config, "save_overrides", _save)
    monkeypatch.setattr(app_router, "_audit_routing_change", lambda *a, **k: None)

    c = TestClient(app)
    c._store = store
    return c


def test_get_routing_returns_effective_map(client):
    r = client.get("/app/api/routing")
    assert r.status_code == 200
    routing = r.json()["routing"]
    assert routing["fibu"] == "Stephan.Mueller@sopra-system.com"


def test_put_routing_saves_override(client):
    r = client.put("/app/api/routing", json={"routing": {"erp": "neu@sopra-system.com"}})
    assert r.status_code == 200
    assert client._store["data"]["erp"] == "neu@sopra-system.com"
    # GET reflektiert den Override
    routing = client.get("/app/api/routing").json()["routing"]
    assert routing["erp"] == "neu@sopra-system.com"


def test_put_routing_rejects_invalid_email(client):
    r = client.put("/app/api/routing", json={"routing": {"erp": "keine-email"}})
    assert r.status_code == 422
