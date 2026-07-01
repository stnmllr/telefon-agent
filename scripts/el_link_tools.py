"""Hängt die Action-Tools an den Agenten (prompt.tool_ids).

  uv run python scripts/el_link_tools.py <agent_id>

- Löst die gewünschten Tools per NAME aus der Live-Tools-Liste auf (keine
  hartkodierten IDs). check_absence wird bewusst NICHT angehängt — das ist ein
  Conversation-Initiation-Webhook, kein aufrufbares Tool.
- Voller conversation_config-Round-Trip; ändert NUR prompt.tool_ids
  (idempotent: keine Dubletten). GET vorher/nachher -> Deep-Diff.
- Loggt den API-Key NICHT.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys

import httpx

BASE = "https://api.elevenlabs.io"
OUT = pathlib.Path(os.environ.get("EL_OUT_DIR", "scratchpad_el"))

# Genau diese drei Action-Tools sollen am Agenten hängen.
WANT_NAMES = ["lookup_phonebook", "create_ticket", "send_email"]


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
        print("Usage: el_link_tools.py <agent_id>"); return 2
    agent_id = argv[0]
    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2
    OUT.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=60.0) as c:
        # 1) Live-Tools holen, Namen -> ID auflösen.
        r = c.get("/v1/convai/tools")
        print(f"GET tools -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:400]); return 1
        raw = r.json()
        items = raw.get("tools", raw) if isinstance(raw, dict) else raw
        by_name = {}
        for t in items:
            tc = t.get("tool_config", t)
            name = tc.get("name") or t.get("name")
            tid = t.get("id") or t.get("tool_id")
            by_name[name] = tid
        print(f"  Workspace-Tools: " + ", ".join(f"{n}={i}" for n, i in by_name.items()))

        want_ids = []
        for name in WANT_NAMES:
            tid = by_name.get(name)
            if not tid:
                print(f"BLOCKED: Tool '{name}' nicht im Workspace gefunden."); return 1
            want_ids.append(tid)

        # 2) Agent holen.
        r = c.get(f"/v1/convai/agents/{agent_id}")
        print(f"GET agent -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:400]); return 1
        agent = r.json()
        before = copy.deepcopy(agent)
        (OUT / "agent_before.json").write_text(
            json.dumps(agent, indent=2, ensure_ascii=False), encoding="utf-8")

        prompt = agent["conversation_config"]["agent"]["prompt"]
        existing = list(prompt.get("tool_ids") or [])
        merged = list(existing)
        for tid in want_ids:
            if tid not in merged:
                merged.append(tid)
        prompt["tool_ids"] = merged
        # Inline-tools-Feld leeren, falls vorhanden (tool_ids ist die kanonische Quelle).
        if prompt.get("tools"):
            print(f"  Hinweis: inline prompt.tools ({len(prompt['tools'])}) bleibt unverändert.")
        print(f"  tool_ids vorher: {existing}")
        print(f"  tool_ids nachher: {merged}")

        # 3) PATCH.
        r = c.patch(f"/v1/convai/agents/{agent_id}",
                    json={"conversation_config": agent["conversation_config"]})
        print(f"PATCH agent -> {r.status_code}")
        if r.status_code not in (200, 201):
            print("FEHLER:", r.text[:800]); return 1

        after = c.get(f"/v1/convai/agents/{agent_id}").json()
        (OUT / "agent_after.json").write_text(
            json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")

    ap = after["conversation_config"]["agent"]["prompt"]
    print(f"\n--- Nachher: tool_ids = {ap.get('tool_ids')} ---")

    fb, fa = _flat(before["conversation_config"]), _flat(after["conversation_config"])
    ch = [k for k in sorted(set(fb) | set(fa)) if fb.get(k) != fa.get(k)]
    print(f"\n--- Deep-Diff conversation_config: {len(ch)} Felder geändert ---")
    for k in ch[:60]:
        print(f"  {k}: {fb.get(k)!r} -> {fa.get(k)!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
