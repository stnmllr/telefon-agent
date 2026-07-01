from app.tools.absence import build_sofia_text


def test_urlaub_with_date():
    txt = build_sofia_text({"type": "urlaub", "end": "2026-07-15"})
    assert txt == "Herr Müller ist im Urlaub und ab 15. Juli 2026 wieder erreichbar."


def test_meeting_with_time():
    txt = build_sofia_text({"type": "meeting", "end": "2026-07-15T14:00"})
    assert txt == "Herr Müller ist gerade im Meeting und ab 14:00 Uhr wieder erreichbar."


def test_dienstreise():
    txt = build_sofia_text({"type": "dienstreise", "end": "2026-08-01"})
    assert "auf Dienstreise" in txt and "1. August 2026" in txt


def test_abwesend_default_type():
    txt = build_sofia_text({"type": "abwesend", "end": "2026-07-15"})
    assert "derzeit abwesend" in txt


def test_invalid_date_graceful():
    txt = build_sofia_text({"type": "urlaub", "end": "kaputt"})
    assert txt == "Herr Müller ist im Urlaub."


def test_note_appended_as_vertretung():
    # Das note-Feld der App (z.B. eine echte Vertretung) wird an Sofias Text angehängt,
    # damit sie sie NENNEN kann statt eine zu erfinden.
    txt = build_sofia_text({"type": "urlaub", "end": "2026-07-15",
                            "note": "Die Vertretung übernimmt Frau Meier."})
    assert txt == ("Herr Müller ist im Urlaub und ab 15. Juli 2026 wieder erreichbar. "
                   "Die Vertretung übernimmt Frau Meier.")


def test_no_note_no_extra():
    txt = build_sofia_text({"type": "urlaub", "end": "2026-07-15"})
    assert txt == "Herr Müller ist im Urlaub und ab 15. Juli 2026 wieder erreichbar."


def test_blank_note_ignored():
    txt = build_sofia_text({"type": "urlaub", "end": "2026-07-15", "note": "   "})
    assert txt == "Herr Müller ist im Urlaub und ab 15. Juli 2026 wieder erreichbar."
