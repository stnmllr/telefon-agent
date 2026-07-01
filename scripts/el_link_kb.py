"""Hängt die FIBU-KB-Docs an den Agenten (usage_mode auto) + aktiviert RAG.

  uv run python scripts/el_link_kb.py <agent_id>

- Liest IDs/Namen aus kb_fibu/upload_manifest.json (idempotent: keine Dubletten).
- Voller conversation_config-Round-Trip; ändert NUR prompt.knowledge_base + prompt.rag.enabled.
- GET vorher/nachher -> Deep-Diff. Loggt den API-Key NICHT.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys

import httpx

BASE = "https://api.elevenlabs.io"
MANIFEST = pathlib.Path("kb_fibu/upload_manifest.json")
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


def _flat(d, p=""):
    o = {}
    if isinstance(d, dict):
        for k, v in d.items():
            o.update(_flat(v, f"{p}.{k}" if p else k))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            o.update(_flat(v, f"{p}[{i}]"))
    else:
        o[p] = d
    return o


def main(argv) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if not argv:
        print("Usage: el_link_kb.py <agent_id>"); return 2
    agent_id = argv[0]
    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2
    if not MANIFEST.exists():
        print(f"BLOCKED: {MANIFEST} fehlt."); return 2
    OUT.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    want = {v["id"]: v["name"] for v in manifest.values()}  # id -> name
    print(f"Manifest: {len(want)} Dokumente")

    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=60.0) as c:
        r = c.get(f"/v1/convai/agents/{agent_id}")
        print(f"GET agent -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:400]); return 1
        agent = r.json()
        before = copy.deepcopy(agent)
        (OUT / "agent_before.json").write_text(
            json.dumps(agent, indent=2, ensure_ascii=False), encoding="utf-8")

        # Nur Docs anhängen, deren RAG-Index 'succeeded' ist (sonst 422 rag_index_not_ready).
        ready, skipped = {}, {}
        for doc_id, name in want.items():
            idx = c.get(f"/v1/convai/knowledge-base/{doc_id}/rag-index").json().get("indexes") or []
            e5 = [i for i in idx if i.get("model") == "e5_mistral_7b_instruct"]
            st = e5[0]["status"] if e5 else "missing"
            (ready if st == "succeeded" else skipped)[doc_id] = (name, st)
        if skipped:
            print(f"ÜBERSPRUNGEN (Index nicht succeeded): "
                  + ", ".join(f"{n} [{s}]" for n, s in skipped.values()))

        prompt = agent["conversation_config"]["agent"]["prompt"]
        existing = prompt.get("knowledge_base") or []
        have_ids = {e.get("id") for e in existing}
        for doc_id, (name, _st) in ready.items():
            if doc_id in have_ids:
                continue
            existing.append({"type": "text", "name": name, "id": doc_id, "usage_mode": "auto"})
        prompt["knowledge_base"] = existing
        prompt.setdefault("rag", {})["enabled"] = True
        # GET expandiert tool_ids zu read-only prompt.tools; beim PATCH darf nur
        # EINES von beiden gesendet werden (sonst 400 both_tools_and_tool_ids).
        if prompt.get("tool_ids"):
            prompt.pop("tools", None)
        print(f"knowledge_base nachher: {len(existing)} Einträge "
              f"({len(ready)} ready); rag.enabled=True")

        r = c.patch(f"/v1/convai/agents/{agent_id}",
                    json={"conversation_config": agent["conversation_config"]})
        print(f"PATCH agent -> {r.status_code}")
        if r.status_code not in (200, 201):
            print("FEHLER:", r.text[:800]); return 1

        after = c.get(f"/v1/convai/agents/{agent_id}").json()
        (OUT / "agent_after.json").write_text(
            json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")

    ap = after["conversation_config"]["agent"]["prompt"]
    print(f"\n--- Nachher: knowledge_base = {len(ap.get('knowledge_base') or [])} Docs; "
          f"rag.enabled = {ap.get('rag', {}).get('enabled')} ---")

    fb, fa = _flat(before["conversation_config"]), _flat(after["conversation_config"])
    ch = [k for k in sorted(set(fb) | set(fa)) if fb.get(k) != fa.get(k)]
    print(f"\n--- Deep-Diff conversation_config: {len(ch)} Felder geändert ---")
    for k in ch[:60]:
        print(f"  {k}: {fb.get(k)!r} -> {fa.get(k)!r}")
    if len(ch) > 60:
        print(f"  … +{len(ch) - 60} weitere")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
