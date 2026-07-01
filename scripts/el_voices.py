"""Sucht Stimmen (eigene + Shared Library) für eine deutsche weibliche 'Sofia'.

  uv run python scripts/el_voices.py [suchbegriff]   (default: sofia)

Loggt den API-Key NICHT.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import httpx

BASE = "https://api.elevenlabs.io"
CURRENT = "cjVigY5qzO86Huf0OWal"


def _load_api_key() -> str | None:
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


def main(argv) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    q = (argv[0] if argv else "sofia").lower()
    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2

    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=60.0) as c:
        # Eigene Stimmen
        r = c.get("/v1/voices")
        own = r.json().get("voices", []) if r.status_code == 200 else []
        print(f"Eigene Stimmen: {len(own)}")
        for v in own:
            mark = "  <-- AKTUELL" if v.get("voice_id") == CURRENT else ""
            labels = v.get("labels", {})
            print(f"  {v.get('name'):20} {v.get('voice_id'):24} "
                  f"{labels.get('gender','?')}/{labels.get('language', labels.get('accent','?'))}{mark}")

        # Shared Library: deutsche weibliche, Name-Suche
        print(f"\nShared Library (gender=female, language=de, search='{q}'):")
        r = c.get("/v1/shared-voices",
                  params={"gender": "female", "language": "de", "search": q, "page_size": 30})
        if r.status_code != 200:
            print(f"  GET /v1/shared-voices -> {r.status_code} {r.text[:200]}")
        else:
            voices = r.json().get("voices", [])
            print(f"  Treffer: {len(voices)}")
            for v in voices:
                print(f"  {v.get('name'):20} {v.get('voice_id'):24} "
                      f"{v.get('gender','?')}/{v.get('language','?')}/{v.get('accent','?')}  "
                      f"uses={v.get('cloned_by_count','?')}  desc={str(v.get('descriptive',''))[:30]}")

        # Falls keine Sofia: zeig deutsche weibliche allgemein
        if r.status_code == 200 and not r.json().get("voices"):
            print("\n  Keine 'Sofia' — deutsche weibliche allgemein (Top nach Nutzung):")
            r2 = c.get("/v1/shared-voices",
                       params={"gender": "female", "language": "de", "page_size": 15,
                               "sort": "cloned_by_count"})
            for v in (r2.json().get("voices", []) if r2.status_code == 200 else []):
                print(f"  {v.get('name'):20} {v.get('voice_id'):24} "
                      f"{v.get('accent','?')}  uses={v.get('cloned_by_count','?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
