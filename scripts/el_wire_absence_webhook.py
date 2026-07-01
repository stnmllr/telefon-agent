"""Verdrahtet den Conversation-Initiation-Webhook (Abwesenheits-Check) in ElevenLabs.

  TOOL_AUTH_TOKEN="$(gcloud secrets versions access latest --secret=tool-auth-token \
     --project boxwood-mantra-489408-c0)" \
  uv run python scripts/el_wire_absence_webhook.py <agent_id> [base_url]

Zwei Schritte (idempotent):
  1) Workspace-Setting `conversation_initiation_client_data_webhook` = {url, request_headers}
     -> ElevenLabs ruft bei Anrufbeginn POST <base_url>/tools/check_absence mit Header
        X-Tool-Token; das Backend liefert dynamic_variables absence_active/absence_text.
  2) Agent: overrides.enable_conversation_initiation_client_data_from_webhook = True und
     dynamic_variable_placeholders {absence_active:"false", absence_text:""} als Fallback.

Bewahrt Prompt/Tools/KB (read-modify-write, poppt read-only prompt.tools).
Loggt keine Secrets. TOOL_AUTH_TOKEN kommt aus der Umgebung (nicht hartkodiert).
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys

import httpx

BASE = "https://api.elevenlabs.io"
DEFAULT_APP = "https://telefon-agent-1051648887841.europe-west3.run.app"
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
        print("Usage: el_wire_absence_webhook.py <agent_id> [base_url]"); return 2
    agent_id = argv[0]
    base_url = (argv[1] if len(argv) > 1 else DEFAULT_APP).rstrip("/")
    webhook_url = f"{base_url}/tools/check_absence"

    key = _load_api_key()
    if not key:
        print("BLOCKED: ELEVENLABS_API_KEY nicht gefunden."); return 2
    token = os.environ.get("TOOL_AUTH_TOKEN", "").strip()
    if not token:
        print("BLOCKED: TOOL_AUTH_TOKEN nicht in der Umgebung (aus Secret setzen)."); return 2
    OUT.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=BASE, headers={"xi-api-key": key}, timeout=60.0) as c:
        # 1) Workspace-Webhook
        settings = c.get("/v1/convai/settings").json()
        settings["conversation_initiation_client_data_webhook"] = {
            "url": webhook_url,
            "request_headers": {"X-Tool-Token": token},
        }
        r = c.patch("/v1/convai/settings", json=settings)
        print(f"PATCH /v1/convai/settings -> {r.status_code}")
        if r.status_code not in (200, 201):
            print("FEHLER:", r.text[:600]); return 1
        got = c.get("/v1/convai/settings").json()["conversation_initiation_client_data_webhook"]
        print(f"  webhook.url = {got.get('url')}")
        print(f"  X-Tool-Token gesetzt = {'X-Tool-Token' in (got.get('request_headers') or {})}")

        # 2) Agent: fetch aktivieren + Placeholder-Defaults
        a = c.get(f"/v1/convai/agents/{agent_id}").json()
        before = copy.deepcopy(a)
        (OUT / "agent_before.json").write_text(
            json.dumps(before, indent=2, ensure_ascii=False), encoding="utf-8")
        a["platform_settings"]["overrides"]["enable_conversation_initiation_client_data_from_webhook"] = True
        dv = a["conversation_config"]["agent"].setdefault("dynamic_variables", {})
        ph = dv.setdefault("dynamic_variable_placeholders", {})
        ph.setdefault("absence_active", "false")
        ph.setdefault("absence_text", "")
        pr = a["conversation_config"]["agent"]["prompt"]
        if pr.get("tool_ids"):
            pr.pop("tools", None)
        plen = len(pr.get("prompt", ""))

        r = c.patch(f"/v1/convai/agents/{agent_id}", json={
            "conversation_config": a["conversation_config"],
            "platform_settings": a["platform_settings"],
        })
        print(f"PATCH agent -> {r.status_code}")
        if r.status_code not in (200, 201):
            print("FEHLER:", r.text[:600]); return 1

        af = c.get(f"/v1/convai/agents/{agent_id}").json()
        (OUT / "agent_after.json").write_text(
            json.dumps(af, indent=2, ensure_ascii=False), encoding="utf-8")
        ov = af["platform_settings"]["overrides"]
        prp = af["conversation_config"]["agent"]["prompt"]
        print(f"  enable_...from_webhook = {ov.get('enable_conversation_initiation_client_data_from_webhook')}")
        print(f"  placeholders = {json.dumps(af['conversation_config']['agent'].get('dynamic_variables'), ensure_ascii=False)}")
        print(f"  prompt.prompt unverändert = {len(prp.get('prompt',''))==plen}; "
              f"tool_ids = {len(prp.get('tool_ids') or [])}; kb = {len(prp.get('knowledge_base') or [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
