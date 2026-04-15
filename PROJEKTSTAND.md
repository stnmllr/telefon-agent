# KI-Telefon-Agent — Projektstand 15.04.2026

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

## Aktueller Status: ✅ ALLE 8 TEST-SZENARIEN BESTANDEN

Alle Szenarien in test_scenarios.bat laufen korrekt durch:
- syska ProFI Support: Schritt-für-Schritt Hilfe mit Rückfragen
- Steuerkonto-Differenz: Diagnose-Frage wird gestellt
- Telefonbuch: E-Mail wird zuerst angeboten, dann Durchwahl
- ERP / EVS / IT / Verwaltung: Durchwahl + E-Mail Angebot
- Verabschiedung: korrekt erkannt

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
│   ├── rag_service.py           ← LLM + RAG + System-Prompt + Telefonbuch im Prompt
│   ├── memory_service.py        ← Firestore Conversation Memory
│   └── phonebook_service.py     ← Telefonbuch-Lookup (für zukünftige Nutzung)
└── utils/
    └── twiml_builder.py         ← TwiML Response Builder mit XML-Escaping
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

## Routing-Logik (aktiv im System-Prompt)

| Kategorie | Erkennungsmerkmale | Aktion |
|---|---|---|
| syska ProFI | Buchung, Fibu, Periode, Storno, OPos... | RAG-Pipeline |
| ERP | ERP, Warenwirtschaft, Auftrag, Kulimi... | DW 112 + E-Mail erp-support@sopra-system.com |
| EVS | EVS, Zeiterfassung | DW 20 + E-Mail evs-support@sopra-system.com |
| HR | HR, Personal, Urlaub, Gehalt... | DW 116 + E-Mail hr-support@sopra-system.com |
| IT | Computer, Netzwerk, Drucker, Login... | DW 115 + E-Mail it-support@sopra-system.com |
| Verwaltung | Vertrag, Rechnung, Preis, Lizenz... | DW 26 + E-Mail Stephan.Mueller@sopra-system.com |
| Telefonbuch | "Ich möchte X sprechen" | Erst E-Mail anbieten, dann bei Ablehnung DW nennen |
| Verabschiedung | Nein danke, Tschüss... | Farewell TwiML |

## Wichtige Fixes dieser Session

1. XML-Escaping in twiml_builder.py — Anführungszeichen haben TwiML abgeschnitten
2. Telefonbuch-Shortcut entfernt — LLM übernimmt jetzt korrekt die E-Mail-Logik
3. max_output_tokens auf 1200 erhöht
4. Test-Fallback in /call/process — SpeechResult direkt als Parameter möglich
5. test_scenarios.bat finalisiert und committed

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

### 1. E-Mail Service implementieren ← NÄCHSTES ZIEL
Der Agent bietet E-Mails an aber kann sie noch nicht wirklich versenden.
Neues File: app/services/email_service.py via SendGrid

Neue Env-Vars in Cloud Run:
```
SENDGRID_API_KEY=...
```

E-Mail Adressen (bereits im Telefonbuch):
- ERP Support: erp-support@sopra-system.com
- EVS Support: evs-support@sopra-system.com
- HR Support: hr-support@sopra-system.com
- IT Support: it-support@sopra-system.com
- Verwaltung: Stephan.Mueller@sopra-system.com

### 2. Outlook-Kalender Integration ← WARTET AUF IT-ADMIN
Ansprechpartner: Patrick Münchhoff, DW 82
Benötigt: Azure App Registration mit Calendars.Read Berechtigung

Technischer Plan:
- Google Cloud Scheduler alle 15 Min → liest Outlook → schreibt Status in Firestore
- Firestore: calendar_status/Stephan.Mueller@sopra-system.com
- Felder: status (verfügbar/meeting/abwesend), bis (Uhrzeit)
- Agent liest Status beim Anruf aus Firestore

Benötigte Env-Vars nach Freigabe:
```
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
OUTLOOK_USER_EMAIL=Stephan.Mueller@sopra-system.com
```

### 3. Durchwahl-Aussprache verbessern
TTS liest Durchwahlen noch nicht optimal.
Nächster Versuch: SSML `<say-as interpret-as="telephone">` direkt im TwiML

### 4. Szenario 7 verfeinern
Verwaltungs-Anfragen werden noch zu oft als FIBU/OPos interpretiert.
System-Prompt Unterscheidung verbessern:
- "Rechnung an Kunden" = OPos/FIBU
- "Unsere Rechnung, Wartungsvertrag, Lizenz" = Verwaltung → Stephan Müller

### 5. KI-Testagent (Artefakt)
Claude-Artefakt das test_scenarios.bat automatisch auswertet
und Verbesserungsvorschläge macht — nach E-Mail Service implementieren.

### 6. Supportfälle hochladen
Fall 6-8 in GCS Bucket:
```cmd
gsutil cp supportfaelle_syska_profi.txt gs://boxwood-mantra-489408-c0-handbuecher/
```

### 7. Error Handling & Monitoring
Cloud Logging Alerts, Health Checks

### 8. Intent-Classifier
FIBU / OPos / Kore / Anbu / Sonstiges

## Wichtige Architektur-Entscheidungen

- Vertex AI Search läuft unter locations/global
- Gemini läuft unter us-central1
- Enterprise Edition → Extractive Answers → vollständige Textpassagen
- Firestore: Conversation Memory + Pending-Cache für Redirect
- Telefonbuch direkt im System-Prompt als Text (35 Einträge)
- XML-Escaping in twiml_builder.py verhindert abgeschnittene Antworten
- Keine direkte Weiterleitung möglich — Agent nennt Durchwahl oder bietet E-Mail
- PowerShell in VS Code → immer Command Prompt verwenden
- Test: test_scenarios.bat im Projektordner ausführen
