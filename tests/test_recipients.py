from app.tools.recipients import (
    DEFAULT_ROUTING, merge_routing, resolve_recipient, validate_override,
)


def test_fibu_default_is_verwaltung_address():
    assert DEFAULT_ROUTING["fibu"] == "Stephan.Mueller@sopra-system.com"


def test_phonebook_not_in_defaults():
    assert "phonebook" not in DEFAULT_ROUTING


def test_override_wins():
    merged = merge_routing({"erp": "neu@sopra-system.com"})
    assert merged["erp"] == "neu@sopra-system.com"


def test_empty_override_falls_back_to_default():
    merged = merge_routing({"erp": "   "})
    assert merged["erp"] == DEFAULT_ROUTING["erp"]


def test_unknown_key_ignored():
    merged = merge_routing({"unsinn": "x@y.de"})
    assert "unsinn" not in merged


def test_phonebook_override_ignored():
    merged = merge_routing({"phonebook": "x@y.de"})
    assert "phonebook" not in merged


def test_resolve_phonebook_is_none():
    assert resolve_recipient("phonebook", DEFAULT_ROUTING) is None


def test_resolve_recipient_case_insensitive():
    # ElevenLabs-LLM schickt die Kategorie großgeschrieben ("Fibu"), die
    # Routing-Keys sind aber klein. Das darf den Empfänger nicht auf None kippen.
    assert resolve_recipient("Fibu", DEFAULT_ROUTING) == "Stephan.Mueller@sopra-system.com"
    assert resolve_recipient("FIBU", DEFAULT_ROUTING) == "Stephan.Mueller@sopra-system.com"
    assert resolve_recipient("ERP", DEFAULT_ROUTING) == DEFAULT_ROUTING["erp"]
    assert resolve_recipient("  Hr  ", DEFAULT_ROUTING) == DEFAULT_ROUTING["hr"]


def test_resolve_unknown_category_still_none():
    assert resolve_recipient("Quatsch", DEFAULT_ROUTING) is None
    assert resolve_recipient("Phonebook", DEFAULT_ROUTING) is None


def test_validate_override():
    valid = {"a@b.de", "c@d.de"}
    assert validate_override("a@b.de", valid) is True
    assert validate_override("halluziniert@x.de", valid) is False
    assert validate_override("", valid) is False
