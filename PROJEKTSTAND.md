# KI-Telefon-Agent — Projektstand 14.04.2026

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

- Gemini 2.5 Flash aktiv — gute Antwortqualität
- Neue Begrüßung: "Guten Tag, Sie sind verbunden mit dem SOPRA System Assistenten. Ich bin ein Künstliche Intelligenz Assistent und helfe Ihnen gerne weiter. Was kann ich für Sie tun?"
- Telefonbuch mit 35 Einträgen inkl. E-Mail-Adressen direkt im System-Prompt
- Routing-Logik für alle Kategorien (syska, ERP, EVS, HR, IT, Verwaltung, Telefonbuch)
- Zwischenantwort "Einen Moment bitte..." bei langen Fragen (>5 Wörter)
- Kein Markdown in Antworten
- Schritt-für-Schritt Gesprächsführung mit Rückfragen
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

## Projektstruktur

```
app/
├── data/
│   └── telefonbuch.csv          ← Internes Telefonverzeichnis mit Durchwahlen + E-Mails
├── routers/
│   └── call_router.py           ← Twilio Webhooks + Routing-Logik
├── services/
│   ├── rag_service.py           ← LLM + RAG + System-Prompt
│   ├── memory_service.py        ← Firestore Conversation Memory
│   ├── phonebook_service.py     ← Telefonbuch-Lookup
│   └── email_service.py         ← (noch zu implementieren)
└── utils/
    └── twiml_builder.py         ← TwiML Response Builder
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
→ answer_question() aufrufen (RAG + LLM)
→ Antwort als TwiML zurückgeben
```

## Routing-Logik (aktiv im System-Prompt)

| Kategorie | Erkennungsmerkmale | Aktion |
|---|---|---|
| syska ProFI | Buchung, Fibu, Periode, Storno, OPos... | RAG-Pipeline |
| ERP | ERP, Warenwirtschaft, Auftrag, Kulimi... | DW 112 nennen oder E-Mail erp-support@sopra-system.com |
| EVS | EVS, Zeiterfassung | DW 20 nennen oder E-Mail evs-support@sopra-system.com |
| HR | HR, Personal, Urlaub, Gehalt... | DW 116 nennen oder E-Mail hr-support@sopra-system.com |
| IT | Computer, Netzwerk, Drucker, Login... | DW 115 nennen oder E-Mail it-support@sopra-system.com |
| Verwaltung | Vertrag, Rechnung, Preis, Lizenz... | DW 26 nennen oder E-Mail Stephan.Mueller@sopra-system.com |
| Telefonbuch | "Ich möchte X sprechen", "Durchwahl von X" | Direkt aus telefonbuch.csv antworten |
| Persönlich | Jemand möchte Stephan Müller sprechen | DW 26 nennen, keine direkte Weiterleitung möglich |
| Unklar | Alles andere | Rückfrage stellen |

## Offenes Problem: Durchwahl-Aussprache
TTS liest Durchwahlen wie "26" als "zweiundzwanzig" oder "zweisechste".
Bisherige Versuche: Leerzeichen, Komma, Bindestrich, Wörter — alle unzureichend.
→ Nächste Session: SSML `<say-as interpret-as="telephone">` in Twilio testen

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

## NÄCHSTE SESSION — Offene Punkte (Reihenfolge)

### 1. Durchwahl-Aussprache fixen ← ZUERST
SSML mit `<say-as interpret-as="telephone">` in Twilio testen:
```python
# In twiml_builder.py — Say-Tag mit SSML:
<Say language="de-DE" voice="Google.de-DE-Neural2-F">
  <say-as interpret-as="telephone">26</say-as>
</Say>
```
Twilio unterstützt SSML wenn der Text als SSML-String übergeben wird.

### 2. Outlook-Kalender Integration ← WARTET AUF IT-ADMIN
**Was fehlt:** Admin-Genehmigung für `Calendars.Read` in Microsoft 365
**Ansprechpartner:** Patrick Münchhoff, DW 82
**Was er tun muss:** Im Microsoft 365 Admin Center die Graph API Berechtigung
`Calendars.Read` für eine neue App Registration genehmigen.

**Technischer Plan nach Freigabe:**
- Neue Azure App Registration: `telefon-agent-kalender`
- Neues File: `app/services/calendar_service.py`
- Google Cloud Scheduler: alle 15 Min Kalender prüfen → Status in Firestore schreiben
- Firestore Dokument: `calendar_status/{user_email}` mit Feldern:
  `status` (verfügbar/meeting/abwesend), `bis` (Uhrzeit), `naechster_termin`
- Agent liest Status beim Anruf aus Firestore

**Env-Vars die dann nötig sind:**
```
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
OUTLOOK_USER_EMAIL=Stephan.Mueller@sopra-system.com
```

### 3. E-Mail Service implementieren
Neues File: `app/services/email_service.py`
Für alle Routing-Kategorien die E-Mails versenden sollen.
Empfehlung: SendGrid (einfacher) oder Gmail API (bereits in GCP)

**Neue Env-Vars:**
```
SENDGRID_API_KEY=...
```

### 4. Supportfälle-Dokument hochladen
Fall 6-8 (Steuerkonto-Differenz, UStVA, Monatsabschluss) wurden erstellt
aber noch nicht in den GCS Bucket hochgeladen:
```cmd
gsutil cp supportfaelle_syska_profi.txt gs://boxwood-mantra-489408-c0-handbuecher/
```
Danach Datastore neu indexieren.

### 5. Latenz weiter reduzieren
Aktuell ~13 Sekunden für LLM-Aufruf.
Optionen: RAG_TOP_K auf 3, budget_tokens auf 256, Gemini 2.5 Flash Lite testen

### 6. Error Handling & Monitoring
Cloud Logging Alerts, Health Checks

### 7. Intent-Classifier
FIBU / OPos / Kore / Anbu / Sonstiges

### 8. Multi-Agent Modell
Separater Agent pro Bereich

## Wichtige Architektur-Entscheidungen

- Vertex AI Search läuft unter locations/global
- Gemini läuft unter us-central1
- Enterprise Edition → Extractive Answers → vollständige Textpassagen
- Firestore: zwei Verwendungen — Conversation Memory + Pending-Cache
- Telefonbuch direkt im System-Prompt als Text (35 Einträge, klein genug)
- Keine direkte Weiterleitung möglich — Agent nennt nur Durchwahl
- PowerShell in VS Code → immer Command Prompt verwenden
