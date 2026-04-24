# KI-Telefon-Agent — Projektstand 24.04.2026

## Infrastruktur

| Komponente | Wert |
|---|---|
| GCP Projekt | boxwood-mantra-489408-c0 |
| Cloud Run | telefon-agent / europe-west3 |
| URL | https://telefon-agent-1051648887841.europe-west3.run.app |
| Bucket | gs://boxwood-mantra-489408-c0-handbuecher/ |
| Vertex AI Search FIBU | handbuecher-engine → handbuecher-v2 (Enterprise ✅), Location: global |
| Vertex AI Search ERP | erp-engine → handbuecher-erp (Enterprise ✅), Location: global |
| Firestore | Conversation Memory + Pending-Cache + pending_contact + absence + oauth_states |
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
VERTEX_SEARCH_DATASTORE_FIBU=handbuecher-v2
VERTEX_SEARCH_DATASTORE_ERP=handbuecher-erp
STT_LANGUAGE=de-DE
STT_MODEL=chirp
TTS_VOICE=de-DE-Journey-F          ← neu (war: Neural2-F)
TTS_SPEAKING_RATE=1.0
RAG_TOP_K=5
RAG_MAX_TOKENS=400
LLM_TEMPERATURE=0.0
LATENCY_LOGGING=false
SENDGRID_API_KEY=SG.xxx... (gesetzt)
EMAIL_FROM=stn.mueller@gmail.com     ← temporär, bis DNS für ki-agent@sopra-system.com
EMAIL_FROM_NAME=Sofia – Assistent Stephan Müller
GOOGLE_CLIENT_ID=1051648887841-0iudban8gq0c8k0vohiplvea3k0i7jrd.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-... (gesetzt)
ALLOWED_EMAIL=stn.mueller@gmail.com
APP_SECRET_KEY=sofia-secret-2026-... (gesetzt)
BASE_URL=https://telefon-agent-1051648887841.europe-west3.run.app
```

## Projektstruktur

```
app/
├── data/
│   └── telefonbuch.csv
├── routers/
│   ├── call_router.py           ← Twilio Webhooks + Routing + /call/process_contact
│   └── app_router.py            ← PWA Backend: Google OAuth + Abwesenheits-CRUD
├── services/
│   ├── rag_service.py           ← LLM + RAG + _detect_datastore() + Abwesenheitscheck
│   ├── memory_service.py        ← Firestore: Memory + save/get/update_pending_contact()
│   ├── email_service.py         ← SendGrid E-Mail Service
│   ├── absence_service.py       ← Firestore CRUD für Abwesenheiten + build_sofia_text()
│   └── phonebook_service.py
├── static/
│   ├── index.html               ← PWA Frontend (Sofia Abwesenheits-App)
│   ├── manifest.json            ← PWA Manifest
│   └── sw.js                   ← Service Worker
└── utils/
    ├── twiml_builder.py
    └── latency_logger.py
test_scenarios.bat               ← 13 Szenarien (inkl. 9a/9b, 10a/10b/10c, 11–13)
upload_erp_v4.bat                ← ERP Doku Upload (für künftige Updates)
```

## Gesprächsflow (aktuell implementiert)

```
POST /call/incoming
→ Abwesenheitscheck → falls aktiv: Abwesenheitshinweis in Begrüßung
→ "Hallo, mein Name ist Sofia, ich bin der AI-Assistent von Stephan Müller."

POST /call/transcribe
→ STT → STT-Normalisierung (z.B. "Stefan" → "Stephan") → Redirect zu /call/process

POST /call/process
→ 1. pending_contact Stage prüfen (vor allem anderen)
     - stage="anliegen" → Anliegen speichern, Kontaktdaten abfragen
     - stage="kontakt_retry" → Rückrufnummer nochmals abfragen (max. 1x)
→ 2. Telefonbuch-Intent erkennen (_detect_phonebook_intent)
     - Match in telefonbuch.csv → pending_contact anlegen (category="phonebook", stage="anliegen")
     - "Ich habe [Person] gefunden. Was ist der Anlass Ihres Anrufs?"
     - Kein Match → weiter zu RAG
→ 3. Wortanzahl prüfen (MIN_ANLIEGEN_WORDS)
     - ≥ 15 Wörter → direkt Kontaktdaten abfragen
     - < 15 Wörter → erst Anliegen abfragen
→ 4. Keyword-Routing (ERP/EVS/HR/IT/Verwaltung)
→ 5. Kein Match → RAG-Pipeline (_detect_datastore → FIBU oder ERP oder beide)
→ 6. Verabschiedung bei "Nein danke / Tschüss" → freundlicher Abschluss + Hangup

POST /call/process_contact
→ Kontaktdaten extrahieren (nur Telefon)
→ "Ja gerne" ohne Nummer → einmalige Nachfrage (stage=kontakt_retry)
→ Nach 2. Versuch ohne Nummer → Fallback auf Twilio From
→ Bei Ablehnung → Durchwahl nennen
→ Bei Zustimmung → E-Mail senden (bei phonebook: direkt an person_email) → Abschluss
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
| Telefonbuch | sprechen, möchte/würde/will/kann ich X sprechen, suche, verbinden | person_email aus telefonbuch.csv | wird genannt |
| Verabschiedung | Nein danke, Tschüss... | — | Hangup |

## Multi-Datastore RAG (_detect_datastore)

| Frage-Typ | Datastore |
|---|---|
| FIBU-Keywords (Buchung, Storno, OPos, Periode...) | handbuecher-v2 |
| ERP-Keywords (Auftrag, Inventur, Kulimi, Einkauf...) | handbuecher-erp |
| Schnittstellen-Keywords (FIBU↔ERP, Buchungsübergabe...) | beide (concateniert, RAG_TOP_K/2 je) |
| Default | handbuecher-v2 |

## E-Mail Format (SendGrid)

| Feld | Wert |
|---|---|
| Absender | stn.mueller@gmail.com (temporär) |
| Absendername | Sofia – Assistent Stephan Müller |
| Header | "Sofia – Anruf-Weiterleitung / Digitaler Assistent von Stephan Müller" |
| Inhalt | Anrufer-Nr, Rückruf-Tel (aus STT, Fallback: Twilio From), Zeitpunkt, Kategorie, Gesprächszusammenfassung |
| Footer | "Diese E-Mail wurde automatisch von Sofia, dem digitalen Assistenten von Stephan Müller, generiert." |
| Phonebook-Kategorie | E-Mail geht direkt an person_email aus telefonbuch.csv (recipient_override) |

## Abschlusstext je Kategorie

| Kategorie | Text |
|---|---|
| ERP | "Der ERP-Support wird sich in Kürze bei Ihnen melden." |
| EVS | "Der EVS-Support wird sich in Kürze bei Ihnen melden." |
| HR | "Der HR-Support wird sich in Kürze bei Ihnen melden." |
| IT | "Der IT-Support wird sich in Kürze bei Ihnen melden." |
| Verwaltung | "Herr Müller wird sich in Kürze bei Ihnen melden." |
| Phonebook | "Vielen Dank. Ihr Anliegen wird direkt weitergeleitet. Auf Wiederhören." |

## Firestore Collections

| Collection | Zweck |
|---|---|
| conversations/{CallSid} | Gesprächsverlauf (Memory) |
| pending/{CallSid} | SpeechResult Zwischenspeicher |
| pending_contact/{CallSid} | stage + anliegen + category + from_number + person_name + person_email |
| absence/{id} | Abwesenheiten (type, start, end, note, created_at) |
| oauth_states/{state} | OAuth State (TTL 10 Min, verhindert Multi-Instanz-Problem) |

### pending_contact Felder
```
category:      erp | evs | hr | it | verwaltung | phonebook
stage:         anliegen | kontakt | kontakt_retry
speech_result: originale erste Aussage
anliegen:      geschildertes Problem
from_number:   Twilio From-Nummer
person_name:   Name aus telefonbuch.csv (nur bei phonebook)
person_email:  E-Mail aus telefonbuch.csv (nur bei phonebook)
timestamp:     Erstellungszeitpunkt
```

### absence Felder
```
type:        urlaub | meeting | abwesend | dienstreise
start:       ISO-8601 datetime (z.B. "2026-04-25T09:00")
end:         ISO-8601 datetime oder date (Meeting: Uhrzeit, sonst: Datum)
note:        optional
created_at:  timestamp
```

## Sofia Handy-App (PWA)

| Komponente | Details |
|---|---|
| URL | https://telefon-agent-1051648887841.europe-west3.run.app/app/ |
| Auth | Google OAuth (nur stn.mueller@gmail.com) |
| iPhone | Als PWA zum Homescreen hinzufügen (Safari → Teilen → Zum Home-Bildschirm) |
| Funktion | Abwesenheit eintragen (Urlaub/Meeting/Abwesend/Dienstreise) mit Von–Bis |
| Sofia-Integration | Abwesenheitscheck beim Anruf → Sofia informiert Anrufer automatisch |

### Sofia-Texte je Abwesenheitstyp
```
Urlaub:      "Herr Müller ist im Urlaub und ab [Datum] wieder erreichbar."
Meeting:     "Herr Müller ist gerade im Meeting und ab [Uhrzeit] Uhr wieder erreichbar."
Abwesend:    "Herr Müller ist derzeit abwesend und ab [Datum] wieder erreichbar."
Dienstreise: "Herr Müller ist auf Dienstreise und ab [Datum] wieder erreichbar."
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

Budget-Alert: €15/Monat ✅

## Wichtige Fixes dieser Session (24.04.2026)

- **Phonebook-Intent Fix:** `\bsprechen\b` greift jetzt ohne Modalverb → natürliche Sprache wie "Stephan Müller sprechen" wird erkannt
- **Halluzinations-Sperre:** LLM darf nicht mehr behaupten, eine E-Mail verschickt zu haben
- **Abwesenheitscheck:** `answer_question()` prüft beim ersten Turn Firestore auf aktive Abwesenheit
- **Verabschiedung:** SYSTEM_PROMPT ergänzt → Sofia verabschiedet sich freundlich bei "Nein danke"
- **TTS-Stimme:** `de-DE-Journey-F` (war: Neural2-F) — klingt natürlicher, weniger AB-artig
- **AI-Assistent:** Begrüßung geändert von "digitaler Assistent" zu "AI-Assistent"
- **PWA OAuth State:** oauth_states in Firestore (war: In-Memory) → Multi-Instanz-sicher ✅

## NÄCHSTE SESSION — Offene Punkte (Reihenfolge)

### 1. Journey-F Testanruf auswerten
Falls Journey-F nicht reicht → ElevenLabs Integration evaluieren ($22/Monat Creator Plan)

### 2. Qualität
- Szenario 7 verfeinern: "Rechnung an Kunden" = FIBU, "Wartungsvertrag/Lizenz" = Verwaltung
- SSML `<say-as interpret-as="telephone">` für Durchwahl-Aussprache
- MIN_ANLIEGEN_WORDS Schwellenwert in Praxis testen und ggf. anpassen
- Ticketnummer-Vergabe bei E-Mail (Vorstufe Helpdesk)

### 3. eval_agent.py
Automatisierter Test-Loop — sinnvoll sobald Basis-Flow stabil.

### 4. Custom Domain
`sofia.sopra-system.com` für die PWA App — GCP Cloud Run unterstützt Custom Domains direkt.

### 5. Outlook-Kalender Integration
Azure App Registration mit Calendars.Read benötigt. Bei Ben nachfragen, wenn Agent stabil.

## Wichtige Architektur-Entscheidungen

- Agent-Name: **Sofia** (AI-Assistent von Stephan Müller)
- Vertex AI Search: 2 Datastores — FIBU (`handbuecher-v2`) + ERP (`handbuecher-erp`)
- Nur unterstützte Dateitypen in GCS: `docx, pdf, pptx, txt, xlsx` (kein `.doc`)
- E-Mail-Adresse wird nicht per Sprache erfasst — zu fehleranfällig (STT)
- Rückrufnummer: aus STT extrahiert, Fallback: Twilio `From`
- Kontaktdaten-Flow: Anliegen (bei < 15 Wörtern) → Kontaktdaten → E-Mail ODER Durchwahl
- "Ja gerne" ohne Nummer → einmalige Nachfrage, dann Fallback auf Twilio From
- Telefonbuch-Flow: Intent-Erkennung per Regex (`\bsprechen\b` + Modalverben) → find_in_text() → Anliegen → Rückrufnummer → E-Mail direkt an Person
- Gesprächszusammenfassung per Gemini in E-Mail
- Durchwahl nur als letzter Fallback wenn Anrufer E-Mail ablehnt
- Multi-Datastore RAG: _detect_datastore() wählt FIBU/ERP/beide dynamisch
- speechTimeout=3s (FIBU-Flow), 7s (Routing-Flow)
- PowerShell in VS Code → immer Command Prompt verwenden
- Claude Code: Plan-Modus für komplexere Änderungen verwenden
- Test: test_scenarios.bat im Projektordner ausführen
- DSGVO: Kein "Krank" als Abwesenheitstyp — stattdessen "Abwesend" (neutral)
- OAuth State: Firestore statt In-Memory (Multi-Instanz-sicher)
