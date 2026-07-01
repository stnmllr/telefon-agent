"""RAG-Index der FIBU-Docs: Status abfragen und (optional) anstoßen.

  uv run python scripts/el_rag_index.py status     # nur GET-Status aller Docs
  uv run python scripts/el_rag_index.py trigger    # POST rag-index (Modell e5)
  uv run python scripts/el_rag_index.py wait       # pollt bis alle succeeded/failed

Liest IDs aus kb_fibu/upload_manifest.json. Loggt den API-Key NICHT.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

import httpx

BASE = "https://api.elevenlabs.io"
MANIFEST = pathlib.Path("kb_fibu/upload_manifest.json")
MODEL = "e5_mistral_7b_instruct"
OUT = pathlib.Path(os.environ.get("EL_OUT_DIR", "scratchpad_el"))


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


def _doc_status(c, doc_id) -> tuple[str, float]:
    r = c.get(f"/v1/convai/knowledge-base/{doc_id}/rag-index")
    idx = (r.json().get("indexes") or []) if r.status_code == 200 else []
    e5 = [i for i in idx if i.get("model") == MODEL]
    if not e5:
        return "missing", 0.0
    return e5[0].get("status", "?"), e5[0].get("progress_percentage", 0.0)


def _wait(key, docs, max_secs: int = 540, every: int = 15) -> int:
    done_states = {"succeeded", "failed"}
    waited = 0
    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=60.0) as c:
        while True:
            states = {}
            for doc_id, name in docs:
                st, pct = _doc_status(c, doc_id)
                states[name] = (st, pct)
            pending = {n: v for n, v in states.items() if v[0] not in done_states}
            ok = sum(1 for v in states.values() if v[0] == "succeeded")
            failed = [n for n, v in states.items() if v[0] == "failed"]
            print(f"[{waited:3}s] succeeded={ok}/{len(docs)}  "
                  f"pending={len(pending)}  failed={len(failed)}")
            if not pending:
                if failed:
                    print("FAILED:", failed)
                    return 1
                print("\nAlle Indizes succeeded.")
                return 0
            if waited >= max_secs:
                print("\nTIMEOUT — noch offen:")
                for n, (st, pct) in pending.items():
                    print(f"  {n[:34]:34} {st} {pct:.0f}%")
                return 2
            time.sleep(every)
            waited += every


def main(argv) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    mode = argv[0] if argv else "status"
    if mode not in ("status", "trigger", "wait"):
        print("Usage: el_rag_index.py [status|trigger|wait]"); return 2
    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    docs = [(v["id"], v["name"]) for v in manifest.values()]

    if mode == "wait":
        return _wait(key, docs)

    OUT.mkdir(parents=True, exist_ok=True)
    dump = {}
    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=120.0) as c:
        for doc_id, name in docs:
            path = f"/v1/convai/knowledge-base/{doc_id}/rag-index"
            if mode == "trigger":
                r = c.post(path, json={"model": MODEL})
                action = "POST"
            else:
                r = c.get(path)
                action = "GET"
            body = None
            try:
                body = r.json()
            except Exception:
                body = r.text[:200]
            dump[doc_id] = {"name": name, "status_code": r.status_code, "body": body}
            # kurze Zusammenfassung
            summ = body
            if isinstance(body, dict):
                summ = {k: body.get(k) for k in ("status", "progress_percentage", "model",
                                                 "document_model_index_usage") if k in body}
                if "indexes" in body:
                    summ["indexes"] = body["indexes"]
            print(f"{action} {name[:34]:34} -> {r.status_code}  {summ}")

    (OUT / f"rag_index_{mode}.json").write_text(
        json.dumps(dump, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDump: {OUT / f'rag_index_{mode}.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
