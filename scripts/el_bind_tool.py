"""Bindet call_id/caller_number eines Tools an Dynamic Variables (read-modify-write).

  uv run python scripts/el_bind_tool.py <tool_id>

Union-Regel: pro Property nur EINES von description/dynamic_variable/
is_system_provided/constant_value/is_omitted gesetzt -> beim Binden description leeren.
Loggt den API-Key NICHT. Schreibt <id>_before/after.json nach EL_OUT_DIR und difft.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import httpx

BASE = "https://api.elevenlabs.io"
BINDINGS = {"call_id": "system__conversation_id", "caller_number": "system__caller_id"}
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


def _props(obj: dict) -> dict:
    return obj["tool_config"]["api_schema"]["request_body_schema"]["properties"]


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
        print("Usage: el_bind_tool.py <tool_id>"); return 2
    tool_id = argv[0]

    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {"xi-api-key": key}

    with httpx.Client(base_url=BASE, headers=headers, timeout=60.0) as c:
        r = c.get(f"/v1/convai/tools/{tool_id}")
        print(f"GET tool -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:400]); return 1
        before = r.json()
        name = before["tool_config"]["name"]
        before_snapshot = json.loads(json.dumps(before))  # tiefe Kopie zum Diffen
        (OUT / f"{name}_before.json").write_text(
            json.dumps(before, indent=2, ensure_ascii=False), encoding="utf-8")

        props = _props(before)
        for field, var in BINDINGS.items():
            if field not in props:
                print(f"BLOCKED: Property '{field}' fehlt."); return 1
            p = props[field]
            p["dynamic_variable"] = var
            p["description"] = ""
            p["is_system_provided"] = False
            p["constant_value"] = ""
            p["is_omitted"] = False
        print(f"Tool '{name}' geplant:", {f: props[f]["dynamic_variable"] for f in BINDINGS})

        r = c.patch(f"/v1/convai/tools/{tool_id}", json={"tool_config": before["tool_config"]})
        print(f"PATCH tool -> {r.status_code}")
        if r.status_code not in (200, 201):
            print("FEHLER:", r.text[:600]); return 1

        after = c.get(f"/v1/convai/tools/{tool_id}").json()
        (OUT / f"{name}_after.json").write_text(
            json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")

    ap = _props(after)
    print("\n--- Gespeichert (nachher) ---")
    for field in BINDINGS:
        p = ap.get(field, {})
        print(f"  {field}: dynamic_variable={p.get('dynamic_variable')!r}  "
              f"is_system_provided={p.get('is_system_provided')!r}")

    fb, fa = _flat(before_snapshot["tool_config"]), _flat(after["tool_config"])
    ch = [k for k in sorted(set(fb) | set(fa)) if fb.get(k) != fa.get(k)]
    print(f"\n--- Diff before vs after: {len(ch)} Felder ---")
    for k in ch:
        print(f"  {k}: {fb.get(k)!r} -> {fa.get(k)!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
