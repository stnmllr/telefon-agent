# KI-Telefon-Agent — Projektstand 10.04.2026

## Infrastruktur

| Komponente | Wert |
|---|---|
| GCP Projekt | boxwood-mantra-489408-c0 |
| Cloud Run | telefon-agent / europe-west3 |
| URL | https://telefon-agent-1051648887841.europe-west3.run.app |
| Bucket | gs://boxwood-mantra-489408-c0-handbuecher/ |
| Vertex AI Search | handbuecher-engine (Enterprise Edition ✅), Datastore: handbuecher-v2, Location: global |
| Firestore | Conversation Memory + Pending-Cache für Redirect aktiv |
| Twilio | +49 89 41432469, Webhook auf /call/incoming |
| GitHub | stnmllr/telefon-agent, CI/CD via GitHub Actions (Push main → auto-deploy) |
| Service Account | 1051648887841-compute@developer.gserviceaccount.com |

## Aktueller Status: ✅ AGENT FUNKTIONIERT GUT

- Gemini 2.5 Flash aktiv — Antwortqualität deutlich besser als 2.0
- Zwischenantwort "Einen Moment bitte..." bei langen Fragen (>5 Wörter)
- Kein Markdown mehr in Antworten (Sternchen-Problem behoben)
- Schritt-für-Schritt Gesprächsführung mit Rückfragen aktiv
- Logisches Schlussfolgern bei fehlenden Handbuch-Infos

## Aktuelle Konfiguration (Cloud Run Env-Vars)

```
ENVIRONMENT=production
GCP_PROJECT_ID=boxwood-mantra-489408-c0
GCP_LOCATION=us-central1
GEMINI_MODEL=gemini-2.5-flash
VERTEX_SEARCH_DATASTORE=handbuecher-v2
STT_LANGUAGE=de-DE
STT_MODEL=chirp
TTS_VOICE=de-DE-Journey-F
TTS_SPEAKING_RATE=1.0
RAG_TOP_K=5
RAG_MAX_TOKENS=400
LLM_TEMPERATURE=0.0
```

## Entwicklungsumgebung

| Tool | Status |
|---|---|
| VS Code | ✅ installiert, Projekt geöffnet |
| Claude Code | ✅ als VS Code Extension aktiv |
| Node.js v24 | ✅ installiert |
| Git 2.53 | ✅ installiert |
| gcloud CLI | ✅ installiert, eingeloggt als stn.mueller@gmail.com |
| PowerShell ExecutionPolicy | ✅ RemoteSigned gesetzt |

**Workflow:**
- Planung: claude.ai — PROJEKTSTAND.md zu Beginn hochladen
- Code ändern: Claude Code in VS Code (Chat-Panel rechts)
- Deploy: git add -A && git commit -m "..." && git push origin main
- Terminal: immer Command Prompt verwenden, nicht PowerShell
- Logs live: gcloud beta run services logs tail telefon-agent --region europe-west3 --project boxwood-mantra-489408-c0

## Architektur call_router.py

```
POST /call/incoming
→ Begrüßung + STT aktivieren

POST /call/transcribe
→ STT-Qualität prüfen
→ Verabschiedung erkennen
→ Bei >5 Wörtern: SpeechResult in Firestore (pending/{CallSid})
                   + Say "Einen Moment bitte..."
                   + Redirect zu /call/process
→ Bei ≤5 Wörtern: direkt Redirect zu /call/process

POST /call/process
→ SpeechResult aus Firestore lesen + löschen
→ answer_question() aufrufen (RAG + LLM)
→ Antwort als TwiML zurückgeben
```

## Kosten (monatlich, Schätzung)

| Komponente | Kosten |
|---|---|
| Vertex AI Search Enterprise | ~$2–5 |
| Gemini 2.5 Flash | ~$1–2 |
| Cloud Run | ~$0 |
| Firestore | ~$0 |
| Twilio Nummer + Anrufe | ~$1.50 |
| **Gesamt** | **~$5–10/Monat** |

Budget-Alert: €10/Monat eingerichtet ✅
GCP: Bezahltes Konto, $300 Guthaben läuft noch

## Alle bisherigen Fixes

1. Einrückungsfehler call_router.py — behoben
2. Placeholder my-gcp-project → echte Projekt-ID
3. extractiveContentSpec — aktiv (Enterprise Edition)
4. Modellname → gemini-2.5-flash
5. IAM — Service Account hat roles/discoveryengine.viewer
6. Doppelter LLM-Block entfernt
7. vertex_search_location=global, vertex_search_engine_id=handbuecher-engine
8. LangChain + Vertex AI Libraries aktualisiert
9. Markdown aus Antworten entfernt (answer.replace)
10. Thinking Budget auf 512 Tokens gesetzt
11. Zwischenantwort via Firestore-Redirect implementiert
12. Zwischenantwort nur bei >5 Wörtern

## NÄCHSTE SESSION — Offene Punkte (Reihenfolge)

### 1. Supportfälle-Dokument hochladen ← ZUERST
Fall 6-8 wurden von Claude Code erstellt aber noch nicht in den GCS Bucket hochgeladen.
```cmd
gsutil cp supportfaelle_syska_profi.txt gs://boxwood-mantra-489408-c0-handbuecher/
```
Danach Datastore neu indexieren: GCP Console → AI Search → handbuecher-engine → Daten → Neu indexieren

### 2. Latenz weiter reduzieren
Aktuell ~13 Sekunden für LLM-Aufruf — eingeschränkt durch Gemini 2.5 Flash auf Vertex AI.
Optionen:
- RAG_TOP_K auf 3 reduzieren (weniger Kontext = schneller)
- budget_tokens weiter reduzieren (z.B. 256)
- Gemini 2.5 Flash Lite testen (schneller, etwas weniger Qualität)

### 3. E-Mail Service implementieren
Neues File: app/services/email_service.py via SendGrid oder Gmail API.
Neue Env-Vars in Cloud Run:
```
SENDGRID_API_KEY=...
EMAIL_SUPPORT=support@sopra-system.com
EMAIL_IT=it-support@sopra-system.com
EMAIL_MANAGEMENT=stephan.mueller@sopra-system.com
EMAIL_CC=stephan.mueller@sopra-system.com
```

### 4. Routing-Logik implementieren
Wenn Kunde kein syska-Thema hat:
- EVS → Sprachhinweis
- HR → Sprachhinweis
- ERP → E-Mail support@sopra-system.com
- IT → E-Mail it-support@sopra-system.com
- Verwaltung/Verträge → E-Mail stephan.mueller@sopra-system.com
- Agent kann nicht helfen → E-Mail support@sopra-system.com, CC: stephan.mueller@sopra-system.com

### 5. TTS-Stimme weiter optimieren
Journey-F ist aktiv aber noch nicht optimal.
Alternativen: de-DE-Chirp3-HD-Aoede

### 6. Error Handling & Monitoring
Cloud Logging Alerts, Health Checks

### 7. Intent-Classifier
FIBU / OPos / Kore / Anbu / Sonstiges

### 8. Multi-Agent Modell
Separater Agent pro Bereich

## Routing-Logik (geplant)

| Szenario | Erkennung | Aktion |
|---|---|---|
| syska ProFI Frage | Standard | RAG-Pipeline → Antwort |
| Agent kann nicht helfen | Kein Kontext | E-Mail → support@sopra-system.com, CC: stephan.mueller@sopra-system.com |
| EVS | Keyword: "EVS" | Sprachhinweis |
| HR | Keyword: "HR", "Personal" | Sprachhinweis |
| ERP | Keyword: "ERP", "Warenwirtschaft" | E-Mail → support@sopra-system.com |
| IT-Problem | Keyword: "Computer", "Netzwerk", "IT" | E-Mail → it-support@sopra-system.com |
| Verwaltung/Verträge | Keyword: "Vertrag", "Rechnung", "Preis" | E-Mail → stephan.mueller@sopra-system.com |

## Wichtige Architektur-Entscheidungen

- Vertex AI Search läuft unter locations/global
- Gemini läuft unter us-central1
- Enterprise Edition → Extractive Answers → vollständige Textpassagen
- Firestore: zwei Verwendungen — Conversation Memory + Pending-Cache für Redirect
- PowerShell in VS Code → immer Command Prompt verwenden
