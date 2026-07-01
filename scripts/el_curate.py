"""Kuratiert das RAG-Set auf KEEP (Fibu, Opos, Abi, Buchungs Bsp) im 2-MB-Budget.

  uv run python scripts/el_curate.py

1. Löscht den e5-RAG-Index JEDES Docs, das NICHT in KEEP ist (gibt Budget frei).
2. Stößt RAG-Index für KEEP-Docs ohne 'succeeded'-Index an (Fibu, Opos).
3. Pollt bis alle KEEP-Docs succeeded.
4. Druckt RAG-Budget-Übersicht.

Loggt den API-Key NICHT. Danach separat scripts/el_link_kb.py ausführen.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

import httpx

BASE = "https://api.elevenlabs.io"
MODEL = "e5_mistral_7b_instruct"
MANIFEST = pathlib.Path("kb_fibu/upload_manifest.json")

KEEP = {
    "ybrSe11VGf3XKXAQDaEr": "Fibu",
    "Est2tHZnxasbz3l3d84d": "Opos",
    "LLjBvPfIjF5P8RfmNJ0u": "Abi",
    "GHrqFyPIXeyDG8GSXl9U": "Buchungs Bsp",
}


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


def _e5(c, doc_id):
    idx = c.get(f"/v1/convai/knowledge-base/{doc_id}/rag-index").json().get("indexes") or []
    e5 = [i for i in idx if i.get("model") == MODEL]
    return e5[0] if e5 else None


def _overview(c):
    o = c.get("/v1/convai/knowledge-base/rag-index").json()
    return o.get("total_used_bytes"), o.get("total_max_bytes")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    all_docs = {v["id"]: v["name"] for v in manifest.values()}

    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=120.0) as c:
        used, mx = _overview(c)
        print(f"Budget vorher: {used:,} / {mx:,} bytes")

        # 1) Nicht-KEEP-Indizes löschen
        print("\n-- Lösche Nicht-KEEP-Indizes --")
        for doc_id, name in all_docs.items():
            if doc_id in KEEP:
                continue
            e5 = _e5(c, doc_id)
            if not e5:
                continue
            r = c.delete(f"/v1/convai/knowledge-base/{doc_id}/rag-index/{e5['id']}")
            print(f"  DELETE {name[:30]:30} [{e5.get('status')}] -> {r.status_code}")
            if r.status_code not in (200, 204):
                print("    Body:", r.text[:200])

        used, mx = _overview(c)
        print(f"\nBudget nach Löschen: {used:,} / {mx:,} bytes  (frei: {mx - used:,})")

        # 2) KEEP-Docs ohne succeeded-Index neu anstoßen
        print("\n-- Index für KEEP-Docs --")
        for doc_id, name in KEEP.items():
            e5 = _e5(c, doc_id)
            if e5 and e5.get("status") == "succeeded":
                print(f"  {name}: schon succeeded")
                continue
            r = c.post(f"/v1/convai/knowledge-base/{doc_id}/rag-index", json={"model": MODEL})
            print(f"  POST {name} -> {r.status_code} {r.json().get('status')}")
            if r.status_code not in (200, 201):
                print("    Body:", r.text[:300])

        # 3) Poll
        print("\n-- Warte auf succeeded --")
        waited, every, mxwait = 0, 15, 540
        while True:
            sts = {n: (_e5(c, d) or {}).get("status", "missing") for d, n in KEEP.items()}
            ok = sum(1 for v in sts.values() if v == "succeeded")
            print(f"  [{waited:3}s] {sts}")
            if all(v in ("succeeded", "failed") for v in sts.values()):
                if any(v == "failed" for v in sts.values()):
                    print("FAILED:", {n: v for n, v in sts.items() if v == "failed"})
                    return 1
                break
            if waited >= mxwait:
                print("TIMEOUT"); return 2
            time.sleep(every); waited += every

        used, mx = _overview(c)
        print(f"\nFertig. Budget: {used:,} / {mx:,} bytes")
    print("\nNächster Schritt: uv run python scripts/el_link_kb.py agent_2101kvt9zh93ekmt9j6vgpdbzsdy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
