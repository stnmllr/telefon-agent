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
