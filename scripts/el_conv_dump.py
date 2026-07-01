"""Read-only: holt die letzten Conversations und dumpt die Tool-Calls (Request+Response).

  uv run python scripts/el_conv_dump.py <agent_id> [n]

Loggt den API-Key NICHT.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import httpx

BASE = "https://api.elevenlabs.io"


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
        print("Usage: el_conv_dump.py <agent_id> [n]"); return 2
    agent_id = argv[0]
    n = int(argv[1]) if len(argv) > 1 else 1
    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2

    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=60.0) as c:
        r = c.get("/v1/convai/conversations",
                  params={"agent_id": agent_id, "page_size": n})
        print(f"LIST conversations -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:400]); return 1
        convs = r.json().get("conversations", [])
        for meta in convs[:n]:
            cid = meta.get("conversation_id")
            print(f"\n===== conversation {cid}  start={meta.get('start_time_unix_secs')} "
                  f"status={meta.get('status')} =====")
            d = c.get(f"/v1/convai/conversations/{cid}")
            if d.status_code != 200:
                print(f"  detail -> {d.status_code}: {d.text[:200]}"); continue
            transcript = d.json().get("transcript", [])
            for turn in transcript:
                role = turn.get("role")
                # Tool-Calls stehen je nach Schema unter tool_calls / tool_results
                for tc in (turn.get("tool_calls") or []):
                    print(f"  [{role}] TOOL_CALL {tc.get('tool_name')} "
                          f"params={json.dumps(tc.get('params_as_json') or tc.get('tool_details') or tc, ensure_ascii=False)[:500]}")
                for tr in (turn.get("tool_results") or []):
                    print(f"  [{role}] TOOL_RESULT {tr.get('tool_name')} "
                          f"-> {json.dumps(tr.get('result_value') or tr, ensure_ascii=False)[:500]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
