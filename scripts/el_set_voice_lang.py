"""Setzt Sprache=de, multilinguales TTS-Modell, Voice=Leonie, dt. first_message.

  uv run python scripts/el_set_voice_lang.py <agent_id>

- Übernimmt Leonie (Library-Voice) idempotent in den Workspace, falls nicht vorhanden.
- Voller conversation_config-Round-Trip; ändert NUR die 4 Felder. Deep-Diff.
Loggt den API-Key NICHT.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys

import httpx

BASE = "https://api.elevenlabs.io"
VOICE_ID = "uvysWDLbKpA4XvpD3GI6"   # Leonie - Clear and Engaging (de, female)
VOICE_NAME = "Leonie"
MODEL_ID = "eleven_flash_v2_5"
LANGUAGE = "de"
FIRST_MESSAGE = "Guten Tag, hier ist Sofia. Wie kann ich Ihnen helfen?"


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


def _ensure_voice(c) -> bool:
    own = c.get("/v1/voices").json().get("voices", [])
    if any(v.get("voice_id") == VOICE_ID for v in own):
        print(f"Voice {VOICE_NAME} bereits im Workspace.")
        return True
    # public_owner_id aus Shared Library holen
    r = c.get("/v1/shared-voices",
              params={"gender": "female", "language": "de", "search": VOICE_NAME, "page_size": 10})
    cand = [v for v in r.json().get("voices", []) if v.get("voice_id") == VOICE_ID]
    if not cand:
        print(f"BLOCKED: {VOICE_NAME} nicht in Shared Library gefunden."); return False
    owner = cand[0].get("public_owner_id")
    r = c.post(f"/v1/voices/add/{owner}/{VOICE_ID}", json={"new_name": VOICE_NAME})
    print(f"ADD voice {VOICE_NAME} -> {r.status_code} {str(r.text)[:160]}")
    return r.status_code in (200, 201)


def main(argv) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if not argv:
        print("Usage: el_set_voice_lang.py <agent_id>"); return 2
    agent_id = argv[0]
    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2

    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=60.0) as c:
        if not _ensure_voice(c):
            return 1

        agent = c.get(f"/v1/convai/agents/{agent_id}").json()
        before = copy.deepcopy(agent)
        cc = agent["conversation_config"]
        cc["tts"]["model_id"] = MODEL_ID
        cc["tts"]["voice_id"] = VOICE_ID
        cc["agent"]["language"] = LANGUAGE
        cc["agent"]["first_message"] = FIRST_MESSAGE

        r = c.patch(f"/v1/convai/agents/{agent_id}", json={"conversation_config": cc})
        print(f"PATCH agent -> {r.status_code}")
        if r.status_code not in (200, 201):
            print("FEHLER:", r.text[:600]); return 1
        after = c.get(f"/v1/convai/agents/{agent_id}").json()

    fb, fa = _flat(before["conversation_config"]), _flat(after["conversation_config"])
    ch = [k for k in sorted(set(fb) | set(fa)) if fb.get(k) != fa.get(k)]
    print(f"\n--- Deep-Diff conversation_config: {len(ch)} Felder ---")
    for k in ch:
        print(f"  {k}: {fb.get(k)!r} -> {fa.get(k)!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
