"""Setzt die description EINES Request-Body-Parameters eines Tools (read-modify-write).

  uv run python scripts/el_set_param_desc.py <tool_id> <param> <neue_description>

Ändert NUR properties[param].description — der Union-Shape (description gesetzt,
dynamic_variable/constant_value/is_system_provided/is_omitted leer/false) bleibt
unverändert, daher kein 422. Loggt den API-Key NICHT. Before/After nach EL_OUT_DIR.
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


def _props(obj: dict) -> dict:
    return obj["tool_config"]["api_schema"]["request_body_schema"]["properties"]


def main(argv) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if len(argv) < 3:
        print("Usage: el_set_param_desc.py <tool_id> <param> <neue_description>"); return 2
    tool_id, param, new_desc = argv[0], argv[1], argv[2]

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

        props = _props(before)
        if param not in props:
            print(f"BLOCKED: Property '{param}' fehlt. Vorhanden: {list(props)}"); return 1
        p = props[param]
        # Guard gegen versehentliches Zerstören einer Bindung:
        if p.get("dynamic_variable") or p.get("is_system_provided") or p.get("constant_value"):
            print(f"BLOCKED: '{param}' ist an eine Variable/Konstante gebunden — "
                  f"description setzen würde den Union-Shape verletzen."); return 1
        old = p.get("description", "")
        p["description"] = new_desc

        r = c.patch(f"/v1/convai/tools/{tool_id}", json={"tool_config": before["tool_config"]})
        print(f"PATCH tool -> {r.status_code}")
        if r.status_code not in (200, 201):
            print("FEHLER:", r.text[:600]); return 1

        after = c.get(f"/v1/convai/tools/{tool_id}").json()
        (OUT / f"{name}_after.json").write_text(
            json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{name}.{param}.description:")
    print(f"  ALT: {old!r}")
    print(f"  NEU: {_props(after)[param].get('description')!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
