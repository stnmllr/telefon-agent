"""Lädt die konvertierten FIBU-Markdowns als Text-Dokumente in die ElevenLabs
Knowledge Base (verifizierter Endpoint POST /v1/convai/knowledge-base/text).

Aufruf (cmd.exe, kein PowerShell, kein .exe-Shim):
    uv run python -m kb_upload --dry-run        # zeigt nur, was passieren würde
    uv run python -m kb_upload                  # Pflicht-Handbücher hochladen
    uv run python -m kb_upload --optional       # + optionale Handbücher
    uv run python -m kb_upload --force           # bereits hochgeladene erneut laden

Key: ELEVENLABS_API_KEY (aus Umgebung oder .env). Wird NICHT geloggt.
Manifest: kb_fibu/upload_manifest.json (Idempotenz; Mapping Datei -> document_id).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import httpx

from kb_upload import core

KB_DIR = pathlib.Path("kb_fibu")
MANIFEST = KB_DIR / "upload_manifest.json"
DEFAULT_BASE = "https://api.elevenlabs.io"
TEXT_ENDPOINT = "/v1/convai/knowledge-base/text"


def _load_api_key() -> str | None:
    import os
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key
    env = pathlib.Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def _save_manifest(manifest: dict) -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _collect_files(include_optional: bool) -> list[str]:
    files = sorted(p.name for p in KB_DIR.glob("*.md") if p.name != "REPORT.md")
    if include_optional:
        files += [f"optional/{p.name}" for p in sorted((KB_DIR / "optional").glob("*.md"))]
    return files


def _upload_one(client: httpx.Client, rel: str) -> dict:
    text = (KB_DIR / rel).read_text(encoding="utf-8")
    name = core.document_name(rel)
    resp = client.post(TEXT_ENDPOINT, json={"name": name, "text": text})
    resp.raise_for_status()
    data = resp.json()
    return {"id": data["id"], "name": data.get("name", name)}


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="FIBU-Markdowns -> ElevenLabs KB (Text)")
    parser.add_argument("--dry-run", action="store_true", help="nur anzeigen, nichts hochladen")
    parser.add_argument("--optional", action="store_true", help="optionale Handbücher mitnehmen")
    parser.add_argument("--force", action="store_true", help="bereits hochgeladene erneut laden")
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="z.B. EU-Residency-Endpoint")
    args = parser.parse_args(argv)

    if not KB_DIR.is_dir():
        print(f"BLOCKED: {KB_DIR} fehlt — erst `uv run python -m kb_convert` ausführen.")
        return 2

    manifest = _load_manifest()
    all_files = _collect_files(args.optional)
    pending = core.select_pending(all_files, manifest, force=args.force)

    print(f"KB-Dir: {KB_DIR} | gesamt: {len(all_files)} | offen: {len(pending)} "
          f"| bereits im Manifest: {len(manifest)}")
    for rel in pending:
        print(f"  -> {rel}   (Name: {core.document_name(rel)})")
    skipped = [f for f in all_files if f not in pending]
    if skipped and not args.force:
        print(f"  übersprungen (im Manifest): {len(skipped)} — mit --force erneut laden")

    if args.dry_run:
        print("\n[dry-run] Kein Upload ausgeführt.")
        return 0

    if not pending:
        print("\nNichts zu tun.")
        return 0

    api_key = _load_api_key()
    if not api_key:
        print("\nBLOCKED: ELEVENLABS_API_KEY nicht gesetzt (Umgebung oder .env). "
              "Key im ElevenLabs-Dashboard erzeugen und in .env eintragen.")
        return 2

    headers = {"xi-api-key": api_key}
    uploaded = 0
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=120.0) as client:
        for rel in pending:
            try:
                entry = _upload_one(client, rel)
            except httpx.HTTPStatusError as exc:
                print(f"  FEHLER {rel}: HTTP {exc.response.status_code} {exc.response.text[:200]}")
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"  FEHLER {rel}: {exc!r}")
                continue
            manifest = core.merge_manifest(manifest, rel, entry)
            _save_manifest(manifest)  # nach jedem Upload sichern (resume-fest)
            uploaded += 1
            print(f"  [ok] {rel} -> document_id={entry['id']}")

    print(f"\nHochgeladen: {uploaded}/{len(pending)} | Manifest: {MANIFEST}")
    print("Nächster Schritt (separat): Dokumente am Agenten verknüpfen + RAG aktivieren, "
          "sobald der Agent konfiguriert ist.")
    return 0 if uploaded == len(pending) else 1


if __name__ == "__main__":
    sys.exit(main())
