"""Read-only Inspektion der ElevenLabs-ConvAI-Config (Tools, Agent, KB).

Loggt den API-Key NICHT. Schreibt rohe JSON-Antworten nach
scratchpad/, druckt nur Zusammenfassungen. Rein lesend (nur GET).

    uv run python -m scripts.el_inspect
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


def _dump(name: str, data) -> pathlib.Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.json"
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden (.env/Umgebung).")
        return 2

    headers = {"xi-api-key": key}
    with httpx.Client(base_url=BASE, headers=headers, timeout=60.0) as c:
        # 1) Tools
        r = c.get("/v1/convai/tools")
        print(f"GET /v1/convai/tools -> {r.status_code}")
        if r.status_code == 200:
            tools = r.json()
            _dump("tools_all", tools)
            items = tools.get("tools", tools) if isinstance(tools, dict) else tools
            print(f"  Tools gesamt: {len(items)}")
            for t in items:
                tc = t.get("tool_config", t)
                name = tc.get("name") or t.get("name")
                print(f"   - {name}  (id={t.get('id') or t.get('tool_id')})")
        else:
            print(f"  Body: {r.text[:300]}")

        # 2) Agents
        r = c.get("/v1/convai/agents")
        print(f"GET /v1/convai/agents -> {r.status_code}")
        if r.status_code == 200:
            agents = r.json()
            _dump("agents_all", agents)
            items = agents.get("agents", agents) if isinstance(agents, dict) else agents
            print(f"  Agents gesamt: {len(items)}")
            for a in items:
                print(f"   - {a.get('name')}  (id={a.get('agent_id') or a.get('id')})")

        # 3) KB docs
        r = c.get("/v1/convai/knowledge-base")
        print(f"GET /v1/convai/knowledge-base -> {r.status_code}")
        if r.status_code == 200:
            kb = r.json()
            _dump("kb_all", kb)
            items = kb.get("documents", kb) if isinstance(kb, dict) else kb
            print(f"  KB-Docs gesamt: {len(items)}")

    print(f"\nRohdaten in: {OUT.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
