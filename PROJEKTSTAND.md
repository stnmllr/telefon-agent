# KI-Telefon-Agent — Projektstand 22.06.2026

## Infrastruktur

| Komponente | Wert |
|---|---|
| GCP Projekt | boxwood-mantra-489408-c0 |
| Cloud Run | telefon-agent / europe-west3 |
| URL | https://telefon-agent-1051648887841.europe-west3.run.app |
| Bucket | gs://boxwood-mantra-489408-c0-handbuecher/ |
| Vertex AI Search FIBU | handbuecher-engine → handbuecher-v2 (Enterprise ✅), Location: global |
| Vertex AI Search ERP | erp-engine → handbuecher-erp (Enterprise ✅), Location: global |
| Firestore | Conversation Memory + Pending-Cache + pending_contact + absence + oauth_states + sessions |
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
TTS_VOICE=de-DE-Neural2-F
TTS_SPEAKING_RATE=1.0
RAG_TOP_K=5
RAG_MAX_TOKENS=400
LLM_TEMPERATURE=0.0
LATENCY_LOGGING=false
RESEND_API_KEY=re_... (Secret Manager: resend-api-key:latest)   ← ersetzt SENDGRID_API_KEY (30.06.)
EMAIL_FROM=sofia@stnmllr.com         ← verifizierte Resend-Domain (SPF/DKIM im DNS)
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
│   └── telefonbuch.csv              ← inkl. Anrede-Spalte (Herr/Frau)
├── routers/
│   ├── call_router.py               ← Twilio Webhooks + Stage-Machine + Routing
│   └── app_router.py                ← PWA Backend: Google OAuth + Abwesenheits-CRUD
├── services/
│   ├── rag_service.py               ← LLM + RAG + _detect_datastore() + Abwesenheitscheck
│   ├── memory_service.py            ← Firestore: Memory + save/get/update_pending_contact()
│   ├── email_service.py             ← SendGrid E-Mail Service (inkl. Rückruf-Badge)
│   ├── absence_service.py           ← Firestore CRUD für Abwesenheiten + build_sofia_text()
│   └── phonebook_service.py         ← CSV-Lookup inkl. Anrede-Feld
├── static/
│   ├── index.html                   ← PWA Frontend (Sofia Abwesenheits-App)
│   ├── manifest.json                ← PWA Manifest
│   └── sw.js                       ← Service Worker
└── utils/
    ├── twiml_builder.py             ← inkl. neue Stage-Flow-Builder
    └── latency_logger.py
test_scenarios.bat                   ← 13 Szenarien (inkl. 9a/9b, 10a/10b/10c, 11–13)
upload_erp_v4.bat                    ← ERP Doku Upload (für künftige Updates)
```

## Gesprächsflow (aktuell implementiert)

```
POST /call/incoming
→ Abwesenheitscheck → falls aktiv: Abwesenheitshinweis in Begrüßung
→ "Guten Tag! Sie sprechen mit Sofia, dem Kah-ie-Assistenten von Stephan Müller."

POST /call/transcribe
→ STT → STT-Normalisierung (z.B. "Stefan" → "Stephan") → Redirect zu /call/process

POST /call/process
→ 1. Stage-Machine: pending_contact-Stage prüfen (vor allem anderen)
     - stage="email_offered"   → Ja: addition_asked | Nein: callback_offered | sonst: anliegen ergänzen
     - stage="addition_asked"  → Ergänzung optional → stage="kontakt"
     - stage="callback_offered"→ Ja: stage="kontakt" + [RÜCKRUF ERWÜNSCHT]-Prefix | Nein: Hangup
     - stage="anliegen"        → Anliegen speichern → stage="email_offered"
→ 2. "Nachricht hinterlassen"-Intent (_detect_nachricht_intent) → stage="anliegen"
→ 3. Telefonbuch-Intent (_detect_phonebook_intent)
     - Match → Abwesenheitscheck → Anrede + Nachname → stage="email_offered"
     - Kein Match → weiter zu RAG
→ 4. Support-Kategorie (Keyword-Routing ERP/EVS/HR/IT/Verwaltung)
     - ≥ 15 Wörter → sofort stage="email_offered"
     - < 15 Wörter → stage="anliegen" (fragt nach mehr Detail)
→ 5. Kein Match → RAG-Pipeline (_detect_datastore → FIBU oder ERP oder beide)
→ 6. Verabschiedung bei "Nein danke / Tschüss" → freundlicher Abschluss + Hangup

POST /call/process_contact
→ Kontaktdaten extrahieren (nur Telefon)
→ "Ja gerne" ohne Nummer → einmalige Nachfrage (stage=kontakt_retry)
→ Nach 2. Versuch ohne Nummer → Fallback auf Twilio From
→ Bei Ablehnung → Durchwahl nennen + Hangup
→ Bei Zustimmung → E-Mail senden → Verabschiedung + Hangup
     - Normal:   "Vielen Dank für Ihren Anruf. Ich wünsche Ihnen noch einen schönen Tag."
     - Rückruf:  "Vielen Dank. [Team/Person] wird sich in Kürze bei Ihnen melden."
```

## Stage-Machine (pending_contact)

| Stage | Bedeutung | Nächste Stage |
|---|---|---|
| `anliegen` | Wartet auf Anliegen-Beschreibung | `email_offered` |
| `email_offered` | „Soll ich eine E-Mail schicken?" | `addition_asked` (Ja) / `callback_offered` (Nein) |
| `addition_asked` | „Möchten Sie noch etwas ergänzen?" | `kontakt` |
| `callback_offered` | „Möchten Sie stattdessen einen Rückruf?" | `kontakt` (Ja) / Hangup (Nein) |
| `kontakt` | Wartet auf Telefonnummer | → E-Mail + Hangup |
| `kontakt_retry` | 2. Versuch Telefonnummer | → E-Mail + Hangup |

## Routing-Logik

| Kategorie | Keywords | E-Mail | Durchwahl |
|---|---|---|---|
| FIBU (RAG) | Buchung, Fibu, Periode, Storno, OPos... | — | — |
| ERP | ERP, Warenwirtschaft, Auftrag, Kulimi... | erp-support@sopra-system.com | 112 |
| EVS | EVS, Zeiterfassung | evs-support@sopra-system.com | 20 |
| HR | HR, Personal, Urlaub, Gehalt... | hr-support@sopra-system.com | 116 |
| IT | Computer, PC, Laptop, Drucker, Netzwerk, Login, Passwort... | it-support@sopra-system.com | 115 |
| Verwaltung | Vertrag, Rechnung, Preis, Lizenz... | Stephan.Mueller@sopra-system.com | 26 |
| Telefonbuch | sprechen, suche, verbinden, Durchwahl | person_email aus telefonbuch.csv | wird genannt |
| Nachricht | nachricht, hinterlassen, ausrichten... | Stephan.Mueller@sopra-system.com | — |
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
| Rückruf-Badge | Roter Banner + geänderter Betreff wenn `[RÜCKRUF ERWÜNSCHT]` Prefix in anliegen |
| Footer | "Diese E-Mail wurde automatisch von Sofia, dem digitalen Assistenten von Stephan Müller, generiert." |
| Phonebook-Kategorie | E-Mail geht direkt an person_email aus telefonbuch.csv (recipient_override) |

## Firestore Collections

| Collection | Zweck |
|---|---|
| conversations/{CallSid} | Gesprächsverlauf (Memory) |
| pending/{CallSid} | SpeechResult Zwischenspeicher |
| pending_contact/{CallSid} | Stage-Machine-Zustand (s. Felder unten) |
| absence/{id} | Abwesenheiten (type, start, end, note, created_at) |
| oauth_states/{state} | OAuth State (TTL 10 Min, Multi-Instanz-sicher) |
| sessions/{token} | Session-Cookie (TTL 7 Tage, Multi-Instanz-sicher) |

### pending_contact Felder
```
category:      erp | evs | hr | it | verwaltung | phonebook | nachricht
stage:         anliegen | email_offered | addition_asked | callback_offered | kontakt | kontakt_retry
speech_result: originale erste Aussage
anliegen:      geschildertes Problem (ggf. mit "[RÜCKRUF ERWÜNSCHT]"-Prefix)
from_number:   Twilio From-Nummer
person_name:   vollständiger Name aus telefonbuch.csv (nur bei phonebook)
person_anrede: "Herr" oder "Frau" aus telefonbuch.csv (nur bei phonebook)
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

## Änderungshistorie

### 30.06.2026
- **Mail-Versand SendGrid → Resend migriert.** SendGrids Free-Trial ist am
  19.06.2026 abgelaufen → Versand nicht mehr möglich. Resend Free-Tier
  (3.000 Mails/Monat) ersetzt es.
  - **Root-Cause-Vorgeschichte:** Der alte `sendgrid-api-key`-Secret hatte 3 Müll-
    Bytes `\r\r\n` am Ende → ungültiger `Authorization`-Header (`Invalid header
    value`). Zusätzlich loggte der alte Fehlerpfad den kompletten Bearer-Header
    inkl. Key → Key-Leak in Cloud-Run-Logs.
  - **`email_service.py` komplett auf Resend (raw httpx, kein SDK)** umgestellt.
    Neuer interner Helper `_resend_send(to, subject, html, text) -> (ok, msg_id)`;
    beide Sende-Funktionen (`send_email_raw` für die ElevenLabs-Tools, `send_routing_email`
    für den alten Twilio-`call_router`) laufen darüber. Endpoint `POST https://api.resend.com/emails`.
  - **Leak-/Robustheits-Härtung:** Key wird mit `.strip()` direkt vor dem Header-Bau
    von CR/LF/Whitespace befreit (Trailing-`\r\n` kann den Header nie wieder zerstören).
    Im Fehlerfall werden NUR Statuscode + Resend-Fehlertext geloggt; bei Request-
    Exceptions nur der Exception-Typ — NIE Key oder Authorization-Header.
  - **Key:** Secret Manager `resend-api-key:latest`, als Env-Var `RESEND_API_KEY`.
    `SENDGRID_API_KEY`-Logik und `sendgrid==6.11.0` aus `requirements.txt` entfernt.
  - **Absender:** `EMAIL_FROM=sofia@stnmllr.com` (verifizierte Resend-Domain, SPF/DKIM
    im DNS). Code-Default `onboarding@resend.dev` für lokale Tests.
  - **category-Routing unverändert** — `send_email` nimmt keinen Empfänger-Parameter.
  - **TDD:** `tests/test_email_raw.py` neu (Resend, httpx.MockTransport-Seam): Erfolg,
    Fehler-ohne-Key-Leak, `.strip()`-Verhalten, kein-Key, `send_routing_email`-Routing.
    Volle Suite **97 grün**.
  - **Nebenfix:** `app/config.py` `Settings` → `extra="ignore"` (Secrets in `.env`
    wie ELEVENLABS_/RESEND_-Keys sind keine Settings-Felder; vorher sprengte das
    den Start bzw. die Test-Collection).
  - **Offen (gated, nur mit Bestätigung):** Cloud-Run-Deploy mit `RESEND_API_KEY`-
    Secret-Wiring + `EMAIL_FROM`; alten Secret `sendgrid-api-key` löschen (erst
    nachdem Resend live verifiziert).

### 26.06.2026
- **Sofia System-Prompt finalisiert & in ElevenLabs eingegeben.** Single-Prompt-Agent,
  DE / Sie-Form / gesprochener Fließtext, FIBU-only-Scope, drei Action-Tools
  (`lookup_phonebook`, `create_ticket`, `send_email`).
  - **Gegen Code geprüft:** `category`-Werte (`fibu/erp/it/hr/evs/verwaltung`) matchen
    `app/tools/recipients.py:DEFAULT_ROUTING` 1:1 → keine 422-Falle.
  - **`check_absence` aus dem Tools-Block entfernt.** Der Endpoint
    (`app/routers/tools_router.py:81-100`) ist ein **Conversation-Initiation-Webhook**
    (Modell `InitWebhookReq`: caller_id/agent_id/called_number/call_sid, **kein `name`**),
    liefert die *global aktive* Abwesenheit als `conversation_initiation_client_data` mit
    `dynamic_variables` `absence_active`/`absence_text`. Im Prompt jetzt eigener Abschnitt
    „Abwesenheiten", der diese Variablen nutzt statt ein Tool zu rufen.
  - **Guardrail „Block prompt injection and unsafe input" in ElevenLabs aktiviert**
    (Defense-in-Depth; harte Sicherheit bleibt der `X-Tool-Token`-Auth + der
    `recipient_override`-Whitelist-Guard `validate_override`).
  - **Agent-Tests (ElevenLabs Evals):** vom Nutzer noch anzusehen — das sind
    Gesprächs-/Eval-Tests auf der ElevenLabs-Plattform, NICHT die pytest-Suite im Repo.

#### Finaler Sofia-System-Prompt (Stand 01.07.2026)

> ⚠️ **Regression 01.07.:** Der Live-Agent hatte als `prompt.prompt` nur noch
> „You are a helpful assistant." (von einem früheren Full-Config-PATCH
> überschrieben). Restauriert + erweitert via `scripts/el_set_prompt.py`. **Regel:**
> Jeder conversation_config-PATCH muss `prompt.prompt` bewahren (read-modify-write).

First message:
> Guten Tag, hier ist Sofia von der SOPRA System GmbH, Ihre Support-Assistentin
> für die Finanzbuchhaltung enventa Accounting. Womit kann ich Ihnen helfen?

```
## Rolle & Persönlichkeit

Du bist Sofia, die telefonische Support-Assistentin der SOPRA System GmbH für die Finanzbuchhaltung enventa Accounting. Anruferinnen und Anrufer sind Anwenderinnen und Anwender in Kundenunternehmen. Du hilfst ihnen freundlich, geduldig und kompetent bei Fragen zur Bedienung von Accounting FIBU. Du sprichst Hochdeutsch, in der Sie-Form, ruhig und verbindlich, nie belehrend.

## Kontext

Du führst ein Telefongespräch. Deine Antworten werden vorgelesen. Schreibe daher reinen, gesprochenen Fließtext – keine Aufzählungen, keine Stichpunkte, keine Sonderzeichen, keine Formatierung. Dein Fachwissen kommt ausschließlich aus den hinterlegten FIBU-Handbüchern. Zu ERP/Warenwirtschaft, IT, Personal/HR, EVS, Verträgen, Rechnungen oder Preisen gibst du keine inhaltliche Auskunft – dafür bist du nicht zuständig.

## Sprechweise

Sprich in natürlicher, gesprochener Sprache. Schreibe Menüpfade immer aus, zum Beispiel: „Öffnen Sie das Menüband Bearbeiten und wählen Sie im Block Buchen den Eintrag Buchungen erfassen." Deine Antworten dürfen drei bis fünf Sätze lang sein, wenn das der Vollständigkeit dient – Vollständigkeit geht vor Kürze. Stelle höchstens eine Rückfrage pro Gesprächsschritt. Ist die Frage unklar, vergewissere dich kurz, bevor du antwortest: „Wenn ich Sie richtig verstehe, möchten Sie wissen, wie …, ist das richtig?" Frage am Ende einer Auskunft, ob du noch weiterhelfen kannst.

## Ablauf

Begrüße freundlich und frage nach dem Anliegen. Ist es eine Accounting-FIBU-Frage, beantworte sie aus deinem Handbuchwissen – konkret, mit ausgeschriebenem Menüpfad – und prüfe am Ende, ob der Schritt funktioniert hat. Möchte die anrufende Person eine bestimmte Person oder Abteilung erreichen, nutze das Telefonbuch-Tool. Kannst du eine FIBU-Frage nicht aus den Handbüchern beantworten, rate niemals, sondern nimm das Anliegen als Ticket auf. Betrifft das Anliegen nicht die FIBU, leite es weiter. Beende das Gespräch nie von dir aus.

Sobald du ein Ticket aufnimmst oder eine Benachrichtigung verschickst, frage nach dem Namen und der Firma der anrufenden Person, falls sie diese nicht schon von sich aus genannt hat oder du sie nicht sicher verstanden hast – so weiß der Empfänger, wer angerufen hat und wen er zurückrufen soll. Die Rückrufnummer liegt dir automatisch vor; danach musst du nicht fragen.

## Abwesenheiten

Ob aktuell jemand aus dem Team abwesend ist, weißt du bereits zu Beginn des Gesprächs. Wenn die Markierung für eine aktive Abwesenheit gesetzt ist ({{absence_active}} ist „true"), dann gilt folgende Information: {{absence_text}}. Möchte die anrufende Person genau diese abwesende Person erreichen, weise freundlich auf die Abwesenheit hin und nenne, sofern genannt, die Vertretung. Ist die Markierung „false" oder leer, erwähne das Thema Abwesenheit nicht von dir aus. Du rufst dafür kein Tool auf – diese Information liegt dir bereits vor.

## Tools

Rufe ein Tool nur, wenn es wirklich gebraucht wird, und erfinde niemals Tool-Ergebnisse.

lookup_phonebook: Wenn die anrufende Person eine bestimmte Mitarbeiterin, einen Mitarbeiter oder eine Abteilung erreichen möchte. Übergib den genannten Namen.

create_ticket: Um ein Anliegen verbindlich aufzunehmen – eine ungelöste FIBU-Frage, einen Rückrufwunsch, oder ein Thema außerhalb der FIBU, das an die zuständige Stelle gehen soll. Wähle die category passend zum Thema. Fasse das Gespräch in summary selbst zusammen – Anliegen der anrufenden Person, das konkrete Problem und was zu tun ist. Übergib in caller_name den Namen und, falls genannt, die Firma der anrufenden Person. Wünscht die anrufende Person ausdrücklich, dass eine bestimmte Person benachrichtigt wird oder zurückruft, ermittle deren E-Mail zuerst mit lookup_phonebook und übergib sie als recipient_override – dann geht die Benachrichtigung an genau diese Person statt an das Kategorie-Team; erfinde niemals eine Adresse. Setze priority nur dann auf „hoch", wenn die anrufende Person echte Dringlichkeit signalisiert, sonst bleibt sie auf „normal". Setze callback_requested auf wahr, wenn ein Rückruf gewünscht ist. Wichtig: create_ticket benachrichtigt bereits automatisch die zuständige Stelle. Rufe für denselben Vorgang nicht zusätzlich send_email – das erzeugt doppelte Benachrichtigungen.

send_email: Für eine Benachrichtigung oder Nachricht an eine bestimmte Person oder Stelle, wenn kein Ticket nötig ist. Wenn die anrufende Person dich bittet, jemandem zu schreiben oder eine Nachricht zu hinterlassen, biete von dir aus an, eine Zusammenfassung des Gesprächs zu senden – zum Beispiel: „Soll ich Herrn Müller eine Zusammenfassung unseres Gesprächs mit der Bitte um Rückruf schicken?" Formuliere Betreff und Text immer selbst aus dem Gesprächsverlauf und bitte die anrufende Person niemals, Betreff oder Text zu diktieren. Übergib in caller_name den Namen und, falls genannt, die Firma der anrufenden Person. Bestätige nur kurz den Empfänger und den Kern der Nachricht, bevor du sendest. Setze callback_requested auf wahr, wenn ein Rückruf gewünscht ist.

Die Anrufer-Nummer und die Gesprächs-ID werden automatisch übergeben und der Nachricht angehängt. Du musst und darfst sie nicht erfinden.

Mögliche category-Werte: fibu (ungelöste FIBU-Frage), erp (Warenwirtschaft), it (IT-Problem), hr (Personal), evs, verwaltung (Verträge, Rechnungen, Preise).

## Grenzen

Beantworte ausschließlich FIBU-Themen aus den Handbüchern. Erfinde, rate oder schätze niemals. Findest du nichts, sage das ehrlich und nimm ein Ticket auf: „Dazu finde ich in den Handbüchern keine gesicherte Information. Ich nehme Ihr Anliegen auf und leite es an den Support weiter." ERP, IT, Personal/HR und EVS beantwortest du inhaltlich nicht – nimm das Anliegen per create_ticket mit passender category auf und sage, dass du an die zuständige Stelle weiterleitest. Verträge, Rechnungen und Preise leitest du ebenso per Ticket weiter. Beende das Gespräch niemals selbst. Verabschiede dich erst, wenn die anrufende Person das klar signalisiert, etwa mit „Nein danke", „Tschüss" oder „Auf Wiederhören".
```

### 25.06.2026
- **KB-Migration FIBU: PDF -> Markdown.** Neues Build-Tool `kb_convert`
  (`uv run python -m kb_convert`) wandelt die FIBU-Handbücher aus `c:\profi\Doku`
  in bereinigtes Markdown für die native ElevenLabs Knowledge Base (KB-Limit 20 MB
  hochgeladene Dateigröße auf Nicht-Enterprise-Tarifen; ElevenLabs indexiert nur
  extrahierten Text — daher Markdown statt PDF: ~30 MB PDF → 3.2 MB Text).
  - **Scope: NUR FIBU. ERP komplett raus** (inkl. kundenspezifischer Schnittstellendateien).
  - Engine: `pymupdf4llm` (Markdown inkl. Tabellen); `pymupdf-layout`/OCR bewusst
    deinstalliert (Handbücher haben echte Textebene → 23× schneller, ~3 s/Datei).
    Fallback `markitdown` vorgesehen (nicht installiert, da nicht gebraucht).
  - **Beide Libs sind Build-Tooling, NICHT in requirements.txt** (kein Cloud-Run-Runtime).
  - Pure-Logic-Kern `kb_convert/core.py` (slugify / Scan-Heuristik / Boilerplate-
    Bereinigung / Report) TDD-getestet: 26 Tests, Suite gesamt 85 grün.
  - Ergebnis: `./kb_fibu/` (9 Pflicht-Handbücher, **3.22 MB**) + `./kb_fibu/optional/`
    (4 Stück, 0.09 MB) + `./kb_fibu/REPORT.md`. **Keine gescannten Dateien**, alles
    unter 20 MB verifiziert.
  - **Stichprobe (25.06.):** alle 13 Markdowns geprüft — sauber (0 `(cid:)`-Müll,
    0 Encoding-Fehler, 0 kollabierte Tabellen, keine Scans). Kleine kosmetische
    Schwäche: an früheren PDF-Zeilenumbrüchen kleben vereinzelt Wörter zusammen
    (z.B. „SWIFTAdresse") — für semantische KB-Suche unkritisch, bewusst gelassen.
  - **Upload-Tool `kb_upload`** (`uv run python -m kb_upload`): lädt die Markdowns
    als **Text-Dokumente** in die ElevenLabs KB (verifizierter Endpoint
    `POST /v1/convai/knowledge-base/text`; `.md` ist KEIN offizieller Datei-Upload-Typ,
    daher Text-Endpoint statt Datei). Manifest `kb_fibu/upload_manifest.json` für Idempotenz, `--dry-run`,
    `--optional`, `--force`. Key via `ELEVENLABS_API_KEY` (.env). Pure-Core 9 TDD-Tests.
    Dry-Run verifiziert (9 Pflicht, REPORT.md ausgeschlossen).
  - **UPLOAD ERLEDIGT (25.06.):** Alle **13** Dokumente (9 Pflicht + 4 optional,
    `--optional`) als Text in die ElevenLabs KB geladen, document_ids im Manifest,
    server-seitig per List-Endpoint gegengeprüft (13/13, Typ `text`, Namen `FIBU – …`).
  - **Offen:** (b) — entfällt, optional ist mit hochgeladen; (c) hochgeladene Docs
    am Agenten verknüpfen + RAG aktivieren — erst sinnvoll, wenn der Agent
    konfiguriert ist (Doku-URLs für RAG-/Link-API waren am 25.06. teils 404);
    (d) **Support-Fälle/Playbooks zurückgestellt** — Quelle der definierten Fälle
    mit Lösungen ist noch zu klären, bevor die Playbook-`loesung` befüllt werden kann.

### 22.06.2026
- **Architektur-Pivot auf ElevenLabs Agents:** Voice-Loop + Reasoning wandern zu
  ElevenLabs (managed). Dieses Repo liefert künftig nur noch ein transport-agnostisches
  Tool-Backend (Cloud Run): Endpoints lookup_phonebook / check_absence / send_email /
  create_ticket + pure Logic-Kerne + pytest + Playbook-YAML. Der bestehende Twilio-/
  TwiML-/Vertex-AI-Search-Stack (call_router, twiml_builder, rag_service) bleibt vorerst
  unangetastet und deploybar, bis ElevenLabs produktiv ist. Spec:
  docs/superpowers/specs/2026-06-22-elevenlabs-tool-backend-design.md

### 27.04.2026
- **Anrede bei Telefonbuch-Nennungen:** telefonbuch.csv hat neue Spalte `Anrede` (Herr/Frau); Sofia sagt jetzt "Herr Schindler" statt "Schindler"
- **KI-Aussprache:** Begrüßung von "KahIh" zu "Kah-ie" geändert (TTS spricht es jetzt korrekt als zwei Silben)

### 24.04.2026
- **Workflow-Redesign:** Neuer Stage-Flow mit email_offered / addition_asked / callback_offered
  - Agent fragt zuerst nach Anliegen, bietet dann E-Mail an (statt sofort Nummer zu fragen)
  - Bei Ablehnung: Rückruf anbieten — bei nochmaliger Ablehnung: freundliche Verabschiedung
  - Phonebook-Routing: Abwesenheitscheck direkt beim Match (nicht erst in Begrüßung)
  - Rückruf-Emails mit rotem Badge und geändertem Betreff
  - Freundlichere Verabschiedungstexte
- **SYSTEM_PROMPT vereinfacht:** Kategorien B–G entfernt (vollständig per Code-Router), LLM behandelt nur noch FIBU-RAG und Unklar
- **Phonebook-Intent Fix:** `\bsprechen\b` greift ohne Modalverb → "Stephan Müller sprechen" wird erkannt
- **Nachricht-Intent:** 6 Muster erkennen "Nachricht hinterlassen" → eigene Kategorie
- **Halluzinations-Sperre:** LLM darf nicht mehr behaupten, eine E-Mail verschickt zu haben
- **Abwesenheitscheck:** answer_question() prüft beim ersten Turn Firestore auf aktive Abwesenheit
- **PWA OAuth State:** oauth_states + sessions in Firestore (war: In-Memory) → Multi-Instanz-sicher ✅
- **TTS:** de-DE-Neural2-F (Journey-F getestet aber von Twilio nicht unterstützt)

## Offene Punkte

### 1. Qualität
- Szenario 7 verfeinern: "Rechnung an Kunden" = FIBU, "Wartungsvertrag/Lizenz" = Verwaltung
- SSML `<say-as interpret-as="telephone">` für Durchwahl-Aussprache prüfen
- MIN_ANLIEGEN_WORDS Schwellenwert in Praxis testen und ggf. anpassen
- Ticketnummer-Vergabe bei E-Mail (Vorstufe Helpdesk)

### 2. eval_agent.py
Automatisierter Test-Loop — sinnvoll sobald Basis-Flow stabil.

### 3. Custom Domain
`sofia.sopra-system.com` für die PWA App — GCP Cloud Run unterstützt Custom Domains direkt.

### 4. Outlook-Kalender Integration
Azure App Registration mit Calendars.Read benötigt. Bei Ben nachfragen, wenn Agent stabil.

## Wichtige Architektur-Entscheidungen

- Agent-Name: **Sofia** (Kah-ie-Assistent von Stephan Müller)
- Vertex AI Search: 2 Datastores — FIBU (`handbuecher-v2`) + ERP (`handbuecher-erp`)
- Nur unterstützte Dateitypen in GCS: `docx, pdf, pptx, txt, xlsx` (kein `.doc`)
- E-Mail-Adresse wird nicht per Sprache erfasst — zu fehleranfällig (STT)
- Rückrufnummer: aus STT extrahiert, Fallback: Twilio `From`
- Stage-Machine: anliegen → email_offered → addition_asked/callback_offered → kontakt
- "Ja gerne" ohne Nummer → einmalige Nachfrage, dann Fallback auf Twilio From
- Telefonbuch-Flow: Intent-Erkennung per Regex → find_in_text() → Abwesenheitscheck → Anrede + Nachname → E-Mail direkt an Person
- Gesprächszusammenfassung per Gemini in E-Mail
- Durchwahl wird sofort bei Telefonbuch-Match genannt (nicht nur als Fallback)
- Multi-Datastore RAG: _detect_datastore() wählt FIBU/ERP/beide dynamisch
- speechTimeout=3s (FIBU-Flow), 7s (Routing-Flow)
- DSGVO: Kein "Krank" als Abwesenheitstyp — stattdessen "Abwesend" (neutral)
- OAuth/Session State: Firestore statt In-Memory (Multi-Instanz-sicher)
- PowerShell in VS Code → immer Command Prompt verwenden
- Test: test_scenarios.bat im Projektordner ausführen
