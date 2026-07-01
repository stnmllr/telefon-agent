"""FIBU-Handbücher (PDF) -> bereinigtes Markdown für die ElevenLabs KB.

Aufruf (cmd.exe, kein PowerShell, kein .exe-Shim):
    uv run python -m kb_convert
    uv run python -m kb_convert --source "c:\\profi\\Doku"

Wandelt die Whitelist-Handbücher nach ./kb_fibu/ (Pflicht) bzw.
./kb_fibu/optional/ (optional), erkennt vermutlich gescannte PDFs (OCR nötig)
und schreibt ./kb_fibu/REPORT.md. Scans landen NUR im Report, nicht im Upload-Satz.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import pymupdf
import pymupdf4llm

from kb_convert import core

DEFAULT_SOURCE = pathlib.Path(r"c:\profi\Doku")
OUT_DIR = pathlib.Path("kb_fibu")

# Basis-Dateinamen ohne .pdf
REQUIRED = [
    "Handbuch Fibu",
    "Handbuch OPos",
    "Handbuch Anbu",
    "Handbuch Kore",
    "Handbuch Reports",
    "Handbuch Buchungs-Bsp",
    "Handbuch Rebu",
    "Handbuch ABI",
    "Handbuch Chefinfo",
]
OPTIONAL = [
    "Handbuchergänzung_Schweiz",
    "MWSt 2024 Schweiz",
    "enventa.ebilanz_hinweise",
    "Handbuch GDPdU",
]


def measure(path: pathlib.Path) -> tuple[int, int]:
    """Seitenzahl + Roh-Zeichen der Textebene (für Scan-Heuristik)."""
    doc = pymupdf.open(path)
    try:
        pages = doc.page_count
        chars = sum(len(page.get_text()) for page in doc)
    finally:
        doc.close()
    return pages, chars


def convert_markdown(path: pathlib.Path) -> str:
    """PDF -> bereinigtes Markdown. Primär pymupdf4llm; Fallback markitdown."""
    try:
        chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True, show_progress=False)
        page_texts = [c["text"] for c in chunks]
        md = core.strip_boilerplate(page_texts)
        if md.strip():
            return md
    except Exception as exc:  # noqa: BLE001 — bewusst breit, Fallback folgt
        print(f"  pymupdf4llm fehlgeschlagen ({exc!r}), versuche markitdown …")

    try:
        from markitdown import MarkItDown
    except ImportError:
        raise RuntimeError(
            "pymupdf4llm lieferte keinen Text und markitdown ist nicht installiert "
            "(uv pip install markitdown)."
        )
    return MarkItDown().convert(str(path)).text_content


def process(name: str, dest_dir: pathlib.Path, source: pathlib.Path) -> dict | None:
    """Eine Datei verarbeiten. Gibt eine Report-Zeile zurück oder None bei BLOCKED."""
    pdf = source / f"{name}.pdf"
    if not pdf.exists():
        print(f"BLOCKED: Whitelist-Datei fehlt: {pdf}")
        return None

    pages, chars = measure(pdf)
    scanned = core.is_probably_scanned(chars, pages)
    row = {"name": pdf.name, "pages": pages, "chars": chars,
           "md_bytes": 0, "scanned": scanned}

    if scanned:
        cpp = (chars / pages) if pages else 0
        print(f"  [WARN] {pdf.name}: vermutlich gescannt ({cpp:.0f} Z./Seite) - "
              f"NICHT konvertiert, OCR noetig.")
        return row

    md = convert_markdown(pdf)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{core.slugify(name)}.md"
    out.write_text(md, encoding="utf-8")
    row["md_bytes"] = len(md.encode("utf-8"))
    print(f"  [ok] {pdf.name} -> {out} ({core._kb(row['md_bytes'])} KB, {pages} S.)")
    return row


def main(argv: list[str] | None = None) -> int:
    # cmd.exe-Konsole ist cp1252; Report-Datei bleibt UTF-8. stdout robust machen.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="FIBU-Handbücher -> Markdown für ElevenLabs KB")
    parser.add_argument("--source", type=pathlib.Path, default=DEFAULT_SOURCE,
                        help=f"PDF-Quellordner (Default: {DEFAULT_SOURCE})")
    parser.add_argument("--out", type=pathlib.Path, default=OUT_DIR,
                        help=f"Zielordner (Default: {OUT_DIR})")
    args = parser.parse_args(argv)

    source: pathlib.Path = args.source
    out_dir: pathlib.Path = args.out

    if not source.is_dir():
        print(f"BLOCKED: Quellordner existiert nicht: {source}")
        return 2

    # Vorab-Check: fehlen Pflicht-Dateien? -> STOP, nicht raten.
    missing = [n for n in REQUIRED if not (source / f"{n}.pdf").exists()]
    if missing:
        print("BLOCKED: Pflicht-Dateien fehlen im Quellordner:")
        for n in missing:
            print(f"  - {n}.pdf")
        return 2

    print(f"Quelle: {source}")
    print(f"== Pflicht ({len(REQUIRED)}) ==")
    required_rows = [process(n, out_dir, source) for n in REQUIRED]

    print(f"== Optional ({len(OPTIONAL)}) -> {out_dir / 'optional'} ==")
    optional_rows = []
    for n in OPTIONAL:
        if (source / f"{n}.pdf").exists():
            optional_rows.append(process(n, out_dir / "optional", source))
        else:
            print(f"  übersprungen (nicht vorhanden): {n}.pdf")

    req_ok = [r for r in required_rows if r is not None]
    opt_ok = [r for r in optional_rows if r is not None]

    # Report nur über den Upload-Satz (Pflicht) für die 20-MB-Prüfung;
    # optionale Dateien separat ausgewiesen.
    report = ["# KB-FIBU Konvertierungs-Report", "",
              f"Quelle: `{source}`", "",
              "## Pflicht-Handbücher (Upload-Satz)", "",
              core.build_report(req_ok)]
    if opt_ok:
        report += ["", "## Optionale Handbücher (separat, Stef entscheidet pro Datei)", "",
                   core.build_report(opt_ok)]

    scanned_req = [r["name"] for r in req_ok if r["scanned"]]
    if scanned_req:
        report += ["", "## ⚠️ BLOCKED / Aufmerksamkeit",
                   "Folgende **Pflicht**-Dateien sind vermutlich gescannt und wurden "
                   "NICHT konvertiert (OCR nötig):", ""]
        report += [f"- {n}" for n in scanned_req]

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "REPORT.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nReport: {report_path}")

    written = [r for r in req_ok if not r["scanned"]]
    total_mb = sum(r["md_bytes"] for r in written) / (1024 * 1024)
    print(f"Pflicht geschrieben: {len(written)}/{len(REQUIRED)} | "
          f"Markdown gesamt: {total_mb:.2f} MB ({'<' if total_mb < 20 else '>='} 20 MB)")
    if scanned_req:
        print(f"⚠️ BLOCKED: {len(scanned_req)} Pflicht-Datei(en) gescannt: {scanned_req}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
