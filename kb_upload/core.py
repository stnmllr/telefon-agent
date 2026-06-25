"""Pure-Logic-Kern des KB-Upload-Tools — kein I/O, direkt unit-testbar."""

from __future__ import annotations

import os

NAME_PREFIX = "FIBU"


def document_name(md_filename: str) -> str:
    """Sprechender KB-Dokumentname aus dem Markdown-Dateinamen.

    'handbuch-fibu.md' -> 'FIBU – Handbuch Fibu'. Etwaiger Unterordner-Pfad
    (z.B. 'optional/...') wird ignoriert.
    """
    stem = os.path.basename(md_filename).removesuffix(".md")
    pretty = stem.replace("-", " ").title()
    return f"{NAME_PREFIX} – {pretty}"


def select_pending(files: list[str], manifest: dict, force: bool) -> list[str]:
    """Welche Dateien hochgeladen werden. Ohne ``force`` werden bereits im
    Manifest verzeichnete Dateien übersprungen (Idempotenz)."""
    if force:
        return list(files)
    return [f for f in files if f not in manifest]


def merge_manifest(manifest: dict, filename: str, entry: dict) -> dict:
    """Neue/aktualisierte Manifest-Map zurückgeben, ohne ``manifest`` zu mutieren."""
    out = dict(manifest)
    out[filename] = entry
    return out
