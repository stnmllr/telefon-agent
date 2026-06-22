import pytest
from app.services import routing_config


class _Doc:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class _DocRef:
    def __init__(self, store, raises=False):
        self._store = store
        self._raises = raises

    async def get(self):
        if self._raises:
            raise RuntimeError("firestore down")
        return _Doc(self._store.get("data"))

    async def set(self, data, merge=False):
        self._store["data"] = {**(self._store.get("data") or {}), **data} if merge else data


class _Collection:
    def __init__(self, ref):
        self._ref = ref

    def document(self, _id):
        return self._ref


class _FakeDB:
    def __init__(self, ref):
        self._ref = ref

    def collection(self, _name):
        return _Collection(self._ref)


@pytest.mark.asyncio
async def test_load_overrides_returns_dict(monkeypatch):
    store = {"data": {"erp": "neu@x.de"}}
    monkeypatch.setattr(routing_config, "_db", lambda: _FakeDB(_DocRef(store)))
    assert await routing_config.load_overrides() == {"erp": "neu@x.de"}


@pytest.mark.asyncio
async def test_load_overrides_graceful_on_error(monkeypatch):
    monkeypatch.setattr(routing_config, "_db", lambda: _FakeDB(_DocRef({}, raises=True)))
    assert await routing_config.load_overrides() == {}


@pytest.mark.asyncio
async def test_save_overrides(monkeypatch):
    store = {"data": {"erp": "alt@x.de"}}
    monkeypatch.setattr(routing_config, "_db", lambda: _FakeDB(_DocRef(store)))
    await routing_config.save_overrides({"hr": "neu@x.de"})
    assert store["data"] == {"erp": "alt@x.de", "hr": "neu@x.de"}


@pytest.mark.asyncio
async def test_replace_overrides_removes_old_keys(monkeypatch):
    """FIX 2: replace_overrides uses merge=False so removed keys are truly gone."""
    store = {"data": {"erp": "alt@x.de", "hr": "hr@x.de"}}
    monkeypatch.setattr(routing_config, "_db", lambda: _FakeDB(_DocRef(store)))
    # Replace with only hr — erp must disappear
    await routing_config.replace_overrides({"hr": "neu@x.de"})
    assert store["data"] == {"hr": "neu@x.de"}
    assert "erp" not in store["data"]
