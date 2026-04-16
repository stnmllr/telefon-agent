# KI-Telefon-Agent — Projektstand 16.04.2026

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

## Status: ✅ ALLE 8 TEST-SZENARIEN BESTANDEN

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
LATENCY_LOGGING=true        ← temporär, nach Tests auf false setzen
```

## Projektstruktur

```
app/
├── data/
│   └── telefonbuch.csv          ← Internes Telefonverzeichnis
├── routers/
│   └── call_router.py           ← Twilio Webhooks + Routing-Logik
├── services/
│   ├── rag_service.py           ← LLM + RAG + System-Prompt
│   ├── memory_service.py        ← Firestore Conversation Memory
│   └── phonebook_service.py     ← Telefonbuch-Lookup
└── utils/
    ├── twiml_builder.py         ← TwiML Response Builder mit XML-Escaping
    └── latency_logger.py        ← Latenz-Messung (neu)
test_scenarios.bat               ← Automatisierte Tests für alle 8 Szenarien
```

## Architektur call_router.py

```
POST /call/incoming
→ Begrüßung als SOPRA System KI-Assistent + STT aktivieren

POST /call/transcribe
→ STT-Qualität prüfen
→ Verabschiedung erkennen
→ Bei >5 Wörtern: SpeechResult in Firestore (pending/{CallSid})
                   + "Einen Moment bitte..."
                   + Redirect zu /call/process
→ Bei ≤5 Wörtern: direkt Redirect zu /call/process

POST /call/process
→ SpeechResult aus Firestore lesen + löschen
→ Fallback: SpeechResult direkt als Parameter (für Tests)
→ answer_question() aufrufen (RAG + LLM)
→ Antwort XML-escaped als TwiML zurückgeben
```

## Routing-Logik

| Kategorie | Erkennungsmerkmale | Aktion |
|---|---|---|
| syska ProFI | Buchung, Fibu, Periode, Storno, OPos... | RAG-Pipeline |
| ERP | ERP, Warenwirtschaft, Auftrag, Kulimi... | DW 112 + erp-support@sopra-system.com |
| EVS | EVS, Zeiterfassung | DW 20 + evs-support@sopra-system.com |
| HR | HR, Personal, Urlaub, Gehalt... | DW 116 + hr-support@sopra-system.com |
| IT | Computer, Netzwerk, Drucker, Login... | DW 115 + it-support@sopra-system.com |
| Verwaltung | Vertrag, Rechnung, Preis, Lizenz... | DW 26 + Stephan.Mueller@sopra-system.com |
| Telefonbuch | "Ich möchte X sprechen" | Erst E-Mail anbieten, dann bei Ablehnung DW |
| Verabschiedung | Nein danke, Tschüss... | Farewell TwiML |

## Latenz-Analyse — Ergebnisse (16.04.2026)

### Messmethode
Strukturiertes Cloud Logging via `latency_logger.py` (LATENCY_LOGGING=true).
Gemessen: alle Segmente innerhalb `/call/process`.

### Messwerte

| Segment | Gemessen | Bewertung |
|---|---|---|
| firestore_read | 38–108 ms | ✅ Unkritisch |
| rag_start (Overhead) | 33–136 ms | ✅ Unkritisch |
| Vertex AI Search (rag_done) | 422–574 ms | ✅ Gut |
| Gemini 2.5 Flash (llm_done) | 1024–1232 ms | ✅ Gut |
| tts_ready | 58–87 ms | ✅ Unkritisch |
| **Gesamt /call/process** | **1614–2138 ms** | ✅ Backend schnell |

### Fazit
Das Backend ist **nicht** der Flaschenhals. Die ~15 Sekunden beim echten Anruf
entstehen primär durch Twilio:

| Quelle | Geschätzte Zeit | Optimierbar |
|---|---|---|
| Twilio STT (Chirp) | ~5–8 s | Bedingt |
| speechTimeout (Stille-Erkennung) | bis 10 s | ✅ → auf 3 s reduziert |
| TTS Journey-F Generierung | ~1–2 s | Bedingt |
| Backend (RAG + LLM) | ~2 s | Bereits optimiert |

## Fixes dieser Session (16.04.2026)

1. **latency_logger.py** implementiert in `app/utils/` — ein/ausschaltbar per `LATENCY_LOGGING` ENV-Var
2. **Logging auf stderr** umgestellt (`_cloud_logger.info` statt `print`)
3. **speechTimeout** von 10s auf 3s reduziert → erwartete Latenz ~7–8s statt 15s
4. Debug-Logs (`DEBUG_PROCESS_REACHED`) temporär eingebaut — **vor nächstem Release entfernen**

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

## NÄCHSTE SESSION — Offene Punkte (Reihenfolge)

### 1. Nachbereitung Latenz-Analyse ← SOFORT
- Echten Testanruf machen: gefühlte Latenz mit speechTimeout=3s prüfen
- Falls Anrufer abgeschnitten wird: auf 4–5s anpassen
- `LATENCY_LOGGING=false` setzen nach Abschluss
- Debug-Logs (`DEBUG_PROCESS_REACHED`) aus `call_router.py` entfernen

### 2. Weitere Latenz-Optimierungen (optional)
- TTS Voice: `de-DE-Neural2-F` statt `Journey-F` → ~0.5s schneller
- Firestore-Roundtrip eliminieren: SpeechResult direkt als URL-Parameter
- STT-Modell: `latest_short` statt Chirp → schnellere Transkription

### 3. Multi-Datastore RAG (FIBU + ERP) ← GEPLANT
Konzept: Zwei getrennte Vertex AI Search Datastores statt einem.

**Neue Datastores:**
- `handbuecher-v2` (bereits vorhanden) → syska ProFI FIBU
- `handbuecher-erp` (neu anlegen) → ERP (NUG) Dokumentation

**Neue Env-Vars:**
```
VERTEX_SEARCH_DATASTORE_FIBU=handbuecher-v2
VERTEX_SEARCH_DATASTORE_ERP=handbuecher-erp
```

**Routing-Logik in rag_service.py:**
- FIBU-Keywords (Buchung, Konto, OPos...) → handbuecher-v2
- ERP-Keywords (Artikel, Auftrag, Lager...) → handbuecher-erp
- Schnittstellenfragen (z.B. "Rechnung aus ERP kommt nicht in Fibu") → beide Datastores, Ergebnisse zusammenführen

**Umsetzungsschritte:**
1. Datastore + Engine in GCP Console anlegen (global, Enterprise)
2. ERP-Doku in GCS hochladen + indexieren
3. Env-Vars in Cloud Run setzen
4. rag_service.py: `_detect_datastore()` Funktion + dual-query bei "both"
5. System-Prompt um FIBU↔ERP Integrationskontext erweitern
6. test_scenarios.bat um ERP-Schnittstellenfragen erweitern

**Hintergrund:** FIBU ist an ERP angebunden — Ausgangsrechnungen aus ERP
erzeugen automatisch OPos in der FIBU. Agent muss beide Kontexte kennen.

### 4. E-Mail Service implementieren ← NÄCHSTES HAUPTZIEL
Neues File: `app/services/email_service.py` via SendGrid

Neue Env-Vars:
```
SENDGRID_API_KEY=...
```

E-Mail Adressen:
- ERP Support: erp-support@sopra-system.com
- EVS Support: evs-support@sopra-system.com
- HR Support: hr-support@sopra-system.com
- IT Support: it-support@sopra-system.com
- Verwaltung: Stephan.Mueller@sopra-system.com

### 4. Outlook-Kalender Integration ← WARTET AUF IT-ADMIN
Ansprechpartner: Patrick Münchhoff, DW 82
Benötigt: Azure App Registration mit Calendars.Read

Technischer Plan:
- Cloud Scheduler alle 15 Min → liest Outlook → schreibt Status in Firestore
- Firestore: calendar_status/Stephan.Mueller@sopra-system.com
- Felder: status (verfügbar/meeting/abwesend), bis (Uhrzeit)

Benötigte Env-Vars:
```
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
OUTLOOK_USER_EMAIL=Stephan.Mueller@sopra-system.com
```

### 5. Qualität
- Szenario 7 verfeinern: Verwaltungs-Anfragen vs. FIBU/OPos besser trennen
  - "Rechnung an Kunden" = OPos/FIBU
  - "Unsere Rechnung, Wartungsvertrag, Lizenz" = Verwaltung → Stephan Müller
- Durchwahl-Aussprache: SSML `<say-as interpret-as="telephone">` in TwiML
- Supportfälle 6–8 hochladen:
  ```cmd
  gsutil cp supportfaelle_syska_profi.txt gs://boxwood-mantra-489408-c0-handbuecher/
  ```
- Intent-Classifier: FIBU / OPos / Kore / Anbu / Sonstiges

### 6. Infrastruktur
- Error Handling & Cloud Logging Alerts
- Health Checks einrichten

## Wichtige Architektur-Entscheidungen

- Vertex AI Search läuft unter locations/global
- Gemini läuft unter us-central1
- Enterprise Edition → Extractive Answers → vollständige Textpassagen
- Firestore: Conversation Memory + Pending-Cache für Redirect
- Telefonbuch direkt im System-Prompt als Text (35 Einträge)
- XML-Escaping in twiml_builder.py verhindert abgeschnittene Antworten
- Keine direkte Weiterleitung möglich — Agent nennt Durchwahl oder bietet E-Mail
- MCP-Server: noch nicht integriert (Latenz-Overhead, Gemini nutzt Function Calling nativ)
- speechTimeout=3s — Haupthebel Latenz (von ~15s auf ~7s erwartet)
- PowerShell in VS Code → immer Command Prompt verwenden
- Test: test_scenarios.bat im Projektordner ausführen
