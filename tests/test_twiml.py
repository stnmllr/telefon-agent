# ============================================================
# tests/test_twiml.py
# Einfache Tests für den TwiML-Builder (keine GCP-Deps nötig)
# Ausführen: pytest tests/
# ============================================================

import pytest
from app.utils.twiml_builder import (
    build_welcome_twiml,
    build_answer_twiml,
    build_fallback_twiml,
)


def test_welcome_twiml_contains_gather():
    twiml = build_welcome_twiml("Hallo!", "/call/transcribe")
    assert "<Gather" in twiml
    assert "action=\"/call/transcribe\"" in twiml
    assert "Hallo!" in twiml


def test_answer_twiml_contains_answer():
    twiml = build_answer_twiml("Die Lieferzeit beträgt 3 Tage.", "/call/transcribe")
    assert "Die Lieferzeit beträgt 3 Tage." in twiml
    assert "<Gather" in twiml


def test_fallback_twiml_is_valid_xml():
    import xml.etree.ElementTree as ET
    twiml = build_fallback_twiml("Bitte wiederholen.", "/call/transcribe")
    root = ET.fromstring(twiml)   # wirft Exception bei ungültigem XML
    assert root.tag == "Response"


def test_health_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
