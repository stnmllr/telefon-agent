"""Setzt System-Prompt (prompt.prompt) und first_message eines Agenten (read-modify-write).

  uv run python scripts/el_set_prompt.py <agent_id> <prompt_file> [first_message_file]

Ändert NUR prompt.prompt und (optional) agent.first_message. tool_ids/KB/RAG
bleiben unangetastet; die read-only prompt.tools werden vor dem PATCH gepoppt
(sonst 400 both_tools_and_tool_ids_provided). Before/After -> Deep-Diff.
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
    if len(argv) < 2:
        print("Usage: el_set_prompt.py <agent_id> <prompt_file> [first_message_file]"); return 2
    agent_id, prompt_file = argv[0], argv[1]
    first_file = argv[2] if len(argv) > 2 else None

    new_prompt = pathlib.Path(prompt_file).read_text(encoding="utf-8").rstrip("\n")
    new_first = pathlib.Path(first_file).read_text(encoding="utf-8").strip() if first_file else None

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
        before = copy.deepcopy(agent)
        (OUT / "agent_before.json").write_text(
            json.dumps(agent, indent=2, ensure_ascii=False), encoding="utf-8")

        acfg = agent["conversation_config"]["agent"]
        prompt = acfg["prompt"]
        old_prompt = prompt.get("prompt", "")
        prompt["prompt"] = new_prompt
        if new_first is not None:
            acfg["first_message"] = new_first
        # GET expandiert tool_ids zu read-only prompt.tools; beim PATCH darf nur
        # EINES von beiden gesendet werden (sonst 400 both_tools_and_tool_ids).
        if prompt.get("tool_ids"):
            prompt.pop("tools", None)

        print(f"prompt.prompt: {len(old_prompt)} -> {len(new_prompt)} Zeichen")
        print(f"tool_ids bleibt: {prompt.get('tool_ids')}")
        print(f"knowledge_base bleibt: {len(prompt.get('knowledge_base') or [])} Docs; "
              f"rag.enabled={prompt.get('rag', {}).get('enabled')}")

        r = c.patch(f"/v1/convai/agents/{agent_id}",
                    json={"conversation_config": agent["conversation_config"]})
        print(f"PATCH agent -> {r.status_code}")
        if r.status_code not in (200, 201):
            print("FEHLER:", r.text[:800]); return 1

        after = c.get(f"/v1/convai/agents/{agent_id}").json()
        (OUT / "agent_after.json").write_text(
            json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")

    ap = after["conversation_config"]["agent"]
    print(f"\n--- Nachher ---")
    print(f"first_message: {ap.get('first_message')!r}")
    print(f"prompt.prompt Länge: {len(ap['prompt'].get('prompt',''))}")
    print(f"tool_ids: {ap['prompt'].get('tool_ids')}")
    print(f"knowledge_base: {len(ap['prompt'].get('knowledge_base') or [])} Docs; "
          f"rag.enabled={ap['prompt'].get('rag', {}).get('enabled')}")

    fb, fa = _flat(before["conversation_config"]), _flat(after["conversation_config"])
    ch = [k for k in sorted(set(fb) | set(fa)) if fb.get(k) != fa.get(k)]
    print(f"\n--- Deep-Diff conversation_config: {len(ch)} Felder geändert ---")
    for k in ch[:40]:
        bv, av = fb.get(k), fa.get(k)
        bv = (bv[:70] + "…") if isinstance(bv, str) and len(bv) > 70 else bv
        av = (av[:70] + "…") if isinstance(av, str) and len(av) > 70 else av
        print(f"  {k}: {bv!r} -> {av!r}")
    if len(ch) > 40:
        print(f"  … +{len(ch) - 40} weitere")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
