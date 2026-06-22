from app.tools.phonebook import fuzzy_lookup, all_emails


def _nachnamen(matches):
    return sorted(m["nachname"] for m in matches)


def test_full_name_returns_only_best_match():
    # "Stefan Bär" matcht Bär auf beiden Tokens → nur Bär, NICHT Peters/Müller
    matches = fuzzy_lookup("Stefan Bär")
    assert _nachnamen(matches) == ["Bär"]


def test_firstname_only_returns_all_collisions():
    # reine Vornamen-Anfrage → alle phonetischen Kollisionen zur Disambiguierung
    matches = fuzzy_lookup("Stefan")
    nn = _nachnamen(matches)
    assert "Bär" in nn and "Peters" in nn and "Müller" in nn


def test_exact_lastname():
    matches = fuzzy_lookup("Schindler")
    assert _nachnamen(matches) == ["Schindler"]
    assert matches[0]["anrede"] == "Herr"
    assert matches[0]["durchwahl"] == "35"


def test_no_match_returns_empty():
    assert fuzzy_lookup("Xylophon") == []


def test_match_fields_present():
    m = fuzzy_lookup("Schindler")[0]
    assert set(m.keys()) == {"anrede", "vorname", "nachname", "email", "durchwahl", "beschreibung"}
    assert m["email"] == "Severin.Schindler@sopra-system.com"
    assert m["vorname"] == "Severin"


def test_all_emails_excludes_empty():
    emails = all_emails()
    assert "Severin.Schindler@sopra-system.com" in emails
    assert "" not in emails
    # "Zentrale" hat keine E-Mail → nicht enthalten
    assert all(e for e in emails)
