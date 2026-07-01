"""Round-Trip-Test: bindet send_email.call_id/caller_number an Dynamic Variables.

Ablauf (nur EIN Tool: send_email):
  1. GET aktuelles tool_config
  2. call_id -> system__conversation_id, caller_number -> system__caller_id
  3. PATCH /v1/convai/tools/{id} mit vollem tool_config
  4. GET zurück, zeige was ElevenLabs gespeichert hat + Deep-Diff

Loggt den API-Key NICHT.  uv run python scripts/el_bind_send_email.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import httpx

BASE = "https://api.elevenlabs.io"
SEND_EMAIL_ID = "tool_0201kvte9qtnfvq9bqqfgk6wk70x"
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


def _props(tool_obj: dict) -> dict:
    return tool_obj["tool_config"]["api_schema"]["request_body_schema"]["properties"]


def _flat(d, prefix=""):
    """Flache Key->Value-Map zum Diffen."""
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flat(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.update(_flat(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = d
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden.")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {"xi-api-key": key}

    with httpx.Client(base_url=BASE, headers=headers, timeout=60.0) as c:
        # 1) GET vorher
        r = c.get(f"/v1/convai/tools/{SEND_EMAIL_ID}")
        print(f"GET tool -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:400]); return 1
        before = r.json()
        (OUT / "send_email_before.json").write_text(
            json.dumps(before, indent=2, ensure_ascii=False), encoding="utf-8")

        # 2) Modify
        tc = before["tool_config"]
        props = _props(before)
        for field, var in BINDINGS.items():
            if field not in props:
                print(f"BLOCKED: Property '{field}' fehlt im Schema."); return 1
            # Getaggte Union: NUR dynamic_variable darf "gesetzt" sein.
            p = props[field]
            p["dynamic_variable"] = var
            p["description"] = ""          # war "gesetzt" (LLM-Prompt-Modus) -> leeren
            p["is_system_provided"] = False
            p["constant_value"] = ""
            p["is_omitted"] = False
        print("Geplant:", {f: props[f]["dynamic_variable"] for f in BINDINGS})

        # 3) PATCH (voller tool_config)
        r = c.patch(f"/v1/convai/tools/{SEND_EMAIL_ID}", json={"tool_config": tc})
        print(f"PATCH tool -> {r.status_code}")
        if r.status_code not in (200, 201):
            print("FEHLER-Body:", r.text[:600]); return 1

        # 4) GET nachher
        r = c.get(f"/v1/convai/tools/{SEND_EMAIL_ID}")
        after = r.json()
        (OUT / "send_email_after.json").write_text(
            json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")

    # Bericht
    ap = _props(after)
    print("\n--- Gespeicherte Werte (nachher) ---")
    for field in BINDINGS:
        p = ap.get(field, {})
        print(f"  {field}: dynamic_variable={p.get('dynamic_variable')!r}  "
              f"is_system_provided={p.get('is_system_provided')!r}  "
              f"constant_value={p.get('constant_value')!r}  is_omitted={p.get('is_omitted')!r}")

    print("\n--- Deep-Diff before vs after (nur tool_config) ---")
    fb, fa = _flat(before["tool_config"]), _flat(after["tool_config"])
    keys = sorted(set(fb) | set(fa))
    changed = False
    for k in keys:
        if fb.get(k) != fa.get(k):
            changed = True
            print(f"  {k}: {fb.get(k)!r} -> {fa.get(k)!r}")
    if not changed:
        print("  (keine Unterschiede — Achtung: dann hat der PATCH nichts gespeichert!)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
