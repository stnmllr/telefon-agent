"""Abwesenheits-Text für Sofia (Pure-Core).

Windows-/Locale-sicher: festes deutsches Monats-Array statt strftime('%-d %B').
"""
from datetime import datetime

_MONTHS_DE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
              "Juli", "August", "September", "Oktober", "November", "Dezember"]

_PHRASES = {
    "urlaub": "im Urlaub",
    "meeting": "im Meeting",
    "abwesend": "derzeit abwesend",
    "dienstreise": "auf Dienstreise",
}


def build_sofia_text(absence: dict) -> str:
    atype = absence.get("type", "abwesend")
    phrase = _PHRASES.get(atype, "derzeit abwesend")
    end = absence.get("end", "")

    if atype == "meeting":
        time_part = end.split("T")[1][:5] if "T" in end else end
        if time_part:
            return f"Herr Müller ist gerade {phrase} und ab {time_part} Uhr wieder erreichbar."
        return f"Herr Müller ist gerade {phrase}."

    date_part = end.split("T")[0]
    try:
        d = datetime.fromisoformat(date_part)
        formatted = f"{d.day}. {_MONTHS_DE[d.month]} {d.year}"
        return f"Herr Müller ist {phrase} und ab {formatted} wieder erreichbar."
    except (ValueError, IndexError):
        return f"Herr Müller ist {phrase}."
