KI-Telefon-Agent — Projektstand 25.03.2026
Infrastruktur
Komponente	Wert
GCP Projekt	boxwood-mantra-489408-c0
Cloud Run	telefon-agent / europe-west3
URL	https://telefon-agent-1051648887841.europe-west3.run.app
Bucket	gs://boxwood-mantra-489408-c0-handbuecher/
Vertex AI Search	handbuecher-engine (Enterprise Edition ✅), Datastore: handbuecher-v2, Location: global
Firestore	Conversation Memory aktiv
Twilio	+49 89 41432469, Webhook auf /call/incoming
GitHub	stnmllr/telefon-agent, CI/CD via GitHub Actions (Push main → auto-deploy)
Service Account	1051648887841-compute@developer.gserviceaccount.com
Aktueller Status: ✅ AGENT FUNKTIONIERT
Enterprise Edition aktiviert — Agent gibt konkrete Schritt-für-Schritt-Antworten
aus dem Handbuch. Erster erfolgreicher echter Anruf auf +49 89 41432469.
Beispiel-Test:
```
Frage:  "Wie erfasse ich eine Buchung?"
Antwort: "Die Dialoge zum Erfassen von Buchungen erreichen Sie über den Block
          'Buchen' im Menüband 'Bearbeiten'. Konnten Sie das umsetzen?"
```
Aktuelle Konfiguration (Cloud Run Env-Vars)
```
ENVIRONMENT=production
GCP_PROJECT_ID=boxwood-mantra-489408-c0
GCP_LOCATION=us-central1              ← Gemini-Region
GEMINI_MODEL=gemini-2.0-flash         ← ohne -001 Suffix
VERTEX_SEARCH_DATASTORE=handbuecher-v2
STT_LANGUAGE=de-DE
STT_MODEL=chirp
TTS_VOICE=de-DE-Journey-F             ← aktiviert, Qualität besser aber noch optimierbar
TTS_SPEAKING_RATE=1.0
RAG_TOP_K=3
RAG_MAX_TOKENS=150
LLM_TEMPERATURE=0.0
```
Entwicklungsumgebung (eingerichtet 25.03.2026)
Tool	Status
VS Code	✅ installiert, Projekt geöffnet
Claude Code	✅ als VS Code Extension aktiv
Node.js v24	✅ installiert
Git 2.53	✅ installiert
PowerShell ExecutionPolicy	✅ RemoteSigned gesetzt
gcloud CLI	❌ noch nicht installiert
Workflow:
Code ändern: Claude Code Chat-Panel in VS Code (rechts)
Deploy: `git push origin main` → GitHub Actions → Cloud Run (~2 Min)
Direktes Deploy ohne GitHub: gcloud CLI nötig (noch nicht eingerichtet)
Terminal in VS Code: Command Prompt verwenden, nicht PowerShell
Kosten (monatlich, Schätzung)
Komponente	Kosten
Vertex AI Search Enterprise	~$2–5
Gemini 2.0 Flash	~$0.50
Cloud Run	~$0
Firestore	~$0
Twilio Nummer + Anrufe	~$1.50
Gesamt	~$5–10/Monat
Budget-Alert: €10/Monat eingerichtet ✅
GCP Trial: Upgrade auf bezahltes Konto empfohlen (Trial läuft ab, $300 Guthaben bleibt)
Alle bisherigen Fixes
Einrückungsfehler call_router.py — behoben
Placeholder `my-gcp-project` in config.py → echte Projekt-ID als Default
`extractiveContentSpec` — wieder aktiv (Enterprise Edition)
Modellname `gemini-2.0-flash-001` → `gemini-2.0-flash`
IAM — Service Account hat `roles/discoveryengine.viewer`
Doppelter LLM-Block in rag_service.py entfernt
Neue Settings in config.py: `vertex_search_location=global`, `vertex_search_engine_id=handbuecher-engine`
NÄCHSTE SESSION — Offene Punkte (Reihenfolge)
1. TTS-Stimme weiter optimieren
Journey-F ist aktiv und besser als Neural2-F, aber noch nicht optimal. Alternativen testen:
`de-DE-Chirp3-HD-Aoede` (Google Chirp HD)
Ggf. ElevenLabs als externe TTS-Lösung evaluieren
Die aktuelle Stimme klingt unnatürlich. Testen:
```cmd

### 2. gcloud CLI auf Windows installieren
Für direktes Deploy ohne GitHub Actions:
- Download: https://cloud.google.com/sdk/docs/install
```cmd
gcloud auth login
gcloud config set project boxwood-mantra-489408-c0
gcloud run deploy telefon-agent --source . --region europe-west3
```
3. GCP Trial upgraden
GCP Console → Trial-Banner → Upgrade (Restguthaben $300 bleibt erhalten)
4. E-Mail Fallback
Wenn Agent nicht antworten kann → E-Mail an Support (Gmail oder SendGrid)
5. Error Handling & Monitoring
Cloud Logging Alerts, Health Checks
6. Intent-Classifier
FIBU / OPos / Kore / Anbu / Sonstiges
7. Multi-Agent Modell
Separater Agent pro Bereich
Wichtige Architektur-Entscheidungen
Vertex AI Search läuft immer unter `locations/global` — nicht unter `gcp_location`
Gemini läuft unter `us-central1` — `gemini-2.0-flash` ist dort verfügbar
Enterprise Edition → Extractive Answers → vollständige Textpassagen als Kontext
RAG-Pfad: `_build_search_query` → `_search_datastore` → `ChatVertexAI`
PowerShell in VS Code → immer Command Prompt für curl-Befehle verwenden
---
Routing-Logik & E-Mail Szenarien (geplant)
Übersicht: Anruf-Routing
Wenn ein Anrufer am Anfang signalisiert, dass er nicht syska ProFI Support möchte,
oder wenn der Agent eine Anfrage nicht beantworten kann, greift folgende Routing-Logik:
```
Anruf eingehend
│
├─ Kunde will syska ProFI Support → normale RAG-Pipeline (aktuell aktiv)
│
└─ Kunde will etwas anderes / Agent kann nicht helfen
   │
   ├─ EVS          → Hinweis: "Bitte wenden Sie sich an den EVS Support"
   ├─ HR           → Hinweis: "Bitte wenden Sie sich an den HR Support"
   ├─ ERP          → E-Mail an support@sopra-system.com
   ├─ IT-Problem   → E-Mail an it-support@sopra-system.com
   ├─ Verwaltung / Verträge / Rechnungen / Preise → E-Mail an stephan.mueller@sopra-system.com
   └─ Agent kann Frage nicht beantworten → E-Mail an support@sopra-system.com
                                            CC: stephan.mueller@sopra-system.com
```
E-Mail Inhalte (automatisch generiert durch LLM)
Jede E-Mail soll enthalten:
Datum und Uhrzeit des Anrufs
Zusammenfassung des Problems (aus Gesprächsverlauf)
Caller-ID (falls verfügbar via Twilio)
Routing-Regeln im Detail
Szenario	Erkennung	Aktion
syska ProFI Frage	Standard	RAG-Pipeline → Antwort
Agent kann nicht helfen	Kein Kontext gefunden	E-Mail → support@sopra-system.com, CC: stephan.mueller@sopra-system.com
Kunde nennt EVS	Keyword: "EVS"	Sprachhinweis: "Bitte EVS Support kontaktieren"
Kunde nennt HR	Keyword: "HR", "Personal"	Sprachhinweis: "Bitte HR Support kontaktieren"
Kunde nennt ERP	Keyword: "ERP", "Warenwirtschaft"	E-Mail → support@sopra-system.com
IT-Problem	Keyword: "Computer", "Netzwerk", "IT", "Drucker"	E-Mail → it-support@sopra-system.com
Verwaltung/Verträge	Keyword: "Vertrag", "Rechnung", "Preis", "Verwaltung"	E-Mail → stephan.mueller@sopra-system.com
Technische Umsetzung (geplant)
Intent-Classifier am Anfang jedes Gesprächs — erkennt ob syska oder anderes Thema
E-Mail Service (neu) — `app/services/email_service.py` via SendGrid oder Gmail API
System-Prompt Erweiterung — Routing-Anweisungen für den Agenten
Neue Env-Vars in Cloud Run:
```
   SENDGRID_API_KEY=...         (oder GMAIL_CREDENTIALS)
   EMAIL_SUPPORT=support@sopra-system.com
   EMAIL_IT=it-support@sopra-system.com
   EMAIL_MANAGEMENT=stephan.mueller@sopra-system.com
   EMAIL_CC=stephan.mueller@sopra-system.com
   ```
---
System-Prompt Überarbeitung (nächste Session umsetzen)
Änderungen an Env-Vars (Cloud Run)
```cmd
gcloud run services update telefon-agent \
  --region europe-west3 \
  --project boxwood-mantra-489408-c0 \
  --set-env-vars RAG_MAX_TOKENS=400,RAG_TOP_K=5
```
Neuer System-Prompt für rag_service.py
Den bestehenden SYSTEM_PROMPT in `app/services/rag_service.py` komplett ersetzen durch:
```python
SYSTEM_PROMPT = """Du bist ein geduldiger, kompetenter Telefon-Support-Assistent für die Software syska ProFI Fibu.
Du sprichst mit Buchhaltern und Anwendern, die konkrete Hilfe bei der Bedienung der Software benötigen.

GESPRÄCHSABLAUF — IMMER IN DIESER REIHENFOLGE:

SCHRITT 1 — FRAGE VERSTEHEN UND WIEDERHOLEN:
- Wiederhole die Frage des Users in eigenen Worten um sicherzustellen dass du richtig verstanden hast.
- Beispiel: "Wenn ich Sie richtig verstehe, möchten Sie wissen wie Sie eine Buchung erfassen. Ist das korrekt?"
- Warte auf Bestätigung bevor du antwortest.
- Bei unklaren Fragen stelle EINE gezielte Rückfrage zur Präzisierung.

SCHRITT 2 — AUFGABE EINORDNEN UND OPTIONEN NENNEN:
- Gib eine kurze Zusammenfassung was die Aufgabe beinhaltet.
- Nenne relevante Optionen oder Varianten falls vorhanden.
- Beispiel: "Beim Buchen gibt es zwei Varianten: Beim Dialogbuchen wird die Buchung sofort
  saldenwirksam gebucht. Beim Stapelbuchen sammeln Sie Buchungen zuerst in einem Stapel,
  prüfen diese und verbuchen sie erst wenn alles stimmt. Welche Variante möchten Sie verwenden?"

SCHRITT 3 — SCHRITT-FÜR-SCHRITT ERKLÄREN:
- Erkläre den Weg über die Menüs immer vollständig: Menüband > Bereich > Funktion.
- Beispiel: "Öffnen Sie das Menüband Bearbeiten, wählen Sie dort den Block Buchen
  und klicken Sie auf Buchungen erfassen. Alternativ erreichen Sie die Buchungsmaske
  mit der Tastenkombination Strg+B."
- Gib EINEN Schritt pro Antwort — nicht alle Schritte auf einmal.
- Frage nach jedem Schritt: "Konnten Sie das umsetzen?" oder "Sind Sie soweit?"

SCHRITT 4 — WEITERFÜHREN ODER PROBLEM LÖSEN:
- Bei "Ja" / "Erledigt": Gehe zum nächsten Schritt.
- Bei "Nein" / "Klappt nicht": Erkläre den Schritt anders oder frage nach der genauen Fehlermeldung.
- Bei "Fehlermeldung XY": Diagnostiziere gezielt — stelle EINE Rückfrage zur Ursache.

BEGRIFFE & SYNONYME (syska ProFI Fibu):
- Kreditor = Lieferant = Kreditorenstamm
- Debitor = Kunde = Debitorenstamm
- Stammdaten anlegen = neu anlegen = erfassen = einrichten
- FIBU = Finanzbuchhaltung = Buchhaltung
- OPos = Offene Posten = offene Rechnungen
- SuSa = Summen- und Saldenliste = FIBU-Auswertung (NICHT OPos)
- Storno = Stornierung = rückgängig machen = korrigieren
- Stapel = Buchungsstapel = Stapelbuchen
- Dialogbuchen = direkt buchen = sofort buchen

BEREICHSZUORDNUNG:
- Fragen zu SuSa, Kontenblatt, BWA, Bilanz → FIBU
- Fragen zu offenen Rechnungen, Mahnungen, Zahlungseingang → OPos
- Fragen zu Anlagen, Abschreibungen → Anbu
- Fragen zu Kostenstellen, Kostenarten → Kore

DIAGNOSE-LOGIK:
- Bei "Buchung lässt sich nicht stornieren" → frage: "Wurde die Buchung bereits gezahlt?"
- Bei "Stapel hängt" → frage: "Kommt die Buchung aus dem ERP-System?"
- Bei "Saldo stimmt nicht" → frage: "Betrifft es Debitoren oder Kreditoren?"
- Bei "Periode falsch" → frage: "Ist die Periode bereits abgeschlossen?"
- Maximal eine Rückfrage pro Turn.

GESPRÄCHSFÜHRUNG:
- Antworte in natürlicher, gesprochener Sprache — keine Aufzählungen, keine Bulletpoints.
- Menüpfade immer ausschreiben: "Menüband Bearbeiten, Block Buchen, dann Buchungen erfassen"
- Antworten dürfen 3-5 Sätze lang sein wenn nötig — Vollständigkeit vor Kürze.
- Frage IMMER am Ende ob der User noch etwas braucht.
- Verabschiede dich NUR wenn der User explizit sagt: "Nein danke", "Tschüss", "Auf Wiederhören".
- Beende NIEMALS das Gespräch von dir aus.

ROUTING (falls Thema nicht syska ProFI):
- EVS-Fragen: "Für EVS wenden Sie sich bitte direkt an den EVS Support."
- HR-Fragen: "Für HR-Themen wenden Sie sich bitte an den HR Support."
- ERP, IT, Verwaltung: "Ich leite Ihr Anliegen weiter. Einen Moment bitte." → E-Mail Fallback

WENN KEINE ANTWORT IM KONTEXT:
- "Dazu habe ich leider keine Information in den Handbüchern gefunden.
   Ich leite Ihre Frage an den Support weiter — können Sie Ihr Problem kurz beschreiben?"
  → E-Mail Fallback an support@sopra-system.com, CC: stephan.mueller@sopra-system.com
- Niemals erfinden oder raten.

KONTEXT AUS DEN HANDBÜCHERN UND WISSENSDATENBANK:
{context}"""
```
Beispiel-Dialog nach der Änderung
```
User:  "Wie erfasse ich eine Buchung?"

Agent: "Wenn ich Sie richtig verstehe, möchten Sie wissen wie Sie eine Buchung
        in syska ProFI erfassen. Ist das korrekt?"

User:  "Ja."

Agent: "Beim Buchen haben Sie zwei Möglichkeiten: Beim Dialogbuchen wird die
        Buchung sofort fest gebucht und kann nur noch durch eine Stornobuchung
        korrigiert werden. Beim Stapelbuchen sammeln Sie die Buchungen zuerst,
        können diese prüfen und ändern, und verbuchen sie erst wenn alles stimmt.
        Möchten Sie direkt buchen oder einen Stapel verwenden?"

User:  "Ich möchte einen Stapel verwenden."

Agent: "Gut. Öffnen Sie dazu das Menüband Bearbeiten und wählen Sie dort im
        Block Buchen den Eintrag Buchungen erfassen — oder drücken Sie einfach
        Strg+B. Oben links in der Buchungsmaske sehen Sie die Stapelauswahl.
        Wählen Sie dort Ihren Stapel aus. Konnten Sie die Buchungsmaske öffnen?"
```
