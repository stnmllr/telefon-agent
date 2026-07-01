# CLAUDE.md — telefon-agent

## Tests ausführen
Immer mit `uv` über das Modul aufrufen — NICHT die `pytest.exe` direkt:

```
uv run python -m pytest
```

**Warum `python -m pytest`:** Auf diesem Rechner blockiert der EPDR/WatchGuard-
Endpoint-Schutz den direkten `pytest.exe`-Entrypoint (wie bei FisherScreen). Der
Aufruf über `python -m pytest` umgeht den blockierten Entrypoint.

Einmalig die Umgebung aufsetzen (Python 3.12 wie in der Production/Dockerfile —
System-Python 3.14 hat keine Wheels für langchain/aiplatform):

```
uv venv --python 3.12
uv pip install -r requirements.txt
```

## Umgebung
- In VS Code immer **Command Prompt** verwenden, nie PowerShell.
- Pure-Logic-Kerne liegen unter `app/tools/` und dürfen kein I/O (Firestore/HTTP/
  Resend) berühren — nur CSV-Read. So bleiben sie direkt unit-testbar.

## Architektur
Siehe `docs/superpowers/specs/2026-06-22-elevenlabs-tool-backend-design.md`.
Pivot auf ElevenLabs Agents; dieses Repo liefert das Tool-Backend.
