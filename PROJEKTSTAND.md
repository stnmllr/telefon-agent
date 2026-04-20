# KI-Telefon-Agent — Projektstand 20.04.2026

## Infrastruktur

| Komponente | Wert |
|---|---|
| GCP Projekt | boxwood-mantra-489408-c0 |
| Cloud Run | telefon-agent / europe-west3 |
| URL | https://telefon-agent-1051648887841.europe-west3.run.app |
| Bucket | gs://boxwood-mantra-489408-c0-handbuecher/ |
| Vertex AI Search | handbuecher-engine (Enterprise Edition ✅), Datastore: handbuecher-v2, Location: global |
| Firestore | Conversation Memory + Pending-Cache + pending_contact (neu) |
| Twilio | +49 89 41432469, Webhook auf /call/incoming |
| GitHub | stnmllr/telefon-agent, CI/CD via GitHub Actions (Push main → auto-deploy) |
| Service Account | 1051648887841-compute@developer.gserviceaccount.com |
| SendGrid | Free Plan (100 Mails/Tag), API Key gesetzt, Sender: stn.mueller@gmail.com (verifiziert) |

## Aktuelle Konfiguration (Cloud Run Env-Vars)

```
ENVIRONMENT=production
GCP_PROJECT_ID=boxwood-mantra-489408-c0
GCP_LOCATION=us-central1
GEMINI_MODEL=gemini-2.5-flash
VERTEX_SEARCH_DATASTORE=handbuecher-v2
STT_LANGUAGE=de-DE
STT_MODEL=chirp
TTS_VOICE=de-DE-Neural2-F
TTS_SPEAKING_RATE=1.0
RAG_TOP_K=5
RAG_MAX_TOKENS=400
LLM_TEMPERATURE=0.0
LATENCY_LOGGING=false
SENDGRID_API_KEY=SG.xxx... (gesetzt)
EMAIL_FROM=stn.mueller@gmail.com     ← temporär, bis DNS für ki-agent@sopra-system.com gesetzt
EMAIL_FROM_NAME=Sofia – Assistent Stephan Müller
```

## Projektstruktur

```
app/
├── data/
│   └── telefonbuch.csv
├── routers/
│   └── call_router.py           ← Twilio Webhooks + Routing-Logik + /call/process_contact (neu)
├── services/
│   ├── rag_service.py           ← LLM + RAG + extract_contact_data() + summarize_conversation()
│   ├── memory_service.py        ← Firestore: Conversation Memory + save/get_pending_contact()
│   ├── email_service.py         ← SendGrid E-Mail Service (neu)
│   └── phonebook_service.py
└── utils/
    ├── twiml_builder.py
    └── latency_logger.py
test_scenarios.bat               ← 10 Szenarien (inkl. 9a/9b, 10a/10b/10c)
```

## Architektur call_router.py

```
POST /call/incoming
→ Begrüßung: "Hallo, mein Name ist Sofia, ich bin der digitale Assistent von Stephan Müller."
→ STT aktivieren

POST /call/transcribe
→ STT-Qualität prüfen
→ Verabschiedung erkennen
→ Redirect zu /call/process

POST /call/process
→ [NEU] Zuerst: pending_contact Stage prüfen (noch buggy — siehe offene Punkte)
→ Routing-Kategorie erkennen (ERP/EVS/HR/IT/Verwaltung)
→ Bei Kategorie-Match: Anliegen abfragen → save_pending_contact(stage="anliegen")
→ Kein Match: RAG-Pipeline (syska ProFI FIBU)

POST /call/process_contact  ← NEU
→ SpeechResult lesen
→ Bei stage="kontakt": Kontaktdaten per Gemini extrahieren → E-Mail senden → Abschluss
→ Bei Ablehnung: Durchwahl nennen → Hangup
```

## Routing-Logik

| Kategorie | Erkennungsmerkmale | Aktion |
|---|---|---|
| syska ProFI | Buchung, Fibu, Periode, Storno, OPos... | RAG-Pipeline |
| ERP | ERP, Warenwirtschaft, Auftrag, Kulimi... | Anliegen → Kontakt → E-Mail an erp-support@sopra-system.com / DW 112 |
| EVS | EVS, Zeiterfassung | Anliegen → Kontakt → E-Mail an evs-support@sopra-system.com / DW 20 |
| HR | HR, Personal, Urlaub, Gehalt... | Anliegen → Kontakt → E-Mail an hr-support@sopra-system.com / DW 116 |
| IT | Computer, Netzwerk, Drucker, Login... | Anliegen → Kontakt → E-Mail an it-support@sopra-system.com / DW 115 |
| Verwaltung | Vertrag, Rechnung, Preis, Lizenz... | Anliegen → Kontakt → E-Mail an Stephan.Mueller@sopra-system.com / DW 26 |
| Telefonbuch | "Ich möchte X sprechen" | Erst E-Mail anbieten, dann bei Ablehnung DW |
| Verabschiedung | Nein danke, Tschüss... | Farewell TwiML |

## E-Mail Service (SendGrid)

| Feld | Wert |
|---|---|
| Absender | stn.mueller@gmail.com (temporär) → ki-agent@sopra-system.com (nach DNS) |
| Absendername | Sofia – Assistent Stephan Müller |
| Inhalt | Anrufer-Nr, Rückruf-Tel, E-Mail, Zeitpunkt, Kategorie, Anliegen, Gesprächszusammenfassung |
| Format | Plain Text + HTML |

## E-Mail Empfänger

| Kategorie | Empfänger |
|---|---|
| ERP | erp-support@sopra-system.com |
| EVS | evs-support@sopra-system.com |
| HR | hr-support@sopra-system.com |
| IT | it-support@sopra-system.com |
| Verwaltung | Stephan.Mueller@sopra-system.com |

## Firestore Collections

| Collection | Zweck |
|---|---|
| conversations/{CallSid} | Gesprächsverlauf (Memory) |
| pending/{CallSid} | SpeechResult Zwischenspeicher für Redirect |
| pending_contact/{CallSid} | Routing-Stage + Anliegen + from_number |

### pending_contact Dokument-Felder
```
category:    "erp" | "evs" | "hr" | "it" | "verwaltung"
stage:       "anliegen" | "kontakt"
speech_result: originale Frage des Anrufers
anliegen:    geschildertes Problem (wird in Stage "anliegen" ergänzt)
from_number: Twilio From-Nummer
timestamp:   Erstellungszeitpunkt
```

## Kosten (monatlich, Schätzung)

| Komponente | Kosten |
|---|---|
| Vertex AI Search Enterprise | ~$2–5 |
| Gemini 2.5 Flash | ~$1–2 |
| Cloud Run | ~$0 |
| Firestore | ~$0 |
| Twilio Nummer + Anrufe | ~$1.50 |
| SendGrid | ~$0 (Free Plan) |
| **Gesamt** | **~$5–10/Monat** |

Budget-Alert: €10/Monat eingerichtet ✅

## NÄCHSTE SESSION — Offene Punkte (Reihenfolge)

### 1. Bug: Stage-Prüfung in /call/process ← SOFORT
**Problem:** Nach "Ja, ich möchte das Problem schildern" landet der zweite
`/call/process` Aufruf in der normalen Pipeline statt den pending_contact-Stage zu lesen.

**Fix:** In `/call/process` als **allererstes** (vor Keyword-Erkennung und RAG):
`get_pending_contact(call_sid)` aufrufen (ohne delete).
- Wenn `stage == "anliegen"` → SpeechResult als `anliegen` speichern, stage auf `"kontakt"` setzen,
  TwiML: "Darf ich Ihre Rückruf-Nummer und E-Mail-Adresse notieren?"
  → Gather + Redirect zu `/call/process_contact`
- Wenn `stage == "kontakt"` → sollte nicht vorkommen, Fallback zu process_contact

### 2. Bug: "Computer" wird als HR statt IT erkannt
IT-Keywords prüfen und ergänzen: "computer", "startet nicht", "drucker", "netzwerk", "login", "passwort".
Reihenfolge der Kategorie-Prüfung: IT vor HR.

### 3. DNS-Records für ki-agent@sopra-system.com ← WARTET AUF PATRICK
Ansprechpartner: Patrick Münchhoff, DW 82

4 DNS-Records in SendGrid Dashboard (Settings → Sender Authentication):
```
CNAME  em4101.sopra-system.com        → u105946128.wl129.sendgrid.net
CNAME  s1._domainkey.sopra-system.com → s1.domainkey.u105946128.wl129.sendgrid.net
CNAME  s2._domainkey.sopra-system.com → s2.domainkey.u105946128.wl129.sendgrid.net
TXT    _dmarc.sopra-system.com        → v=DMARC1; p=quarantine;
```
Nach DNS-Setup: `EMAIL_FROM` in Cloud Run auf `ki-agent@sopra-system.com` ändern.

### 4. E-Mail Header anpassen
"KI-Telefon-Agent — Anruf-Weiterleitung / SOPRA System GmbH" →
"Sofia – Assistent Stephan Müller" in `email_service.py` HTML-Template.

### 5. Multi-Datastore RAG (FIBU + ERP) ← GEPLANT
Zweiter Vertex AI Search Datastore `handbuecher-erp` für ERP-Dokumentation.
ERP-Doku Upload von M:\doku (2,39 GB).
Routing: FIBU-Keywords → handbuecher-v2, ERP-Keywords → handbuecher-erp.

### 6. Outlook-Kalender Integration ← WARTET AUF IT-ADMIN
Ansprechpartner: Patrick Münchhoff, DW 82
Azure App Registration mit Calendars.Read benötigt.

### 7. Qualität
- Szenario 7 verfeinern: Verwaltungs-Anfragen vs. FIBU/OPos besser trennen
- SSML `<say-as interpret-as="telephone">` für Durchwahl-Aussprache
- Intent-Classifier: FIBU / OPos / Kore / Anbu / Sonstiges
- Ticketnummer-Vergabe bei E-Mail-Weiterleitung (Vorstufe Helpdesk)

### 8. Infrastruktur
- Error Handling & Cloud Logging Alerts
- Health Checks einrichten
- LATENCY_LOGGING nach weiteren Tests dauerhaft auf false

## Wichtige Architektur-Entscheidungen

- Agent-Name: Sofia (digitaler Assistent von Stephan Müller)
- Vertex AI Search läuft unter locations/global
- Gemini läuft unter us-central1
- Enterprise Edition → Extractive Answers → vollständige Textpassagen
- Firestore: Conversation Memory + Pending-Cache + pending_contact (3 Collections)
- Telefonbuch direkt im System-Prompt als Text (35 Einträge)
- XML-Escaping in twiml_builder.py verhindert abgeschnittene Antworten
- Keine direkte Weiterleitung möglich — Agent nennt Durchwahl nur als letzten Fallback
- Kontaktdaten-Flow: Anliegen → Kontaktdaten → E-Mail ODER Durchwahl bei Ablehnung
- Gesprächszusammenfassung per Gemini statt rohem Protokoll in E-Mail
- speechTimeout=3s (FIBU-Flow), 7s (Routing-Flow)
- PowerShell in VS Code → immer Command Prompt verwenden
- Test: test_scenarios.bat im Projektordner ausführen
