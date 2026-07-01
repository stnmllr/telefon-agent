"""Empfänger-Routing (Pure-Core): Defaults, Merge mit Overrides, Override-Guard."""

DEFAULT_ROUTING: dict[str, str] = {
    "erp": "erp-support@sopra-system.com",
    "evs": "evs-support@sopra-system.com",
    "hr": "hr-support@sopra-system.com",
    "it": "it-support@sopra-system.com",
    "verwaltung": "Stephan.Mueller@sopra-system.com",
    "nachricht": "Stephan.Mueller@sopra-system.com",
    "fibu": "Stephan.Mueller@sopra-system.com",
}


def merge_routing(overrides: dict | None) -> dict:
    """Defaults überlagert durch valide Overrides.

    - nur Keys aus DEFAULT_ROUTING (unbekannte/`phonebook` ignoriert),
    - leeres Override -> Code-Default (statt '').
    """
    merged = dict(DEFAULT_ROUTING)
    if overrides:
        for key, value in overrides.items():
            if key in DEFAULT_ROUTING and isinstance(value, str) and value.strip():
                merged[key] = value.strip()
    return merged


def resolve_recipient(category: str, routing: dict) -> str | None:
    """Empfänger für eine Kategorie; `phonebook` ist override-only -> None.

    Case-insensitiv: das ElevenLabs-LLM schickt die Kategorie gern
    großgeschrieben ("Fibu"), die Routing-Keys sind aber klein.
    """
    if not isinstance(category, str):
        return None
    return routing.get(category.strip().lower())


def validate_override(email: str, valid_emails: set[str]) -> bool:
    """True nur, wenn email exakt einer (nicht-leeren) Telefonbuch-Mail entspricht."""
    return bool(email and email.strip()) and email.strip() in valid_emails
