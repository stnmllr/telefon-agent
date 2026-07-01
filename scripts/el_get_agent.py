"""Read-only: holt die volle Agent-Config und zeigt prompt.knowledge_base + rag.

  uv run python scripts/el_get_agent.py <agent_id>

Loggt den API-Key NICHT. Dump nach EL_OUT_DIR/agent_full.json.
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


def main(argv) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if not argv:
        print("Usage: el_get_agent.py <agent_id>"); return 2
    agent_id = argv[0]
    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2
    OUT.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=60.0) as c:
        r = c.get(f"/v1/convai/agents/{agent_id}")
        print(f"GET agent -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:400]); return 1
        agent = r.json()
    (OUT / "agent_full.json").write_text(
        json.dumps(agent, indent=2, ensure_ascii=False), encoding="utf-8")

    prompt = agent.get("conversation_config", {}).get("agent", {}).get("prompt", {})
    kb = prompt.get("knowledge_base", "<fehlt>")
    rag = prompt.get("rag", "<fehlt>")
    print("\nprompt.knowledge_base:")
    print(json.dumps(kb, indent=2, ensure_ascii=False))
    print("\nprompt.rag:")
    print(json.dumps(rag, indent=2, ensure_ascii=False))
    print(f"\nVolle Config: {(OUT / 'agent_full.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
