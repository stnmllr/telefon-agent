# .env-in-Git — Sicherheitsbewertung (25.06.2026)

## Befund
`.env` war seit dem Initial-Commit versioniert (Commits `741b518a`, `3c9535f5`).
Klingt nach Leak — **ist aber keiner:**

- Die in der History committeten Werte sind **Platzhalter**, keine echten Secrets:
  - `TWILIO_AUTH_TOKEN` = nur `xxxx…`
  - `TWILIO_ACCOUNT_SID` = Platzhalter-artig (`ACxxxx…`)
  - Restliche Variablen sind keine Credentials (Projekt-ID, Modellnamen, Rufnummer, RAG-Parameter).
- **Kein** echter API-Key in der History (kein ElevenLabs, kein SendGrid, kein OAuth-Secret).
- Der lokale, echte `.env` (mit `ELEVENLABS_API_KEY` etc.) wurde **nie committet** —
  verifiziert: der Schutz-Commit `fd3e2f32` enthält den Key nicht.

## Bewertung
- **Rotation nötig?** Nein. Es wurde nie ein echtes Geheimnis veröffentlicht.
- **Dauerhafter Fix (erledigt):** `.env` per `git rm --cached` aus dem Tracking
  genommen (Commit `fd3e2f32`); `.gitignore` greift jetzt. Die echte lokale Datei
  bleibt liegen und wird nicht mehr versioniert.

## Optional: History trotzdem säubern (kosmetisch)
Nur falls gewünscht (z.B. vor Veröffentlichung des Repos). **Schreibt die History um
→ Force-Push nötig, betrifft CI/CD-Auto-Deploy und alle Klone.** Nicht ausführen ohne
ausdrückliches Go.

```bash
# Variante A: git-filter-repo (empfohlen)
#   pip/pipx install git-filter-repo
git filter-repo --path .env --invert-paths

# Variante B: BFG
#   bfg --delete-files .env

# danach (destruktiv):
git push --force origin main
```

Vor einem Force-Push: lokalen Klon sichern, CI/CD-Auswirkungen prüfen
(GitHub Actions Push→Auto-Deploy), Mitwirkende informieren.

## Empfehlung
Da nie ein echtes Secret in der History lag, ist die Bereinigung **nicht dringend**.
Der bereits erfolgte Untracking-Fix reicht für den laufenden Betrieb. History-Rewrite
nur, wenn das Repo öffentlich/extern geteilt werden soll.
