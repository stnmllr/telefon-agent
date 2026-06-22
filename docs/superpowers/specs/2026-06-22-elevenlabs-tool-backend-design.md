# Sofia — ElevenLabs Tool-Backend (Phase 1) — Design-Spec

**Datum:** 2026-06-22
**Branch (geplant):** `refactor/elevenlabs-phase-1` (von `migrate/gemini-2.5-flash`)
**Status:** Design freigegeben (mit Review-Korrekturen), Implementierungsplan folgt via writing-plans.

---

## 1. Kontext & Ziel

Pivot von der bestehenden Twilio-Webhook-/TwiML-Stage-Machine auf **ElevenLabs Agents**
(managed Voice-Loop + Reasoning + Knowledge Base). Auf unserer Seite bleibt nur ein schlankes,
**transport-agnostisches** Tool-Backend auf Cloud Run, das ElevenLabs als „Server Tools" aufruft.

**Codebarer Phase-1-Umfang in DIESEM Repo:**
- 4 HTTP-Endpoints (`lookup_phonebook`, `check_absence`, `send_email`, `create_ticket`)
- Pure-Logic-Kerne unter `app/tools/` (kein I/O außer CSV-Read) — direkt unit-testbar
- pytest-Suite (`uv run python -m pytest`)
- Playbook-YAML-Schema + 1 befülltes Beispiel für die KB

**Nicht in diesem Repo (ElevenLabs-Dashboard / Business / Recht):** System-Prompt, Knowledge Base,
Eval-Simulation, System-Tools `end_call`/`transfer_to_number`, Nummer-Import, LLM-Tier-Wahl,
Concurrency-Tier, Call-Recording/DSGVO, AV-Konstellation.

**De-Risking:** Tools sind reine HTTP-Endpoints + pure Funktionen. Sie funktionieren hinter
ElevenLabs genauso wie hinter Twilio ConversationRelay, falls die Plattformentscheidung später
korrigiert wird. pytest-Suite und Eval-Set sind plattformunabhängig.

**Vorbedingung (verifiziert erledigt):** Repo-Migration `C:\Users\stephan\telefon-agent` →
`D:\programme\telefon-agent` ist abgeschlossen, alter Pfad existiert nicht mehr. Wird **nicht**
erneut ausgeführt.

---

## 2. Architektur & Modul-Layout

Neuer, isolierter Tool-Layer **neben** dem alten Stack. Der alte Twilio-/TwiML-/RAG-Code
(`call_router.py`, `twiml_builder.py`, Vertex AI Search) bleibt in Phase 1 **unangetastet** und
deploybar, bis ElevenLabs produktiv ist.

```
app/
├── routers/
│   ├── tools_router.py      ← NEU: POST /tools/{lookup_phonebook,check_absence,send_email,create_ticket}
│   └── app_router.py        ← bleibt; ERWEITERT um GET/PUT /app/api/routing (Empfänger-Config)
├── tools/                   ← NEU: transport-agnostische Pure-Logic-Kerne (kein Firestore/HTTP)
│   ├── phonetik.py          ← koelner_phonetik(s) -> str   (stdlib, ~40 Zeilen)
│   ├── phonebook.py         ← fuzzy_lookup(name) -> list[Match]   (nur CSV-Read)
│   ├── absence.py           ← build_sofia_text(absence) -> str   (Windows/Locale-sicher)
│   ├── recipients.py        ← DEFAULT_ROUTING + resolve_recipient(category, map) + validate_override(email)  (pure)
│   └── tickets.py           ← format_ticket_id(year, seq) -> str   (pure)
├── services/                ← bleibt; email_service / absence_service werden wiederverwendet
│   └── routing_config.py    ← NEU: lädt Firestore config/routing, merged über DEFAULT_ROUTING (I/O + Cache)
├── static/index.html        ← bleibt; ERWEITERT um Settings-Sektion (Empfänger editieren)
└── playbooks/               ← NEU
    ├── README.md            ← Schema-Doku (Abschnitt 7)
    └── fibu-periode-gesperrt.yaml   ← 1 Beispiel (loesung-Schritte als Platzhalter)
```

**Hexagonale Trennung:**
- `app/tools/*` = reine Funktionen, kein Seiteneffekt außer CSV-Read → direkt unit-testbar, transport-agnostisch.
- `tools_router.py` = dünne HTTP-Schicht je Endpoint: **Auth → Validierung → Pure-Core → I/O (Firestore/SendGrid) → Audit-Log → JSON**.

---

## 3. Querschnitt: Auth, Audit, Idempotenz

### 3.1 Auth
Jeder Endpoint prüft Header `X-Tool-Token` gegen Env `TOOL_AUTH_TOKEN`. Fehlend/falsch → **401**.
Token wird in der ElevenLabs-Tool-Config hinterlegt. Konstanter-Zeit-Vergleich (`hmac.compare_digest`).

### 3.2 Audit-Log
Jeder **schreibende** Call (`send_email`, `create_ticket`) schreibt nach Firestore
`tool_audit/{auto-id}`:
```
{ tool, ts, call_id, caller_number, category, recipient, ticket_id, email_sent, error }
```

### 3.3 Idempotenz (Retry-Schutz, atomar)
ElevenLabs/Netz können Tool-Calls wiederholen (besonders bei Timeout → ggf. **parallel**) →
ohne Schutz doppelte E-Mails/Tickets. Ein Check-then-Act (Query → sonst schreiben) hat eine
Race-Condition: zwei parallele Retries lesen beide „kein Eintrag" und führen beide aus.

**Atomare Lösung (create-if-not-exists):** Das Audit-Doc bekommt eine **deterministische ID
`{call_id}:{tool}`** (`:` ist als Firestore-Doc-ID erlaubt; `call_sid` ist safe). Ablauf:
1. Reservierungs-Doc `tool_audit/{call_id}:{tool}` per `create()` anlegen (schlägt **hart** fehl,
   wenn es schon existiert — Firestore-Precondition, kein Composite-Index nötig), Status `in_progress`.
2. Bei Precondition-Fehler → Duplikat: vorhandenes Doc lesen und dessen Ergebnis zurückgeben
   (bzw. „wird bereits verarbeitet"), **nicht** erneut ausführen.
3. Sonst: Aktion ausführen, Doc auf Status `done` + Ergebnis (`ticket_id`, `email_sent`, `error`) updaten.

Fehlt `call_id` (z.B. Direkttest), wird mit zufälliger Auto-ID ohne Dedup ausgeführt (best effort).

---

## 4. Endpoint-Verträge

Alle: `POST`, JSON rein / JSON raus, Header `X-Tool-Token`.

### 4.1 `POST /tools/lookup_phonebook`
**Request:** `{ "name": "string" }`
**Response (Treffer):**
```json
{ "found": true,
  "matches": [
    { "anrede": "Herr", "vorname": "Stefan", "nachname": "Bär",
      "email": "stefan.baer@sopra-system.com", "durchwahl": "75", "beschreibung": "ERP Support" }
  ] }
```
**Response (kein Treffer):** `{ "found": false }`

**Pure-Core `phonebook.fuzzy_lookup(name) -> list[Match]`:**
- **Keine** Vorab-Normalisierung „Stefan→Stephan" (zerstört Identität bei 2 Stefans + Stephan).
- Eingabe und CSV-Namens-Tokens werden **NFC-normalisiert + casefold** (Umlaute/ß stabil).
- Matching via **Kölner Phonetik** (`phonetik.koelner_phonetik`): Query-Tokens (>2 Zeichen) werden
  phonetisch kodiert und gegen die Kölner-Codes der Vor-/Nachnamen jedes CSV-Eintrags verglichen.
- **Ranking nach Token-Treffer-Anzahl** (verhindert Über-Matching bei vollem Namen): Für jeden
  CSV-Eintrag wird gezählt, wie viele **Query**-Tokens phonetisch matchen.
  - Matcht mindestens ein Eintrag **alle** Query-Tokens → nur die Maximal-Treffer (alle Tokens)
    zurückgeben. Bsp.: „Stefan Bär" → **nur Bär** (Bär matcht beide Tokens; Peters/Müller nur den
    `stefan`-Token `8236`).
  - Matcht **kein** Eintrag alle Tokens → auf Einzel-Token-Treffer zur Disambiguierung zurückfallen.
    Bsp.: reine Vornamen-Anfrage „Stefan" → **Bär, Peters und Müller** (`8236` kollidiert) → Agent fragt nach.
- `Name`-Spalte = „Nachname, Vorname" → in `nachname`/`vorname` aufgesplittet.
- Team-/Zentrale-Zeilen ohne E-Mail werden mit zurückgegeben (`email: ""`), gelten aber **nie**
  als override-fähig (s. 4.3 Guard).

### 4.2 `POST /tools/check_absence` (ElevenLabs Conversation-Initiation-Webhook)
**Request (von ElevenLabs):** `{ "caller_id": "...", "agent_id": "...", "called_number": "...", "call_sid": "..." }`
**Response (ElevenLabs-Envelope):**
```json
{ "type": "conversation_initiation_client_data",
  "dynamic_variables": { "absence_active": "true", "absence_text": "Herr Müller ist im Urlaub und ab 15. Juli wieder erreichbar." }
}
```
Bei keiner aktiven Abwesenheit: `dynamic_variables.absence_active = "false"`, `absence_text = ""`.
Optionales `conversation_config_override` (z.B. `agent.first_message`) wird in Phase 1 leer gelassen;
die Begrüßung referenziert `{{absence_text}}` im Dashboard-Prompt (Dashboard-Config, out of scope).

- Reuse `absence_service.get_active_absence()`.
- Pure-Core `absence.build_sofia_text(absence)` — **Fix gegenüber Alt-Code:** festes deutsches
  Monats-Array statt `strftime("%-d. %B %Y")` (eliminiert Windows-`%-d`-Crash **und**
  Locale-Abhängigkeit der Monatsnamen). 4 Typen: urlaub/meeting/abwesend/dienstreise.
- **Graceful Degradation:** Der Endpoint sitzt im Call-Setup-Pfad **vor** der Begrüßung. Bei
  Firestore-Hänger/Fehler (try/except) liefert er `absence_active="false"` statt den Anrufaufbau
  zu blockieren. Der Anruf kommt immer zustande; im Fehlerfall begrüßt Sofia ohne Abwesenheitshinweis.
- Final-Wiring (Webhook in ElevenLabs verdrahten) = Dashboard-Config, out of scope.

### 4.3 `POST /tools/send_email`
**Request:**
```json
{ "category": "erp|evs|hr|it|verwaltung|nachricht|fibu|phonebook",
  "subject": "string", "body": "string",
  "caller_number": "string", "callback_requested": false,
  "recipient_override": "string|null",
  "call_id": "string|null", "ticket_ref": "string|null" }
```
**Response:** `{ "sent": true, "recipient": "…@…", "message_id": "…", "ticket_ref": null }`

- `recipients.resolve_recipient(category, routing_map)` (pure, nimmt die gemergte Map als Argument).
  Die Map = Code-Defaults überlagert durch Firestore `config/routing` (s. Abschnitt 5). `fibu` ist
  enthalten (Eskalation einer nicht lösbaren FIBU-Frage; Default = `verwaltung`-Adresse).
- **Recipient-Guard:** `recipient_override` wird nur akzeptiert, wenn die Adresse **exakt** einer
  **nicht-leeren** E-Mail aus `telefonbuch.csv` entspricht (`recipients.validate_override`).
  Sonst **422**. Verhindert LLM-Halluzination von Adressen.
- `ticket_ref` (optional) wird in Betreff/Body aufgenommen; bei Direktaufruf `null`.
- Reuse `email_service` (inkl. `caller_name`-Param aus dem Namens-Feature-Commit). Audit + Idempotenz.

### 4.4 `POST /tools/create_ticket`
**Request:**
```json
{ "category": "string", "summary": "string", "caller_number": "string",
  "callback_requested": false, "priority": "normal|hoch", "call_id": "string|null" }
```
**Response:** `{ "created": true, "ticket_id": "SOF-2026-000123", "email_sent": true }`

- `tickets.format_ticket_id(year, seq) -> "SOF-{YYYY}-{seq:06d}"` (pure, getestet).
- Sequenz via **Firestore-Transaktion** auf `counters/tickets` (concurrency-sicher).
- Ablauf: (1) Idempotenz-Check; (2) Counter+Record `tickets/{id}` schreiben →
  **Ticket gilt ab hier als erstellt**; (3) intern `send_email` mit `ticket_ref` aufrufen.
- **Fehlersemantik:** Schlägt SendGrid fehl, bleibt das Ticket gültig (`created: true`),
  `email_sent: false`, Partial-Fail landet im Audit. Eine Ticketnummer wird nie „verbrannt"
  ohne Record.

---

## 5. Routing-Map (Empfänger-Auflösung, konfigurierbar)

Code-Defaults (zentral in `recipients.py`, entspricht heutiger `email_service.CATEGORY_EMAILS`):

| category   | Default-Empfänger                  | Anmerkung |
|------------|------------------------------------|-----------|
| erp        | erp-support@sopra-system.com       | |
| evs        | evs-support@sopra-system.com       | |
| hr         | hr-support@sopra-system.com        | |
| it         | it-support@sopra-system.com        | |
| verwaltung | Stephan.Mueller@sopra-system.com   | |
| nachricht  | Stephan.Mueller@sopra-system.com   | |
| **fibu**   | Stephan.Mueller@sopra-system.com   | **NEU** — Eskalation nicht lösbarer FIBU-Fragen (Normalfall: KB-Auskunft) |
| phonebook  | — | nur via validiertem `recipient_override` |

### 5.1 Konfigurierbarkeit (Firestore + PWA)
Die Empfänger sind **über die PWA editierbar**, ohne Deploy:
- **Firestore-Doc `config/routing`** hält `{ category: email }`-Overrides. Beim Auflösen werden
  Code-Defaults geladen und mit den Firestore-Overrides **gemergt** (Override gewinnt). Eine fehlende
  oder leere `config/routing` → reine Defaults. Map wird im Endpoint geladen (kurzlebiger In-Prozess-Cache).
- **PWA-Erweiterung** der bestehenden Abwesenheits-App (`app_router.py` + `static/index.html`):
  - `GET /app/api/routing` → aktuelle effektive Map (Defaults + Overrides).
  - `PUT /app/api/routing` → speichert Overrides nach `config/routing`.
  - Beide hinter der bestehenden Google-OAuth-Session (nur `ALLOWED_EMAIL`).
  - Neue Settings-Sektion im PWA-Frontend: Liste aller Kategorien mit editierbarem Empfänger-Feld.
- **Validierung beim Speichern:** Eingegebene Empfänger müssen Pflicht-Format E-Mail erfüllen
  (einfache Server-seitige Prüfung). FIBU ist nur eine Zeile dieser Liste — kein Sonderfall im Code.

---

## 6. Tests (TDD — Pure-Cores zuerst)

`uv run python -m pytest`. Firestore/SendGrid via `pytest-mock`, keine echten Calls.

**Reihenfolge (jeweils Test zuerst):**
1. `phonetik.koelner_phonetik` — stefan/stephan/steffen → gleicher Code; bär/baer; müller/mueller; schindler distinkt.
2. `phonebook.fuzzy_lookup` —
   - reine Vornamen-Anfrage „Stefan" liefert **Bär+Peters+Müller** (Vornamen-Kollisions-Regression);
   - voller Name „Stefan Bär" liefert **nur Bär** (Token-Ranking-Regression);
   - exakter Nachname; kein Treffer; NFC/Umlaut-Test (Bär, Müller, Zöscher); Team-Zeilen ohne E-Mail.
3. `absence.build_sofia_text` — alle 4 Typen; Windows-Datumsformat (kein `%-d`-Crash); Meeting-Uhrzeit.
4. `recipients` — `resolve_recipient` je Kategorie inkl. `fibu`; Firestore-Override gewinnt über Default;
   `validate_override` gültig / halluziniert / leere CSV-Mail.
5. `tickets.format_ticket_id` — Nullpadding, Jahr.
6. **Endpoint-Tests** (gemockt): Auth-401; Recipient-Guard-422; **atomare Idempotenz** (2. Call mit
   gleichem `{call_id}:{tool}` = `create()`-Precondition-Fehler → kein 2. Versand, Ergebnis aus
   vorhandenem Doc); create_ticket Partial-Fail (`created:true`, `email_sent:false`);
   check_absence-Envelope-Form **+ Graceful Degradation** (Firestore-Fehler → `absence_active="false"`);
   PWA `GET/PUT /app/api/routing` (Auth + Override-Persistenz).

**Zielabdeckung:** ~95 % auf den Tool-Kernen. Jeder genannte Alt-Bug → Regressionstest.

---

## 7. Playbook-YAML-Schema

Strukturierte YAML-Dokumente für die ElevenLabs Knowledge Base. Schema (Hülle von CC,
**`loesung`-Fachinhalt vom Nutzer** als markierter Platzhalter `<<aus Handbuch befüllen>>`):

```yaml
- id: fibu-periode-gesperrt
  title: "Buchung nicht möglich – Periode gesperrt"
  area: FIBU                       # FIBU | ERP | EVS | HR | IT | Verwaltung
  trigger: ["kann nicht buchen", "Periode ist gesperrt", "Buchung wird abgelehnt"]
  diagnose:
    - "Welcher Buchungsmonat bzw. welche Periode betrifft es?"
    - "Erscheint eine konkrete Fehlermeldung? Wenn ja, welche genau?"
  loesung:
    - "<<aus Handbuch/Fachwissen befüllen>>"
  verifikation:
    - "Bitten Sie den Anrufer, die Buchung erneut zu versuchen."
  eskalation:
    - { bedingung: "Anrufer hat keine Berechtigung zum Entsperren", aktion: transfer }
    - { bedingung: "Fehlermeldung deutet auf Datenbank-/Integritätsproblem", aktion: ticket_hoch }
  handbuch_refs: ["ProFI FIBU – Periodenverwaltung"]
```

`pyyaml` validiert das Schema beim Laden (Smoke-Test in der Suite). **Kein** `lookup_playbook`-Endpoint
in v1 — native KB-Grounding zuerst; explizites Tool nur, falls Grounding zu lose (Phase 2).

---

## 8. Setup-Schritte (gehören in den Implementierungsplan)

1. Namens-Feature (4 uncommittete Dateien) als sauberen Commit auf `migrate/gemini-2.5-flash` sichern.
2. `refactor/elevenlabs-phase-1` von `migrate/gemini-2.5-flash` abzweigen (erbt Gemini 2.5 + `caller_name`).
3. `CLAUDE.md` neu anlegen: `uv run python -m pytest` als Testaufruf (EPDR/WatchGuard-Workaround
   dokumentieren), „in VS Code immer Command Prompt, nie PowerShell".
4. `requirements.txt` += `pytest`, `pytest-mock`, `pytest-cov`, `pyyaml` (`httpx` bereits vorhanden).
5. `PROJEKTSTAND.md`: aktuelles Datum + Architektur-Pivot (ElevenLabs) vermerken.

---

## 9. Bewusst NICHT in Phase 1 (YAGNI / spätere Phasen)

- Abriss von `call_router.py` / `twiml_builder.py` / Vertex AI Search — erst wenn ElevenLabs produktiv.
- `lookup_playbook`-Tool — erst falls KB-Grounding zu lose.
- Echte Helpdesk-/Ticket-Anbindung — v1 ist E-Mail-Surrogat + Firestore-Record.
- ElevenLabs-Dashboard-Config (System-Prompt, KB-Upload, Eval-Simulation, Nummer-Import) — kein Code.
- L3 Audio-Goldstandard — Phase 2.

---

## 9a. „Code fertig" ≠ „Sicherheitsverhalten validiert"

Die Eval-Szenarien **#9 (Anti-Halluzination: keine Preisaussage)** und **#14 (Eskalation rechtliche
Frage → harter Handoff)** hängen am **Dashboard-System-Prompt** und an `transfer_to_number` — beides
ElevenLabs-Config, kein Repo-Code. Der harte Code-seitige Guard (Tool wird wirklich ausgeführt →
keine erfundene E-Mail/Ticket; Recipient-Guard) ist Teil dieses Spec. Das **Antwort-/Eskalations-
Verhalten** wird aber erst in der **L2-Eval gegen den konfigurierten Agenten** validiert. Abschluss
des Phase-1-Codes bedeutet daher nicht, dass das Sicherheitsverhalten bereits abgenommen ist.

## 10. Offene Klärungen (Business/Dashboard — blockieren den Code nicht)

Aus Abschnitt 8 des Kickoff-Dokuments, bewusst **außerhalb** dieses Code-Spec, vor Produktivgang
zu entscheiden: LLM-Tier (Gemini Pro / Claude vs. Flash), Concurrency-Tier, Call-Recording/DSGVO,
Nummer-Import, AV-Konstellation (Rechtsthema). Werden separat geführt.

---

## Quellen (ElevenLabs Webhook-Vertrag)
- ElevenLabs — Twilio personalization: https://elevenlabs.io/docs/agents-platform/customization/personalization/twilio-personalization
- ElevenLabs — Personalization (conversation initiation webhook): https://elevenlabs.io/docs/agents-platform/customization/personalization
