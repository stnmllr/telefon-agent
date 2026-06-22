"""Telefonbuch-Lookup mit phonetischem Matching (Kölner Phonetik).

Pure-Core: liest nur telefonbuch.csv, kein sonstiges I/O.
KEINE Stefan→Stephan-Normalisierung — die rohen Tokens werden phonetisch
gegen alle Einträge gematcht, alle Maximal-Treffer zurückgegeben.
"""
import csv
import os
import unicodedata
from app.tools.phonetik import koelner_phonetik

_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "telefonbuch.csv")


def _rows():
    with open(_CSV_PATH, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def _split_name(name: str) -> tuple[str, str]:
    """'Nachname, Vorname' -> (nachname, vorname). Ohne Komma: (name, '')."""
    if "," in name:
        nach, _, vor = name.partition(",")
        return nach.strip(), vor.strip()
    return name.strip(), ""


def _query_tokens(text: str) -> list[str]:
    norm = unicodedata.normalize("NFC", text).casefold()
    return [t for t in norm.replace(",", " ").split() if len(t) > 2]


def all_emails() -> set[str]:
    return {r["Email"].strip() for r in _rows() if r.get("Email", "").strip()}


def fuzzy_lookup(name: str) -> list[dict]:
    query_codes = [c for c in (koelner_phonetik(t) for t in _query_tokens(name)) if c]
    if not query_codes:
        return []

    scored = []
    for r in _rows():
        nach, vor = _split_name(r["Name"])
        entry_codes = {koelner_phonetik(t) for t in (nach, vor) if t}
        entry_codes.discard("")
        hits = sum(1 for qc in query_codes if qc in entry_codes)
        if hits > 0:
            scored.append((hits, r, nach, vor))

    if not scored:
        return []

    best = max(h for h, *_ in scored)
    result = []
    for hits, r, nach, vor in scored:
        if hits == best:
            result.append({
                "anrede": r.get("Anrede", "").strip(),
                "vorname": vor,
                "nachname": nach,
                "email": r.get("Email", "").strip(),
                "durchwahl": r.get("Durchwahl", "").strip(),
                "beschreibung": r.get("Beschreibung", "").strip(),
            })
    return result
