import csv
import os
from typing import Optional

_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "telefonbuch.csv")


def lookup(name: str) -> Optional[dict]:
    """Sucht einen Eintrag im Telefonbuch nach Name (case-insensitive, Teilstring-Suche).

    Returns:
        {"name": ..., "durchwahl": ..., "beschreibung": ..., "email": ...} oder None
    """
    needle = name.strip().lower()
    with open(_CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if needle in row["Name"].lower():
                return {
                    "name": row["Name"],
                    "durchwahl": row["Durchwahl"],
                    "beschreibung": row["Beschreibung"],
                    "email": row["Email"],
                }
    return None


def find_in_text(text: str) -> Optional[dict]:
    """Durchsucht den gesamten Text nach einem bekannten Namen aus dem Telefonbuch.

    Nützlich um in einer Freitext-Nutzereingabe einen Telefonbucheintrag zu erkennen.

    Returns:
        {"name": ..., "durchwahl": ..., "beschreibung": ..., "email": ...} oder None
    """
    text_lower = text.lower()
    with open(_CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            # Prüfe Nachname (Teil vor dem Komma) und Vorname einzeln
            name = row["Name"]
            parts = [p.strip().lower() for p in name.replace(",", " ").split()]
            if any(len(p) > 3 and p in text_lower for p in parts):
                return {
                    "name": name,
                    "durchwahl": row["Durchwahl"],
                    "beschreibung": row["Beschreibung"],
                    "email": row["Email"],
                }
    return None


def lookup_by_description(beschreibung: str) -> Optional[dict]:
    """Sucht einen Eintrag im Telefonbuch nach der Beschreibungs-Spalte
    (case-insensitive, Teilstring-Suche).

    Beispiel: lookup_by_description("ERP NUG Support") → ERP NUG Support-Eintrag

    Returns:
        {"name": ..., "durchwahl": ..., "beschreibung": ..., "email": ...} oder None
    """
    needle = beschreibung.strip().lower()
    with open(_CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if needle in row["Beschreibung"].lower():
                return {
                    "name": row["Name"],
                    "durchwahl": row["Durchwahl"],
                    "beschreibung": row["Beschreibung"],
                    "email": row["Email"],
                }
    return None
