# KI-Telefon-Agent — Projektstand 21.04.2026

## Infrastruktur

| Komponente | Wert |
|---|---|
| GCP Projekt | boxwood-mantra-489408-c0 |
| Cloud Run | telefon-agent / europe-west3 |
| URL | https://telefon-agent-1051648887841.europe-west3.run.app |
| Bucket | gs://boxwood-mantra-489408-c0-handbuecher/ |
| Vertex AI Search FIBU | handbuecher-engine → handbuecher-v2 (Enterprise ✅), Location: global |
| Vertex AI Search ERP | erp-engine → handbuecher-erp (Enterprise ✅), Location: global |
| Firestore | Conversation Memory + Pending-Cache + pending_contact |
| Twilio | +49 89 41432469, Webhook auf /call/incoming |
| GitHub | stnmllr/telefon-agent, CI/CD via GitHub Actions (Push main → auto-deploy) |
| Service Account | 1051648887841-compute@developer.gserviceaccount.com |
| SendGrid | Free Plan (100 Mails/Tag), Sender: stn.mueller@gmail.com (verifiziert) |

## GCS Bucket Struktur

```
gs://boxwood-mantra-489408-c0-handbuecher/
  (root)         ← syska ProFI FIBU Handbücher (original, handbuecher-v2)
  fibu/          ← ProFi Doku (neu hochgeladen, auch in handbuecher-v2 importiert)
  erp/
    eevolution/  ← eEvolution Kerndoku
    auftrag/     ← Auftragsverwaltung
    artikel/     ← Artikelstamm
    schnittstellen/ ← FIBU↔ERP Integration
    einkauf/     ← Einkauf
    kulimi/      ← Kulimi
    chargen/     ← Chargenverwaltung
    inventur/    ← Inventur
    preiskon/    ← Preiskonditionen
```

**Hinweis:** Nur unterstützte Dateitypen hochgeladen: `docx, pdf, pptx, txt, xlsx`
`.doc` Dateien wurden ausgeschlossen (nicht von Vertex AI Search unterstützt)

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
EMAIL_FROM=stn.mueller@gmail.com     ← temporär, bis DNS für ki-agent@sopra-system.com
EMAIL_FROM_NAME=Sofia – Assistent Stephan Müller
```

**Noch hinzuzufügen (nach Code-Implementierung):**
```
VERTEX_SEARCH_DATASTORE_FIBU=handbuecher-v2
VERTEX_SEARCH_DATASTORE_ERP=handbuecher-erp
```

## Projektstruktur

```
app/
├── data/
│   └── telefonbuch.csv
├── routers/
│   └── call_router.py           ← Twilio Webhooks + Routing + /call/process_contact
├── services/
│   ├── rag_service.py           ← LLM + RAG + extract_contact_data() + summarize_conversation()
│   ├── memory_service.py        ← Firestore: Memory + save/get/update_pending_contact()
│   ├── email_service.py         ← SendGrid E-Mail Service
│   └── phonebook_service.py
└── utils/
    ├── twiml_builder.py
    └── latency_logger.py
test_scenarios.bat               ← 10 Szenarien (inkl. 9a/9b, 10a/10b/10c)
upload_erp_v4.bat                ← ERP Doku Upload (für künftige Updates)
```

## Gesprächsflow (aktuell implementiert)

```
POST /call/incoming
→ "Hallo, mein Name ist Sofia, ich bin der digitale Assistent von Stephan Müller."

POST /call/transcribe
→ STT → Redirect zu /call/process

POST /call/process
→ 1. pending_contact Stage prüfen (vor allem anderen)
     - stage="anliegen" → Anliegen speichern, Kontaktdaten abfragen
→ 2. Wortanzahl prüfen (MIN_ANLIEGEN_WORDS)
     - ≥ 15 Wörter → direkt Kontaktdaten abfragen
     - < 15 Wörter → erst Anliegen abfragen
→ 3. Keyword-Routing (ERP/EVS/HR/IT/Verwaltung)
→ 4. Kein Match → RAG-Pipeline (syska ProFI FIBU)

POST /call/process_contact
→ Kontaktdaten extrahieren (nur Telefon)
→ Bei Ablehnung → Durchwahl nennen
→ Bei Zustimmung → E-Mail senden → Abschluss mit Team-Namen
```

## Routing-Logik

| Kategorie | Keywords | E-Mail | Durchwahl |
|---|---|---|---|
| syska ProFI | Buchung, Fibu, Periode, Storno, OPos... | — | — |
| ERP | ERP, Warenwirtschaft, Auftrag, Kulimi... | erp-support@sopra-system.com | 112 |
| EVS | EVS, Zeiterfassung | evs-support@sopra-system.com | 20 |
| HR | HR, Personal, Urlaub, Gehalt... | hr-support@sopra-system.com | 116 |
| IT | Computer, PC, Laptop, Drucker, Netzwerk, Login, Passwort... | it-support@sopra-system.com | 115 |
| Verwaltung | Vertrag, Rechnung, Preis, Lizenz... | Stephan.Mueller@sopra-system.com | 26 |
| Telefonbuch | "Ich möchte X sprechen" | — | wird genannt |
| Verabschiedung | Nein danke, Tschüss... | — | — |

## E-Mail Format (SendGrid)

| Feld | Wert |
|---|---|
| Absender | stn.mueller@gmail.com (temporär) |
| Absendername | Sofia – Assistent Stephan Müller |
| Header | "Sofia – Anruf-Weiterleitung / Digitaler Assistent von Stephan Müller" |
| Inhalt | Anrufer-Nr, Rückruf-Tel (aus STT, Fallback: Twilio From), Zeitpunkt, Kategorie, Gesprächszusammenfassung |
| Footer | "Diese E-Mail wurde automatisch von Sofia, dem digitalen Assistenten von Stephan Müller, generiert." |

## Abschlusstext je Kategorie

| Kategorie | Text |
|---|---|
| ERP | "Der ERP-Support wird sich in Kürze bei Ihnen melden." |
| EVS | "Der EVS-Support wird sich in Kürze bei Ihnen melden." |
| HR | "Der HR-Support wird sich in Kürze bei Ihnen melden." |
| IT | "Der IT-Support wird sich in Kürze bei Ihnen melden." |
| Verwaltung | "Herr Müller wird sich in Kürze bei Ihnen melden." |

## Firestore Collections

| Collection | Zweck |
|---|---|
| conversations/{CallSid} | Gesprächsverlauf (Memory) |
| pending/{CallSid} | SpeechResult Zwischenspeicher |
| pending_contact/{CallSid} | stage + anliegen + category + from_number |

### pending_contact Felder
```
category:      erp | evs | hr | it | verwaltung
stage:         anliegen | kontakt
speech_result: originale erste Aussage
anliegen:      geschildertes Problem
from_number:   Twilio From-Nummer
timestamp:     Erstellungszeitpunkt
```

## Kosten (monatlich, Schätzung)

| Komponente | Kosten |
|---|---|
| Vertex AI Search Enterprise (2 Datastores) | ~$4–10 |
| Gemini 2.5 Flash | ~$1–2 |
| Cloud Run | ~$0 |
| Firestore | ~$0 |
| Twilio Nummer + Anrufe | ~$1.50 |
| SendGrid | ~$0 (Free Plan) |
| **Gesamt** | **~$7–14/Monat** |

Budget-Alert: €10/Monat eingerichtet ✅ → ggf. auf €15 erhöhen

## NÄCHSTE SESSION — Offene Punkte (Reihenfolge)

### 1. Multi-Datastore RAG Code implementieren ← HAUPTZIEL
Infrastruktur ist bereit — jetzt Code anpassen:

**Prompt für Claude Code:**
- `rag_service.py`: Neue Funktion `_detect_datastore(question)` 
  - FIBU-Keywords → `handbuecher-v2`
  - ERP-Keywords → `handbuecher-erp`
  - Schnittstellenfragen → beide Datastores, Ergebnisse zusammenführen
- Neue ENV-Vars in Cloud Run setzen:
  ```
  VERTEX_SEARCH_DATASTORE_FIBU=handbuecher-v2
  VERTEX_SEARCH_DATASTORE_ERP=handbuecher-erp
  ```
- `answer_question()` anpassen: datastore dynamisch wählen
- test_scenarios.bat um ERP-Fragen erweitern

### 2. ERP Import-Status prüfen
Operation: `import-documents-16868525097247230552`
```cmd
for /f "tokens=*" %i in ('gcloud auth print-access-token --project=boxwood-mantra-489408-c0') do set TOKEN=%i
curl -X GET "https://discoveryengine.googleapis.com/v1/projects/1051648887841/locations/global/collections/default_collection/dataStores/handbuecher-erp/branches/0/operations/import-documents-16868525097247230552" -H "Authorization: Bearer %TOKEN%" -H "x-goog-user-project: boxwood-mantra-489408-c0"
```

### 3. DNS-Records für ki-agent@sopra-system.com ← WARTET AUF PATRICK
Patrick Münchhoff, DW 82 — 4 CNAME/TXT Records in SendGrid Dashboard.
Nach DNS-Setup: `EMAIL_FROM` in Cloud Run auf `ki-agent@sopra-system.com` ändern.

### 4. Budget-Alert prüfen
Zweiter Datastore kostet mehr — Alert ggf. auf €15/Monat erhöhen.

### 5. Outlook-Kalender Integration ← WARTET AUF PATRICK
Azure App Registration mit Calendars.Read benötigt.

### 6. Qualität
- Szenario 7 verfeinern: "Rechnung an Kunden" = FIBU, "Wartungsvertrag/Lizenz" = Verwaltung
- SSML `<say-as interpret-as="telephone">` für Durchwahl-Aussprache
- MIN_ANLIEGEN_WORDS Schwellenwert in Praxis testen und ggf. anpassen
- Ticketnummer-Vergabe bei E-Mail (Vorstufe Helpdesk)

### 7. eval_agent.py
Automatisierter Test-Loop — sinnvoll sobald Basis-Flow stabil.

## Wichtige Architektur-Entscheidungen

- Agent-Name: **Sofia** (digitaler Assistent von Stephan Müller)
- Vertex AI Search: 2 Datastores — FIBU (`handbuecher-v2`) + ERP (`handbuecher-erp`)
- Nur unterstützte Dateitypen in GCS: `docx, pdf, pptx, txt, xlsx` (kein `.doc`)
- E-Mail-Adresse wird nicht per Sprache erfasst — zu fehleranfällig (STT)
- Rückrufnummer: aus STT extrahiert, Fallback: Twilio `From`
- Kontaktdaten-Flow: Anliegen (bei < 15 Wörtern) → Kontaktdaten → E-Mail ODER Durchwahl
- Gesprächszusammenfassung per Gemini in E-Mail
- Durchwahl nur als letzter Fallback wenn Anrufer E-Mail ablehnt
- speechTimeout=3s (FIBU-Flow), 7s (Routing-Flow)
- PowerShell in VS Code → immer Command Prompt verwenden
- Test: test_scenarios.bat im Projektordner ausführen
