# KI-Telefon-Agent — Projektstand 23.03.2026

## Infrastruktur

| Komponente | Wert |
|---|---|
| GCP Projekt | boxwood-mantra-489408-c0 |
| Cloud Run | telefon-agent / europe-west3 |
| URL | https://telefon-agent-1051648887841.europe-west3.run.app |
| Bucket | gs://boxwood-mantra-489408-c0-handbuecher/ |
| Vertex AI Search | handbuecher-engine (App-ID), Datastore: handbuecher-v2, Location: global |
| Firestore | Conversation Memory aktiv |
| Twilio | +49 89 41432469, Webhook auf /call/incoming |
| GitHub | stnmllr/telefon-agent, CI/CD via GitHub Actions (Push main → auto-deploy) |
| Service Account | 1051648887841-compute@developer.gserviceaccount.com |

## Aktueller Status: ✅ AGENT FUNKTIONIERT

Erster erfolgreicher End-to-End-Test am 23.03.2026 — RAG findet Kontext,
Gemini antwortet korrekt auf Deutsch mit Diagnose-Fragen.

Beispiel-Test:
```
POST /call/transcribe
SpeechResult=Ich habe in die falsche Periode gebucht
→ Antwort: "Wurde die Buchung bereits gezahlt?"
```

## Aktuelle Konfiguration (Cloud Run Env-Vars)

```
ENVIRONMENT=production
GCP_PROJECT_ID=boxwood-mantra-489408-c0
GCP_LOCATION=us-central1          ← Gemini-Region
GEMINI_MODEL=gemini-2.0-flash     ← WICHTIG: ohne -001 Suffix
VERTEX_SEARCH_DATASTORE=handbuecher-v2
STT_LANGUAGE=de-DE
STT_MODEL=chirp
TTS_VOICE=de-DE-Neural2-F
TTS_SPEAKING_RATE=1.0
RAG_TOP_K=3
RAG_MAX_TOKENS=150
LLM_TEMPERATURE=0.0
```

## Bugs die heute gefixt wurden

1. **Einrückungsfehler call_router.py** — war bereits vor dieser Session behoben
2. **Placeholder `my-gcp-project`** in config.py → echte Projekt-ID als Default
3. **`extractiveContentSpec`** entfernt — Standard Edition unterstützt keine Extractive Answers (Enterprise Feature)
4. **Modellname** `gemini-2.0-flash-001` → `gemini-2.0-flash`
5. **IAM** — Service Account hat `roles/discoveryengine.viewer` erhalten
6. **Doppelter LLM-Block** in rag_service.py entfernt
7. **Neue Settings** in config.py: `vertex_search_location=global`, `vertex_search_engine_id=handbuecher-engine`

## Wichtige Architektur-Entscheidungen

- **Vertex AI Search** läuft immer unter `locations/global` — NICHT unter `gcp_location`
- **Gemini** läuft unter `us-central1` — `gemini-2.0-flash` ist dort verfügbar
- **Snippets statt Extractive Answers** — Standard Edition, völlig ausreichend für Telefon-Support
- **RAG-Pfad**: `_build_search_query` → `_search_datastore` → `ChatVertexAI`

## Nächste geplante Features (Reihenfolge)

1. **Entwicklungsumgebung aufbauen** ← NÄCHSTE SESSION (siehe unten)
2. **Latenz messen** — echter Anruf auf +49 89 41432469 testen
3. **E-Mail Fallback** — wenn Agent nicht antworten kann → E-Mail an Support
4. **Error Handling & Monitoring** — Cloud Logging Alerts, Health Checks
5. **Intent-Classifier** — FIBU / OPos / Kore / Anbu / Sonstiges
6. **Multi-Agent Modell** — separater Agent pro Bereich

---

## NÄCHSTE SESSION: Entwicklungsumgebung aufbauen

### Ziel
Schluss mit Copy-Paste zwischen Chat und Editor. Professioneller lokaler
Entwicklungs-Workflow mit VS Code + Claude Code.

### Schritte (in dieser Reihenfolge)

**Schritt 1 — VS Code installieren**
- Download: https://code.visualstudio.com
- Einfach installieren, keine Konfiguration nötig

**Schritt 2 — Node.js installieren**
- Download: https://nodejs.org (LTS-Version)
- Wird für Claude Code benötigt

**Schritt 3 — Git for Windows installieren** (falls nicht vorhanden)
- Download: https://git-scm.com
- Bei Installation: "Use VS Code as default editor" wählen

**Schritt 4 — Repository lokal klonen**
```bash
git clone https://github.com/stnmllr/telefon-agent.git
cd telefon-agent
code .    # öffnet VS Code direkt im Projektordner
```

**Schritt 5 — Claude Code installieren**
```bash
npm install -g @anthropic-ai/claude-code
cd telefon-agent
claude
```

**Schritt 6 — gcloud CLI installieren** (für lokales Deployen)
- Download: https://cloud.google.com/sdk/docs/install
```bash
gcloud auth login
gcloud config set project boxwood-mantra-489408-c0
```

**Schritt 7 — Direktes Deploy ohne GitHub Actions**
```bash
# Zum Testen — kein Commit nötig
gcloud run deploy telefon-agent \
  --source . \
  --region europe-west3 \
  --project boxwood-mantra-489408-c0
```

### Neuer Workflow danach

| Vorher (nervt) | Nachher |
|---|---|
| Chat → Copy → Cloud Shell → Paste | Claude Code schreibt direkt in Datei |
| git commit → GitHub Actions → 2 Min warten | `gcloud run deploy --source .` direkt |
| Logs in Cloud Shell suchen | VS Code Terminal + Log-Streaming |
| Kontext zwischen Chats verloren | Claude Code liest gesamtes Repo |
