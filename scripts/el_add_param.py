"""Fügt einem Tool ein neues (optionales, LLM-befülltes) String-Property hinzu.

  uv run python scripts/el_add_param.py <tool_id> <param> <description>

Idempotent: existiert das Property schon, bleibt es unverändert. Das neue
Property bekommt den Standard-Union-Shape (nur description gesetzt) und wird
NICHT in required aufgenommen (optional). Loggt den API-Key NICHT.
Before/After nach EL_OUT_DIR.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import httpx

BASE = "https://api.elevenlabs.io"
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


def _schema(obj: dict) -> dict:
    return obj["tool_config"]["api_schema"]["request_body_schema"]


def main(argv) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if len(argv) < 3:
        print("Usage: el_add_param.py <tool_id> <param> <description>"); return 2
    tool_id, param, desc = argv[0], argv[1], argv[2]

    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2
    OUT.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=60.0) as c:
        r = c.get(f"/v1/convai/tools/{tool_id}")
        print(f"GET tool -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:400]); return 1
        before = r.json()
        name = before["tool_config"]["name"]
        (OUT / f"{name}_before.json").write_text(
            json.dumps(before, indent=2, ensure_ascii=False), encoding="utf-8")

        schema = _schema(before)
        props = schema.setdefault("properties", {})
        if param in props:
            print(f"'{name}.{param}' existiert bereits — keine Änderung."); return 0
        props[param] = {
            "type": "string",
            "description": desc,
            "enum": None,
            "is_system_provided": False,
            "dynamic_variable": "",
            "allowed_values_dynamic_variable": "",
            "constant_value": "",
            "is_omitted": False,
        }
        # optional -> NICHT in required
        print(f"Neues Property '{name}.{param}' (optional). required bleibt: {schema.get('required')}")

        r = c.patch(f"/v1/convai/tools/{tool_id}", json={"tool_config": before["tool_config"]})
        print(f"PATCH tool -> {r.status_code}")
        if r.status_code not in (200, 201):
            print("FEHLER:", r.text[:600]); return 1

        after = c.get(f"/v1/convai/tools/{tool_id}").json()
        (OUT / f"{name}_after.json").write_text(
            json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")
        ap = _schema(after)["properties"]
        print(f"Properties nachher: {list(ap)}")
        print(f"'{param}' gespeichert: {param in ap}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
