"""Pure-Logic-Kern des KB-Konvertierungs-Tools — kein I/O, direkt unit-testbar.

Enthält: Slug-Bildung, Scan-Heuristik, Boilerplate-Bereinigung, Report-Tabelle.
"""

from __future__ import annotations

import math
import re

# --- Slug ------------------------------------------------------------------

_UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
})


def slugify(name: str) -> str:
    """Sprechender, dateisystem-sicherer Slug. Umlaute werden transkribiert,
    alles Nicht-Alphanumerische zu '-' verschmolzen, lowercase."""
    s = name.translate(_UMLAUT_MAP).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# --- Scan-Heuristik --------------------------------------------------------

def is_probably_scanned(total_chars: int, pages: int, threshold: int = 100) -> bool:
    """True, wenn die Textebene zu dünn ist (vermutlich gescannt, OCR nötig).
    Misst durchschnittliche Zeichen/Seite gegen ``threshold``."""
    if pages <= 0:
        return True
    return (total_chars / pages) < threshold


# --- Boilerplate-Bereinigung ----------------------------------------------

_PAGE_NUMBER_RE = re.compile(
    r"^[-–\s]*(seite\s+)?\d+(\s*(/|von)\s*\d+)?[-–\s]*$",
    re.IGNORECASE,
)


def is_page_number_line(line: str) -> bool:
    """True für reine Seitenzahl-Zeilen wie '12', '- 12 -', 'Seite 5 von 20'."""
    return bool(_PAGE_NUMBER_RE.match(line.strip()))


def strip_boilerplate(
    pages: list[str],
    min_repeat_ratio: float = 0.6,
    max_boiler_len: int = 80,
) -> str:
    """Entfernt wiederkehrende Kopf-/Fußzeilen und reine Seitenzahlen.

    Konservativ: Wiederholungs-Erkennung greift erst ab 3 Seiten. Eine kurze
    Zeile gilt als Boilerplate, wenn sie (normalisiert) auf >= ``min_repeat_ratio``
    der Seiten vorkommt. Im Zweifel wird Inhalt roh gelassen.
    """
    num_pages = len(pages)
    boiler: set[str] = set()

    if num_pages >= 3:
        presence: dict[str, int] = {}
        for page in pages:
            seen_on_page = {
                ln.strip() for ln in page.splitlines() if ln.strip()
            }
            for norm in seen_on_page:
                presence[norm] = presence.get(norm, 0) + 1
        cutoff = max(2, math.ceil(min_repeat_ratio * num_pages))
        boiler = {
            norm for norm, cnt in presence.items()
            if cnt >= cutoff and len(norm) <= max_boiler_len
        }

    cleaned_pages: list[str] = []
    for page in pages:
        kept = [
            ln for ln in page.splitlines()
            if ln.strip() not in boiler and not is_page_number_line(ln)
        ]
        cleaned_pages.append("\n".join(kept).strip())

    return "\n\n".join(p for p in cleaned_pages if p)


# --- Report ----------------------------------------------------------------

def _kb(num_bytes: int) -> float:
    return round(num_bytes / 1024, 1)


def build_report(rows: list[dict], limit_mb: int = 20) -> str:
    """Markdown-Report: eine Zeile je Datei + Summenzeile mit Limit-Hinweis.

    Jede Zeile: ``{name, pages, chars, md_bytes, scanned}``.
    """
    header = (
        "| Datei | Seiten | Zeichen | .md-Größe (KB) | gescannt? |\n"
        "|---|---:|---:|---:|---|"
    )
    lines = [header]
    total_chars = 0
    total_bytes = 0
    for r in rows:
        total_chars += r["chars"]
        total_bytes += r["md_bytes"]
        flag = "ja ⚠️" if r["scanned"] else "nein"
        lines.append(
            f"| {r['name']} | {r['pages']} | {r['chars']:,} | "
            f"{_kb(r['md_bytes'])} | {flag} |".replace(",", ".")
        )

    total_mb = total_bytes / (1024 * 1024)
    status = "unter" if total_mb < limit_mb else "ÜBER"
    lines.append(
        f"| **Gesamt** | — | {total_chars:,} | {_kb(total_bytes)} | — |".replace(",", ".")
    )
    lines.append("")
    lines.append(
        f"**Summe:** {total_mb:.2f} MB Markdown ({total_chars:,} Zeichen) — "
        f"**{status} dem 20 MB-Limit.**".replace(",", ".")
    )
    return "\n".join(lines)
