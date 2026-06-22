# ElevenLabs Tool-Backend (Phase 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein transport-agnostisches Cloud-Run-Tool-Backend (4 HTTP-Endpoints + pure Logic-Kerne + pytest + Playbook-YAML), das ElevenLabs Agents als „Server Tools" aufruft — neben dem unangetasteten Twilio-Altstack.

**Architecture:** Hexagonal: pure Funktionen unter `app/tools/` (kein I/O außer CSV-Read) sind direkt unit-testbar; dünne async HTTP-Schicht `app/routers/tools_router.py` macht Auth → Validierung → Pure-Core → Firestore/SendGrid-I/O (über monkeypatchbare Adapter-Funktionen) → Audit-Log. Empfänger-Routing ist über Firestore + PWA editierbar.

**Tech Stack:** Python 3.11, FastAPI, pydantic, `google-cloud-firestore` (AsyncClient), SendGrid, PyYAML, pytest + pytest-mock. Phonetisches Matching via eigener Kölner-Phonetik (stdlib, keine neue Dependency).

## Global Constraints

- Testaufruf immer: `uv run python -m pytest` (EPDR/WatchGuard-Workaround — in `CLAUDE.md` dokumentiert).
- In VS Code immer **Command Prompt**, nie PowerShell.
- Branch: `refactor/elevenlabs-phase-1`, abgezweigt von `migrate/gemini-2.5-flash`.
- Pure-Cores unter `app/tools/` dürfen **kein** Firestore/HTTP/SendGrid berühren (nur CSV-Read erlaubt).
- **Keine** neue Matching-Dependency: Kölner Phonetik selbst implementiert (stdlib).
- **Keine** Stefan→Stephan-Normalisierung im Telefonbuch-Pfad (zerstört Identität bei 2 Stefans + Stephan).
- Schreibende Endpoints (`send_email`, `create_ticket`): atomare Idempotenz via Firestore-Doc-ID `{call_id}:{tool}` (`create()`-Precondition).
- Recipient-Guard: `recipient_override` nur akzeptiert, wenn exakt = nicht-leere E-Mail aus `telefonbuch.csv`, sonst HTTP 422.
- Routing-Map: **kein** In-Prozess-Cache (Cloud Run multi-instance) — pro Call frisch aus Firestore laden.
- Co-Author-Trailer in jedem Commit: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Projekt-Setup, Branch & Abhängigkeiten

**Files:**
- Commit (vorhanden, uncommittet): `app/routers/call_router.py`, `app/utils/twiml_builder.py`, `app/services/email_service.py`
- Modify: `requirements.txt`, `app/config.py:7-41`, `PROJEKTSTAND.md`
- Create: `CLAUDE.md`, `app/tools/__init__.py`, `app/playbooks/__init__.py`

**Interfaces:**
- Produces: Branch `refactor/elevenlabs-phase-1`; `settings.tool_auth_token: str`; lauffähige pytest-Umgebung.

- [ ] **Step 1: Namens-Feature auf migrate committen**

```bash
git add app/routers/call_router.py app/utils/twiml_builder.py app/services/email_service.py
git commit -m "feat: Anrufer-Namen erfragen (name_asked-Stage)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 2: Refactor-Branch abzweigen**

```bash
git checkout -b refactor/elevenlabs-phase-1
git branch --show-current   # erwartet: refactor/elevenlabs-phase-1
```

- [ ] **Step 3: Test-Abhängigkeiten ergänzen**

An `requirements.txt` anhängen (httpx ist bereits vorhanden — nicht doppeln):

```
# Tests
pytest==8.3.2
pytest-mock==3.14.0
pytest-cov==5.0.0

# Playbooks
pyyaml==6.0.2
```

- [ ] **Step 4: `tool_auth_token` in Settings ergänzen**

In `app/config.py`, innerhalb der `Settings`-Klasse (nach `latency_logging: bool = False`, vor `class Config`):

```python
    # Tool-Backend (ElevenLabs Server-Tools)
    tool_auth_token: str = ""
```

- [ ] **Step 5: Paket-Verzeichnisse anlegen**

```bash
mkdir -p app/tools app/playbooks
printf '' > app/tools/__init__.py
printf '' > app/playbooks/__init__.py
```

- [ ] **Step 6: `CLAUDE.md` anlegen**

Datei `CLAUDE.md` mit Inhalt:

```markdown
# CLAUDE.md — telefon-agent

## Tests ausführen
Immer mit `uv` über das Modul aufrufen — NICHT die `pytest.exe` direkt:

```
uv run python -m pytest
```

**Warum `python -m pytest`:** Auf diesem Rechner blockiert der EPDR/WatchGuard-
Endpoint-Schutz den direkten `pytest.exe`-Entrypoint (wie bei FisherScreen). Der
Aufruf über `python -m pytest` umgeht den blockierten Entrypoint.

Einmalig die Umgebung aufsetzen (Python 3.12 wie in der Production/Dockerfile —
System-Python 3.14 hat keine Wheels für langchain/aiplatform):

```
uv venv --python 3.12
uv pip install -r requirements.txt
```

## Umgebung
- In VS Code immer **Command Prompt** verwenden, nie PowerShell.
- Pure-Logic-Kerne liegen unter `app/tools/` und dürfen kein I/O (Firestore/HTTP/
  SendGrid) berühren — nur CSV-Read. So bleiben sie direkt unit-testbar.

## Architektur
Siehe `docs/superpowers/specs/2026-06-22-elevenlabs-tool-backend-design.md`.
Pivot auf ElevenLabs Agents; dieses Repo liefert das Tool-Backend.
```

- [ ] **Step 7: Umgebung aufsetzen und Bestandstests laufen lassen**

Run:
```
uv venv --python 3.12
uv pip install -r requirements.txt
uv run python -m pytest tests/ -v
```
Expected: bestehende Tests in `tests/test_twiml.py` PASS (4 passed). Falls `uv pip install`
einzelne schwere Deps nicht bauen kann, prüfen ob `uv` das Managed-CPython 3.12 nutzt
(`uv run python --version` → 3.12.x).

- [ ] **Step 8: PROJEKTSTAND.md — Architektur-Pivot vermerken**

Am Anfang von `PROJEKTSTAND.md` die Titelzeile-Datierung aktualisieren und unter „Änderungshistorie" einen neuen Eintrag voranstellen:

```markdown
### 22.06.2026
- **Architektur-Pivot auf ElevenLabs Agents:** Voice-Loop + Reasoning wandern zu
  ElevenLabs (managed). Dieses Repo liefert künftig nur noch ein transport-agnostisches
  Tool-Backend (Cloud Run): Endpoints lookup_phonebook / check_absence / send_email /
  create_ticket + pure Logic-Kerne + pytest + Playbook-YAML. Der bestehende Twilio-/
  TwiML-/Vertex-AI-Search-Stack (call_router, twiml_builder, rag_service) bleibt vorerst
  unangetastet und deploybar, bis ElevenLabs produktiv ist. Spec:
  docs/superpowers/specs/2026-06-22-elevenlabs-tool-backend-design.md
```

- [ ] **Step 9: Commit**

```bash
git add requirements.txt app/config.py CLAUDE.md app/tools/__init__.py app/playbooks/__init__.py PROJEKTSTAND.md
git commit -m "chore: Setup Tool-Backend (Branch, Test-Deps, CLAUDE.md, tool_auth_token)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Kölner Phonetik (Pure-Core)

**Files:**
- Create: `app/tools/phonetik.py`
- Test: `tests/test_phonetik.py`

**Interfaces:**
- Produces: `koelner_phonetik(text: str) -> str` — phonetischer Code eines (Teil-)Worts; Umlaute/ß werden vor-normalisiert.

- [ ] **Step 1: Failing test schreiben**

`tests/test_phonetik.py`:

```python
from app.tools.phonetik import koelner_phonetik


def test_stefan_stephan_steffen_collide():
    code = koelner_phonetik("stefan")
    assert koelner_phonetik("stephan") == code
    assert koelner_phonetik("steffen") == code


def test_umlaut_baer_equals_bar():
    assert koelner_phonetik("Bär") == koelner_phonetik("Baer")
    assert koelner_phonetik("Bär") == koelner_phonetik("Bar")


def test_mueller_variants_collide():
    assert koelner_phonetik("Müller") == koelner_phonetik("Mueller")


def test_distinct_names_differ():
    assert koelner_phonetik("Schindler") != koelner_phonetik("Stefan")


def test_empty_string():
    assert koelner_phonetik("") == ""
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_phonetik.py -v`
Expected: FAIL (ModuleNotFoundError: app.tools.phonetik).

- [ ] **Step 3: Implementierung**

`app/tools/phonetik.py`:

```python
"""Kölner Phonetik (Cologne phonetics) — deutsches Soundex-Äquivalent.

Gruppiert STT-Misshears wie Stefan/Stephan/Steffen als phonetisch gleich.
Reine stdlib, kein I/O.
"""
import unicodedata

_VOWELS = set("aeijouy")
_UMLAUT_MAP = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss",
               "é": "e", "è": "e", "ê": "e", "â": "a", "ç": "c"}


def _preprocess(s: str) -> str:
    s = unicodedata.normalize("NFC", s).casefold()
    s = "".join(_UMLAUT_MAP.get(c, c) for c in s)
    return "".join(c for c in s if c.isalpha())


def koelner_phonetik(text: str) -> str:
    s = _preprocess(text)
    n = len(s)
    codes = []
    for i, c in enumerate(s):
        prev = s[i - 1] if i > 0 else ""
        nxt = s[i + 1] if i + 1 < n else ""
        if c in _VOWELS:
            code = "0"
        elif c == "b":
            code = "1"
        elif c == "p":
            code = "3" if nxt == "h" else "1"
        elif c in "dt":
            code = "8" if nxt in "csz" else "2"
        elif c in "fvw":
            code = "3"
        elif c in "gkq":
            code = "4"
        elif c == "c":
            if i == 0:
                code = "8" if nxt in "ahkloqrux" else "4"
            else:
                code = "8" if (prev in "sz" or nxt not in "ahkoqux") else "4"
        elif c == "x":
            code = "48"
        elif c == "l":
            code = "5"
        elif c in "mn":
            code = "6"
        elif c == "r":
            code = "7"
        elif c in "sz":
            code = "8"
        else:  # h und alles andere → kein Code
            code = ""
        codes.append(code)
    raw = "".join(codes)
    collapsed = []
    for ch in raw:
        if not collapsed or collapsed[-1] != ch:
            collapsed.append(ch)
    res = "".join(collapsed)
    if res:
        res = res[0] + res[1:].replace("0", "")
    return res
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_phonetik.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/tools/phonetik.py tests/test_phonetik.py
git commit -m "feat: Kölner Phonetik für phonetisches Namens-Matching

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Phonebook Fuzzy-Lookup (Pure-Core)

**Files:**
- Create: `app/tools/phonebook.py`
- Test: `tests/test_phonebook.py`

**Interfaces:**
- Consumes: `koelner_phonetik(text)` aus Task 2.
- Produces:
  - `fuzzy_lookup(name: str) -> list[dict]` — Treffer mit Keys `anrede, vorname, nachname, email, durchwahl, beschreibung`. Gibt alle Einträge mit maximaler Token-Treffer-Anzahl zurück.
  - `all_emails() -> set[str]` — alle nicht-leeren E-Mails aus `telefonbuch.csv`.

- [ ] **Step 1: Failing test schreiben**

`tests/test_phonebook.py`:

```python
from app.tools.phonebook import fuzzy_lookup, all_emails


def _nachnamen(matches):
    return sorted(m["nachname"] for m in matches)


def test_full_name_returns_only_best_match():
    # "Stefan Bär" matcht Bär auf beiden Tokens → nur Bär, NICHT Peters/Müller
    matches = fuzzy_lookup("Stefan Bär")
    assert _nachnamen(matches) == ["Bär"]


def test_firstname_only_returns_all_collisions():
    # reine Vornamen-Anfrage → alle phonetischen Kollisionen zur Disambiguierung
    matches = fuzzy_lookup("Stefan")
    nn = _nachnamen(matches)
    assert "Bär" in nn and "Peters" in nn and "Müller" in nn


def test_exact_lastname():
    matches = fuzzy_lookup("Schindler")
    assert _nachnamen(matches) == ["Schindler"]
    assert matches[0]["anrede"] == "Herr"
    assert matches[0]["durchwahl"] == "35"


def test_no_match_returns_empty():
    assert fuzzy_lookup("Xylophon") == []


def test_match_fields_present():
    m = fuzzy_lookup("Schindler")[0]
    assert set(m.keys()) == {"anrede", "vorname", "nachname", "email", "durchwahl", "beschreibung"}
    assert m["email"] == "Severin.Schindler@sopra-system.com"
    assert m["vorname"] == "Severin"


def test_all_emails_excludes_empty():
    emails = all_emails()
    assert "Severin.Schindler@sopra-system.com" in emails
    assert "" not in emails
    # "Zentrale" hat keine E-Mail → nicht enthalten
    assert all(e for e in emails)
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_phonebook.py -v`
Expected: FAIL (ModuleNotFoundError: app.tools.phonebook).

- [ ] **Step 3: Implementierung**

`app/tools/phonebook.py`:

```python
"""Telefonbuch-Lookup mit phonetischem Matching (Kölner Phonetik).

Pure-Core: liest nur telefonbuch.csv, kein sonstiges I/O.
KEINE Stefan→Stephan-Normalisierung — die rohen Tokens werden phonetisch
gegen alle Einträge gematcht, alle Maximal-Treffer zurückgegeben.
"""
import csv
import os
import unicodedata
from app.tools.phonetik import koelner_phonetik

_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "telefonbuch.csv")


def _rows():
    with open(_CSV_PATH, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def _split_name(name: str) -> tuple[str, str]:
    """'Nachname, Vorname' -> (nachname, vorname). Ohne Komma: (name, '')."""
    if "," in name:
        nach, _, vor = name.partition(",")
        return nach.strip(), vor.strip()
    return name.strip(), ""


def _query_tokens(text: str) -> list[str]:
    norm = unicodedata.normalize("NFC", text).casefold()
    return [t for t in norm.replace(",", " ").split() if len(t) > 2]


def all_emails() -> set[str]:
    return {r["Email"].strip() for r in _rows() if r.get("Email", "").strip()}


def fuzzy_lookup(name: str) -> list[dict]:
    query_codes = [c for c in (koelner_phonetik(t) for t in _query_tokens(name)) if c]
    if not query_codes:
        return []

    scored = []
    for r in _rows():
        nach, vor = _split_name(r["Name"])
        entry_codes = {koelner_phonetik(t) for t in (nach, vor) if t}
        entry_codes.discard("")
        hits = sum(1 for qc in query_codes if qc in entry_codes)
        if hits > 0:
            scored.append((hits, r, nach, vor))

    if not scored:
        return []

    best = max(h for h, *_ in scored)
    result = []
    for hits, r, nach, vor in scored:
        if hits == best:
            result.append({
                "anrede": r.get("Anrede", "").strip(),
                "vorname": vor,
                "nachname": nach,
                "email": r.get("Email", "").strip(),
                "durchwahl": r.get("Durchwahl", "").strip(),
                "beschreibung": r.get("Beschreibung", "").strip(),
            })
    return result
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_phonebook.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add app/tools/phonebook.py tests/test_phonebook.py
git commit -m "feat: phonetischer Telefonbuch-Lookup mit Token-Ranking

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Absence Sofia-Text (Pure-Core, Windows/Locale-Fix)

**Files:**
- Create: `app/tools/absence.py`
- Test: `tests/test_absence_tool.py`

**Interfaces:**
- Produces: `build_sofia_text(absence: dict) -> str` — gesprochener Abwesenheitstext; Windows-/Locale-sicher (festes deutsches Monats-Array, kein `strftime("%-d %B")`).

- [ ] **Step 1: Failing test schreiben**

`tests/test_absence_tool.py`:

```python
from app.tools.absence import build_sofia_text


def test_urlaub_with_date():
    txt = build_sofia_text({"type": "urlaub", "end": "2026-07-15"})
    assert txt == "Herr Müller ist im Urlaub und ab 15. Juli 2026 wieder erreichbar."


def test_meeting_with_time():
    txt = build_sofia_text({"type": "meeting", "end": "2026-07-15T14:00"})
    assert txt == "Herr Müller ist gerade im Meeting und ab 14:00 Uhr wieder erreichbar."


def test_dienstreise():
    txt = build_sofia_text({"type": "dienstreise", "end": "2026-08-01"})
    assert "auf Dienstreise" in txt and "1. August 2026" in txt


def test_abwesend_default_type():
    txt = build_sofia_text({"type": "abwesend", "end": "2026-07-15"})
    assert "derzeit abwesend" in txt


def test_invalid_date_graceful():
    txt = build_sofia_text({"type": "urlaub", "end": "kaputt"})
    assert txt == "Herr Müller ist im Urlaub."
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_absence_tool.py -v`
Expected: FAIL (ModuleNotFoundError: app.tools.absence).

- [ ] **Step 3: Implementierung**

`app/tools/absence.py`:

```python
"""Abwesenheits-Text für Sofia (Pure-Core).

Windows-/Locale-sicher: festes deutsches Monats-Array statt strftime('%-d %B').
"""
from datetime import datetime

_MONTHS_DE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
              "Juli", "August", "September", "Oktober", "November", "Dezember"]

_PHRASES = {
    "urlaub": "im Urlaub",
    "meeting": "im Meeting",
    "abwesend": "derzeit abwesend",
    "dienstreise": "auf Dienstreise",
}


def build_sofia_text(absence: dict) -> str:
    atype = absence.get("type", "abwesend")
    phrase = _PHRASES.get(atype, "derzeit abwesend")
    end = absence.get("end", "")

    if atype == "meeting":
        time_part = end.split("T")[1][:5] if "T" in end else end
        if time_part:
            return f"Herr Müller ist gerade {phrase} und ab {time_part} Uhr wieder erreichbar."
        return f"Herr Müller ist gerade {phrase}."

    date_part = end.split("T")[0]
    try:
        d = datetime.fromisoformat(date_part)
        formatted = f"{d.day}. {_MONTHS_DE[d.month]} {d.year}"
        return f"Herr Müller ist {phrase} und ab {formatted} wieder erreichbar."
    except (ValueError, IndexError):
        return f"Herr Müller ist {phrase}."
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_absence_tool.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/tools/absence.py tests/test_absence_tool.py
git commit -m "feat: Windows-/Locale-sicherer Abwesenheits-Sofia-Text

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Recipients — Routing-Defaults, Merge, Guard (Pure-Core)

**Files:**
- Create: `app/tools/recipients.py`
- Test: `tests/test_recipients.py`

**Interfaces:**
- Produces:
  - `DEFAULT_ROUTING: dict[str, str]` — 7 Kategorien (kein `phonebook`).
  - `merge_routing(overrides: dict | None) -> dict` — Defaults + valide Overrides (leeres/unbekanntes/`phonebook` → ignoriert/Default).
  - `resolve_recipient(category: str, routing: dict) -> str | None`.
  - `validate_override(email: str, valid_emails: set[str]) -> bool`.

- [ ] **Step 1: Failing test schreiben**

`tests/test_recipients.py`:

```python
from app.tools.recipients import (
    DEFAULT_ROUTING, merge_routing, resolve_recipient, validate_override,
)


def test_fibu_default_is_verwaltung_address():
    assert DEFAULT_ROUTING["fibu"] == "Stephan.Mueller@sopra-system.com"


def test_phonebook_not_in_defaults():
    assert "phonebook" not in DEFAULT_ROUTING


def test_override_wins():
    merged = merge_routing({"erp": "neu@sopra-system.com"})
    assert merged["erp"] == "neu@sopra-system.com"


def test_empty_override_falls_back_to_default():
    merged = merge_routing({"erp": "   "})
    assert merged["erp"] == DEFAULT_ROUTING["erp"]


def test_unknown_key_ignored():
    merged = merge_routing({"unsinn": "x@y.de"})
    assert "unsinn" not in merged


def test_phonebook_override_ignored():
    merged = merge_routing({"phonebook": "x@y.de"})
    assert "phonebook" not in merged


def test_resolve_phonebook_is_none():
    assert resolve_recipient("phonebook", DEFAULT_ROUTING) is None


def test_validate_override():
    valid = {"a@b.de", "c@d.de"}
    assert validate_override("a@b.de", valid) is True
    assert validate_override("halluziniert@x.de", valid) is False
    assert validate_override("", valid) is False
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_recipients.py -v`
Expected: FAIL (ModuleNotFoundError: app.tools.recipients).

- [ ] **Step 3: Implementierung**

`app/tools/recipients.py`:

```python
"""Empfänger-Routing (Pure-Core): Defaults, Merge mit Overrides, Override-Guard."""

DEFAULT_ROUTING: dict[str, str] = {
    "erp": "erp-support@sopra-system.com",
    "evs": "evs-support@sopra-system.com",
    "hr": "hr-support@sopra-system.com",
    "it": "it-support@sopra-system.com",
    "verwaltung": "Stephan.Mueller@sopra-system.com",
    "nachricht": "Stephan.Mueller@sopra-system.com",
    "fibu": "Stephan.Mueller@sopra-system.com",
}


def merge_routing(overrides: dict | None) -> dict:
    """Defaults überlagert durch valide Overrides.

    - nur Keys aus DEFAULT_ROUTING (unbekannte/`phonebook` ignoriert),
    - leeres Override -> Code-Default (statt '').
    """
    merged = dict(DEFAULT_ROUTING)
    if overrides:
        for key, value in overrides.items():
            if key in DEFAULT_ROUTING and isinstance(value, str) and value.strip():
                merged[key] = value.strip()
    return merged


def resolve_recipient(category: str, routing: dict) -> str | None:
    """Empfänger für eine Kategorie; `phonebook` ist override-only -> None."""
    return routing.get(category)


def validate_override(email: str, valid_emails: set[str]) -> bool:
    """True nur, wenn email exakt einer (nicht-leeren) Telefonbuch-Mail entspricht."""
    return bool(email and email.strip()) and email.strip() in valid_emails
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_recipients.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add app/tools/recipients.py tests/test_recipients.py
git commit -m "feat: Empfänger-Routing mit Merge + Override-Guard (inkl. fibu)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Ticket-ID-Format (Pure-Core)

**Files:**
- Create: `app/tools/tickets.py`
- Test: `tests/test_tickets.py`

**Interfaces:**
- Produces: `format_ticket_id(year: int, seq: int) -> str` → `"SOF-{year}-{seq:06d}"`.

- [ ] **Step 1: Failing test schreiben**

`tests/test_tickets.py`:

```python
from app.tools.tickets import format_ticket_id


def test_zero_padding():
    assert format_ticket_id(2026, 123) == "SOF-2026-000123"


def test_large_seq():
    assert format_ticket_id(2026, 1000000) == "SOF-2026-1000000"


def test_first_ticket():
    assert format_ticket_id(2026, 1) == "SOF-2026-000001"
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_tickets.py -v`
Expected: FAIL (ModuleNotFoundError: app.tools.tickets).

- [ ] **Step 3: Implementierung**

`app/tools/tickets.py`:

```python
"""Ticket-ID-Formatierung (Pure-Core)."""


def format_ticket_id(year: int, seq: int) -> str:
    return f"SOF-{year}-{seq:06d}"
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_tickets.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/tools/tickets.py tests/test_tickets.py
git commit -m "feat: Ticket-ID-Format SOF-YYYY-NNNNNN

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: email_service.send_email_raw + lazy rag-Import

**Files:**
- Modify: `app/services/email_service.py:1-12` (lazy import), Anhang neue Funktion
- Test: `tests/test_email_raw.py`

**Interfaces:**
- Consumes: SendGrid (gemockt im Test).
- Produces: `async send_email_raw(recipient_email: str, subject: str, plain_body: str, ticket_ref: str | None = None, callback: bool = False) -> tuple[bool, str]` → `(ok, message_id)`.

- [ ] **Step 1: Failing test schreiben**

`tests/test_email_raw.py`:

```python
import pytest
from app.services import email_service


class _FakeResponse:
    status_code = 202
    headers = {"X-Message-Id": "msg-123"}


class _FakeSG:
    def __init__(self, *a, **k):
        pass

    def send(self, message):
        return _FakeResponse()


@pytest.mark.asyncio
async def test_send_email_raw_success(monkeypatch):
    monkeypatch.setattr(email_service, "SENDGRID_API_KEY", "SG.test")
    monkeypatch.setattr(email_service, "SendGridAPIClient", _FakeSG)
    ok, message_id = await email_service.send_email_raw(
        "a@b.de", "Betreff", "Inhalt", ticket_ref="SOF-2026-000001")
    assert ok is True
    assert message_id == "msg-123"


@pytest.mark.asyncio
async def test_send_email_raw_no_key(monkeypatch):
    monkeypatch.setattr(email_service, "SENDGRID_API_KEY", "")
    ok, message_id = await email_service.send_email_raw("a@b.de", "B", "I")
    assert ok is False
    assert message_id == ""
```

`pytest-asyncio` wird für `@pytest.mark.asyncio` gebraucht. An `requirements.txt` ergänzen: `pytest-asyncio==0.23.8`, und `tests/` braucht eine Config. `pyproject`-frei: Datei `pytest.ini` anlegen:

```ini
[pytest]
asyncio_mode = auto
```

(Mit `asyncio_mode = auto` ist die `@pytest.mark.asyncio`-Markierung optional, aber unschädlich.)

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_email_raw.py -v`
Expected: FAIL (AttributeError: module 'app.services.email_service' has no attribute 'send_email_raw').

- [ ] **Step 3: rag-Import lazy machen**

In `app/services/email_service.py` die Modul-Import-Zeile entfernen:

```python
from app.services.rag_service import summarize_conversation
```

und stattdessen innerhalb von `send_routing_email` (vor der Nutzung von `summarize_conversation`, aktuell `summary = await summarize_conversation(...)`) lokal importieren:

```python
    from app.services.rag_service import summarize_conversation
    summary = await summarize_conversation(conversation_history)
```

(Entkoppelt den Vertex-/LangChain-Import vom Modul-Import, damit `email_service` ohne GCP-Stack importierbar ist.)

- [ ] **Step 4: `send_email_raw` ans Ende von `email_service.py` anhängen**

```python
async def send_email_raw(
    recipient_email: str,
    subject: str,
    plain_body: str,
    ticket_ref: str | None = None,
    callback: bool = False,
) -> tuple[bool, str]:
    """Versendet eine vom Agenten formulierte E-Mail direkt (ohne RAG-Summary).

    Returns (ok, message_id).
    """
    if not SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY nicht gesetzt — E-Mail wird nicht gesendet")
        return False, ""

    full_subject = f"[{ticket_ref}] {subject}" if ticket_ref else subject
    callback_note = "\n*** RÜCKRUF ERBETEN ***\n" if callback else ""
    plain = f"{callback_note}{plain_body}\n\n— Sofia, digitaler Assistent von Stephan Müller"
    html = (
        '<html><body style="font-family:Arial,sans-serif;color:#333">'
        + ('<div style="background:#c0392b;color:#fff;padding:8px 16px;font-weight:bold">'
           '&#128222; RÜCKRUF ERBETEN</div>' if callback else "")
        + f'<div style="padding:16px;white-space:pre-wrap">{plain_body}</div>'
        '<p style="font-size:12px;color:#888;padding:0 16px">'
        'Automatisch von Sofia generiert.</p></body></html>'
    )
    try:
        message = Mail(
            from_email=(EMAIL_FROM, EMAIL_FROM_NAME),
            to_emails=recipient_email,
            subject=full_subject,
            plain_text_content=plain,
            html_content=html,
        )
        response = SendGridAPIClient(SENDGRID_API_KEY).send(message)
        ok = response.status_code in (200, 202)
        message_id = response.headers.get("X-Message-Id", "") if ok else ""
        if not ok:
            logger.error("SendGrid Fehler: Status %d", response.status_code)
        return ok, message_id
    except Exception as e:
        logger.error("send_email_raw fehlgeschlagen: %s", e)
        return False, ""
```

An `requirements.txt` `pytest-asyncio==0.23.8` ergänzen und `pytest.ini` (Step 1) anlegen. Dann:
`uv pip install -r requirements.txt`

- [ ] **Step 5: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_email_raw.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/services/email_service.py tests/test_email_raw.py requirements.txt pytest.ini
git commit -m "feat: send_email_raw + lazy rag-Import in email_service

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: routing_config Service (Firestore-I/O, kein Cache)

**Files:**
- Create: `app/services/routing_config.py`
- Test: `tests/test_routing_config.py`

**Interfaces:**
- Produces:
  - `async load_overrides() -> dict` — `config/routing`-Doc als dict (leer bei Fehler/fehlend; Graceful).
  - `async save_overrides(overrides: dict) -> None` — merge-Schreiben nach `config/routing`.

- [ ] **Step 1: Failing test schreiben**

`tests/test_routing_config.py`:

```python
import pytest
from app.services import routing_config


class _Doc:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class _DocRef:
    def __init__(self, store, raises=False):
        self._store = store
        self._raises = raises

    async def get(self):
        if self._raises:
            raise RuntimeError("firestore down")
        return _Doc(self._store.get("data"))

    async def set(self, data, merge=False):
        self._store["data"] = {**(self._store.get("data") or {}), **data} if merge else data


class _Collection:
    def __init__(self, ref):
        self._ref = ref

    def document(self, _id):
        return self._ref


class _FakeDB:
    def __init__(self, ref):
        self._ref = ref

    def collection(self, _name):
        return _Collection(self._ref)


@pytest.mark.asyncio
async def test_load_overrides_returns_dict(monkeypatch):
    store = {"data": {"erp": "neu@x.de"}}
    monkeypatch.setattr(routing_config, "_db", lambda: _FakeDB(_DocRef(store)))
    assert await routing_config.load_overrides() == {"erp": "neu@x.de"}


@pytest.mark.asyncio
async def test_load_overrides_graceful_on_error(monkeypatch):
    monkeypatch.setattr(routing_config, "_db", lambda: _FakeDB(_DocRef({}, raises=True)))
    assert await routing_config.load_overrides() == {}


@pytest.mark.asyncio
async def test_save_overrides(monkeypatch):
    store = {"data": {"erp": "alt@x.de"}}
    monkeypatch.setattr(routing_config, "_db", lambda: _FakeDB(_DocRef(store)))
    await routing_config.save_overrides({"hr": "neu@x.de"})
    assert store["data"] == {"erp": "alt@x.de", "hr": "neu@x.de"}
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_routing_config.py -v`
Expected: FAIL (ModuleNotFoundError: app.services.routing_config).

- [ ] **Step 3: Implementierung**

`app/services/routing_config.py`:

```python
"""Firestore-Persistenz der Routing-Overrides (config/routing).

KEIN In-Prozess-Cache: Cloud Run ist multi-instance/scale-to-zero — pro Call
frisch laden, damit ein PWA-Edit sofort wirkt.
"""
import logging
from google.cloud import firestore

logger = logging.getLogger(__name__)


def _db() -> firestore.AsyncClient:
    return firestore.AsyncClient()


async def load_overrides() -> dict:
    try:
        doc = await _db().collection("config").document("routing").get()
        if doc.exists:
            return doc.to_dict() or {}
        return {}
    except Exception as exc:  # Graceful: nie den Call-Pfad blockieren
        logger.warning("routing_config.load_overrides fehlgeschlagen: %s", exc)
        return {}


async def save_overrides(overrides: dict) -> None:
    await _db().collection("config").document("routing").set(overrides, merge=True)
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_routing_config.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/routing_config.py tests/test_routing_config.py
git commit -m "feat: routing_config Firestore-Persistenz (kein Cache)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: tools_router — Gerüst, Auth, Idempotenz-Adapter, lookup_phonebook + check_absence

**Files:**
- Create: `app/routers/tools_router.py`
- Modify: `app/main.py:11-12,35-36`
- Test: `tests/test_tools_endpoints.py`

**Interfaces:**
- Consumes: `phonebook.fuzzy_lookup`, `absence.build_sofia_text`, Settings `tool_auth_token`.
- Produces (für Tasks 10/11 monkeypatchbar):
  - `require_tool_token` (FastAPI-Dependency, liest `settings.tool_auth_token` dynamisch).
  - `async reserve(call_id, tool) -> dict | None`, `async finalize(call_id, tool, **fields)`.
  - `async get_active_absence_safe() -> dict | None`.
  - `router` (APIRouter prefix `/tools`).

- [ ] **Step 1: Failing test schreiben**

`tests/test_tools_endpoints.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import tools_router
from app.config import settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "tool_auth_token", "secret")
    app = FastAPI()
    app.include_router(tools_router.router)
    return TestClient(app)


def test_auth_missing_token_401(client):
    r = client.post("/tools/lookup_phonebook", json={"name": "Schindler"})
    assert r.status_code == 401


def test_lookup_phonebook_match(client):
    r = client.post("/tools/lookup_phonebook",
                    json={"name": "Schindler"},
                    headers={"X-Tool-Token": "secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["matches"][0]["nachname"] == "Schindler"


def test_lookup_phonebook_no_match(client):
    r = client.post("/tools/lookup_phonebook",
                    json={"name": "Xylophon"},
                    headers={"X-Tool-Token": "secret"})
    assert r.json() == {"found": False}


def test_check_absence_active(client, monkeypatch):
    async def _fake():
        return {"type": "urlaub", "end": "2026-07-15"}
    monkeypatch.setattr(tools_router, "get_active_absence_safe", _fake)
    r = client.post("/tools/check_absence", json={"call_sid": "X"},
                    headers={"X-Tool-Token": "secret"})
    body = r.json()
    assert body["type"] == "conversation_initiation_client_data"
    assert body["dynamic_variables"]["absence_active"] == "true"
    assert "Urlaub" in body["dynamic_variables"]["absence_text"]


def test_check_absence_graceful_on_error(client, monkeypatch):
    async def _boom():
        raise RuntimeError("firestore down")
    monkeypatch.setattr(tools_router, "get_active_absence_safe", _boom)
    r = client.post("/tools/check_absence", json={"call_sid": "X"},
                    headers={"X-Tool-Token": "secret"})
    assert r.json()["dynamic_variables"]["absence_active"] == "false"
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_tools_endpoints.py -v`
Expected: FAIL (ModuleNotFoundError: app.routers.tools_router).

- [ ] **Step 3: Implementierung `tools_router.py`**

`app/routers/tools_router.py`:

```python
"""ElevenLabs Server-Tool-Endpoints (Cloud Run).

Dünne async HTTP-Schicht: Auth -> Validierung -> Pure-Core -> I/O -> Audit.
Firestore-Zugriffe sind in kleine, monkeypatchbare Adapter-Funktionen gekapselt.
"""
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from google.cloud import firestore
from google.api_core import exceptions as gexc

from app.config import settings
from app.tools import phonebook
from app.tools.absence import build_sofia_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools")


# ── Auth ─────────────────────────────────────────────────────
async def require_tool_token(x_tool_token: str = Header(default="")):
    expected = settings.tool_auth_token
    if not expected or not hmac.compare_digest(x_tool_token, expected):
        raise HTTPException(status_code=401, detail="invalid tool token")


# ── Firestore-Adapter (monkeypatchbar in Tests) ──────────────
def _db() -> firestore.AsyncClient:
    return firestore.AsyncClient()


def _audit_id(call_id: str, tool: str) -> str:
    return f"{call_id}:{tool}"


async def reserve(call_id: str | None, tool: str) -> dict | None:
    """Atomare Idempotenz-Reservierung. Returns vorhandenes Doc bei Duplikat, sonst None."""
    if not call_id:
        return None
    ref = _db().collection("tool_audit").document(_audit_id(call_id, tool))
    try:
        await ref.create({"tool": tool, "call_id": call_id, "status": "in_progress",
                          "ts": firestore.SERVER_TIMESTAMP})
        return None
    except gexc.AlreadyExists:
        doc = await ref.get()
        return doc.to_dict() if doc.exists else {"status": "in_progress"}


async def finalize(call_id: str | None, tool: str, **fields) -> None:
    data = {"tool": tool, "status": "done", "ts": firestore.SERVER_TIMESTAMP, **fields}
    if not call_id:
        await _db().collection("tool_audit").add(data)
        return
    ref = _db().collection("tool_audit").document(_audit_id(call_id, tool))
    await ref.set({"call_id": call_id, **data}, merge=True)


async def get_active_absence_safe() -> dict | None:
    from app.services.absence_service import get_active_absence
    return await get_active_absence()


# ── lookup_phonebook ─────────────────────────────────────────
class LookupReq(BaseModel):
    name: str


@router.post("/lookup_phonebook", dependencies=[Depends(require_tool_token)])
async def lookup_phonebook(req: LookupReq):
    matches = phonebook.fuzzy_lookup(req.name)
    if not matches:
        return {"found": False}
    return {"found": True, "matches": matches}


# ── check_absence (Conversation-Initiation-Webhook) ──────────
class InitWebhookReq(BaseModel):
    caller_id: str | None = None
    agent_id: str | None = None
    called_number: str | None = None
    call_sid: str | None = None


@router.post("/check_absence", dependencies=[Depends(require_tool_token)])
async def check_absence(req: InitWebhookReq):
    try:
        absence = await get_active_absence_safe()
    except Exception as exc:  # Graceful Degradation: Call-Setup nie blockieren
        logger.warning("check_absence Firestore-Fehler: %s", exc)
        absence = None
    if absence:
        dv = {"absence_active": "true", "absence_text": build_sofia_text(absence)}
    else:
        dv = {"absence_active": "false", "absence_text": ""}
    return {"type": "conversation_initiation_client_data", "dynamic_variables": dv}
```

- [ ] **Step 4: tools_router in `main.py` mounten**

In `app/main.py` Import ergänzen (nach Zeile 12 `from app.routers import app_router`):

```python
from app.routers import tools_router      # NEU
```

und Mount ergänzen (nach Zeile 36 `app.include_router(app_router.router, ...)`):

```python
app.include_router(tools_router.router, tags=["Tools"])   # NEU
```

- [ ] **Step 5: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_tools_endpoints.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add app/routers/tools_router.py app/main.py tests/test_tools_endpoints.py
git commit -m "feat: tools_router mit Auth, Idempotenz-Adapter, lookup_phonebook + check_absence

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: send_email-Endpoint (Guard + Idempotenz + Audit)

**Files:**
- Modify: `app/routers/tools_router.py` (Endpoint anhängen)
- Test: `tests/test_send_email_endpoint.py`

**Interfaces:**
- Consumes: `recipients`, `phonebook.all_emails`, `routing_config.load_overrides`, `email_service.send_email_raw`, `reserve`/`finalize` (Task 9).
- Produces: `POST /tools/send_email` → `{sent, recipient, message_id, ticket_ref}`.

- [ ] **Step 1: Failing test schreiben**

`tests/test_send_email_endpoint.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import tools_router
from app.config import settings
from app.services import email_service, routing_config


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "tool_auth_token", "secret")

    async def _no_overrides():
        return {}
    monkeypatch.setattr(routing_config, "load_overrides", _no_overrides)

    sent = []

    async def _fake_send(recipient, subject, body, ticket_ref=None, callback=False):
        sent.append({"recipient": recipient, "ticket_ref": ticket_ref})
        return True, "msg-1"
    monkeypatch.setattr(email_service, "send_email_raw", _fake_send)

    async def _reserve(call_id, tool):
        return None
    async def _finalize(call_id, tool, **fields):
        return None
    monkeypatch.setattr(tools_router, "reserve", _reserve)
    monkeypatch.setattr(tools_router, "finalize", _finalize)

    app = FastAPI()
    app.include_router(tools_router.router)
    c = TestClient(app)
    c._sent = sent
    return c


def _h():
    return {"X-Tool-Token": "secret"}


def test_send_email_category_routing(client):
    r = client.post("/tools/send_email", headers=_h(), json={
        "category": "erp", "subject": "S", "body": "B"})
    assert r.status_code == 200
    assert r.json()["recipient"] == "erp-support@sopra-system.com"
    assert r.json()["sent"] is True


def test_send_email_override_guard_rejects_hallucination(client):
    r = client.post("/tools/send_email", headers=_h(), json={
        "category": "phonebook", "subject": "S", "body": "B",
        "recipient_override": "halluziniert@x.de"})
    assert r.status_code == 422


def test_send_email_override_accepts_phonebook_email(client):
    r = client.post("/tools/send_email", headers=_h(), json={
        "category": "phonebook", "subject": "S", "body": "B",
        "recipient_override": "Severin.Schindler@sopra-system.com"})
    assert r.status_code == 200
    assert r.json()["recipient"] == "Severin.Schindler@sopra-system.com"


def test_send_email_idempotent_duplicate_skips_send(client, monkeypatch):
    async def _dup(call_id, tool):
        return {"status": "done", "recipient": "erp-support@sopra-system.com",
                "message_id": "old", "email_sent": True}
    monkeypatch.setattr(tools_router, "reserve", _dup)
    r = client.post("/tools/send_email", headers=_h(), json={
        "category": "erp", "subject": "S", "body": "B", "call_id": "C1"})
    assert r.status_code == 200
    assert r.json()["message_id"] == "old"
    assert client._sent == []   # kein erneuter Versand
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_send_email_endpoint.py -v`
Expected: FAIL (404 / kein /tools/send_email).

- [ ] **Step 3: Implementierung — Endpoint an `tools_router.py` anhängen**

Zusätzliche Imports oben in `tools_router.py` ergänzen:

```python
from app.tools import recipients
from app.services import routing_config, email_service
```

Endpoint anhängen:

```python
# ── send_email ───────────────────────────────────────────────
class SendEmailReq(BaseModel):
    category: str
    subject: str
    body: str
    caller_number: str = ""
    callback_requested: bool = False
    recipient_override: str | None = None
    call_id: str | None = None
    ticket_ref: str | None = None


async def _resolve_recipient(req: "SendEmailReq") -> str:
    if req.recipient_override:
        if not recipients.validate_override(req.recipient_override, phonebook.all_emails()):
            raise HTTPException(status_code=422, detail="recipient_override not in phonebook")
        return req.recipient_override
    routing = recipients.merge_routing(await routing_config.load_overrides())
    recipient = recipients.resolve_recipient(req.category, routing)
    if not recipient:
        raise HTTPException(status_code=422, detail=f"no recipient for category '{req.category}'")
    return recipient


@router.post("/send_email", dependencies=[Depends(require_tool_token)])
async def send_email(req: SendEmailReq):
    dup = await reserve(req.call_id, "send_email")
    if dup and dup.get("status") == "done":
        return {"sent": dup.get("email_sent", True), "recipient": dup.get("recipient"),
                "message_id": dup.get("message_id"), "ticket_ref": req.ticket_ref}

    recipient = await _resolve_recipient(req)
    ok, message_id = await email_service.send_email_raw(
        recipient, req.subject, req.body,
        ticket_ref=req.ticket_ref, callback=req.callback_requested)
    await finalize(req.call_id, "send_email", recipient=recipient,
                   message_id=message_id, email_sent=ok,
                   category=req.category, caller_number=req.caller_number)
    return {"sent": ok, "recipient": recipient, "message_id": message_id,
            "ticket_ref": req.ticket_ref}
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_send_email_endpoint.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/routers/tools_router.py tests/test_send_email_endpoint.py
git commit -m "feat: send_email-Endpoint mit Recipient-Guard + Idempotenz

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: create_ticket-Endpoint (Counter-Txn + interne Mail + Partial-Fail)

**Files:**
- Modify: `app/routers/tools_router.py` (Counter-Adapter + Endpoint anhängen)
- Test: `tests/test_create_ticket_endpoint.py`

**Interfaces:**
- Consumes: `tickets.format_ticket_id`, `recipients`, `routing_config`, `email_service.send_email_raw`, `reserve`/`finalize`.
- Produces:
  - `async next_ticket_seq() -> int` (monkeypatchbar), `async save_ticket(record: dict) -> None`.
  - `POST /tools/create_ticket` → `{created, ticket_id, email_sent}`.

- [ ] **Step 1: Failing test schreiben**

`tests/test_create_ticket_endpoint.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import tools_router
from app.config import settings
from app.services import email_service, routing_config


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "tool_auth_token", "secret")

    async def _no_overrides():
        return {}
    monkeypatch.setattr(routing_config, "load_overrides", _no_overrides)

    async def _seq():
        return 123
    monkeypatch.setattr(tools_router, "next_ticket_seq", _seq)

    saved = []
    async def _save(record):
        saved.append(record)
    monkeypatch.setattr(tools_router, "save_ticket", _save)

    async def _reserve(call_id, tool):
        return None
    async def _finalize(call_id, tool, **fields):
        return None
    monkeypatch.setattr(tools_router, "reserve", _reserve)
    monkeypatch.setattr(tools_router, "finalize", _finalize)

    app = FastAPI()
    app.include_router(tools_router.router)
    c = TestClient(app)
    c._saved = saved
    return c


def _h():
    return {"X-Tool-Token": "secret"}


def test_create_ticket_success(client, monkeypatch):
    async def _send(*a, **k):
        return True, "msg-9"
    monkeypatch.setattr(email_service, "send_email_raw", _send)
    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "erp", "summary": "Drucker kaputt", "caller_number": "+49..."})
    body = r.json()
    assert body["created"] is True
    assert body["ticket_id"].startswith("SOF-") and body["ticket_id"].endswith("000123")
    assert body["email_sent"] is True
    assert client._saved and client._saved[0]["ticket_id"] == body["ticket_id"]


def test_create_ticket_partial_fail_email(client, monkeypatch):
    async def _send_fail(*a, **k):
        return False, ""
    monkeypatch.setattr(email_service, "send_email_raw", _send_fail)
    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "erp", "summary": "X", "caller_number": "+49..."})
    body = r.json()
    assert body["created"] is True          # Ticket gilt trotzdem als erstellt
    assert body["email_sent"] is False      # Mail fehlgeschlagen
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_create_ticket_endpoint.py -v`
Expected: FAIL (404 / kein /tools/create_ticket).

- [ ] **Step 3: Implementierung — Counter-Adapter + Endpoint an `tools_router.py` anhängen**

Import oben ergänzen:

```python
from datetime import datetime, timezone
from app.tools import tickets
```

Adapter + Endpoint anhängen:

```python
# ── create_ticket ────────────────────────────────────────────
async def next_ticket_seq() -> int:
    db = _db()
    ref = db.collection("counters").document("tickets")

    @firestore.async_transactional
    async def _txn(txn):
        snap = await ref.get(transaction=txn)
        current = (snap.to_dict() or {}).get("seq", 0) if snap.exists else 0
        nxt = current + 1
        txn.set(ref, {"seq": nxt}, merge=True)
        return nxt

    return await _txn(db.transaction())


async def save_ticket(record: dict) -> None:
    await _db().collection("tickets").document(record["ticket_id"]).set(record)


class CreateTicketReq(BaseModel):
    category: str
    summary: str
    caller_number: str = ""
    callback_requested: bool = False
    priority: str = "normal"
    call_id: str | None = None


@router.post("/create_ticket", dependencies=[Depends(require_tool_token)])
async def create_ticket(req: CreateTicketReq):
    dup = await reserve(req.call_id, "create_ticket")
    if dup and dup.get("status") == "done":
        return {"created": True, "ticket_id": dup.get("ticket_id"),
                "email_sent": dup.get("email_sent", False)}

    year = datetime.now(timezone.utc).year
    seq = await next_ticket_seq()
    ticket_id = tickets.format_ticket_id(year, seq)
    # Ticket gilt ab Record-Existenz als erstellt:
    await save_ticket({
        "ticket_id": ticket_id, "category": req.category, "summary": req.summary,
        "caller_number": req.caller_number, "priority": req.priority,
        "callback_requested": req.callback_requested,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    routing = recipients.merge_routing(await routing_config.load_overrides())
    recipient = recipients.resolve_recipient(req.category, routing) \
        or recipients.DEFAULT_ROUTING["verwaltung"]
    ok, message_id = await email_service.send_email_raw(
        recipient, f"Ticket {ticket_id}: {req.summary[:60]}", req.summary,
        ticket_ref=ticket_id, callback=req.callback_requested)

    await finalize(req.call_id, "create_ticket", ticket_id=ticket_id,
                   recipient=recipient, message_id=message_id, email_sent=ok,
                   category=req.category)
    return {"created": True, "ticket_id": ticket_id, "email_sent": ok}
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_create_ticket_endpoint.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/routers/tools_router.py tests/test_create_ticket_endpoint.py
git commit -m "feat: create_ticket-Endpoint (Counter-Txn, interne Mail, Partial-Fail)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: PWA Routing-Config-API (GET/PUT /app/api/routing)

**Files:**
- Modify: `app/routers/app_router.py` (Endpoints anhängen, nach Zeile 211)
- Test: `tests/test_routing_api.py`

**Interfaces:**
- Consumes: `recipients.merge_routing`, `recipients.DEFAULT_ROUTING`, `routing_config.load_overrides/save_overrides`, `require_auth` (vorhanden).
- Produces:
  - `GET /app/api/routing` → `{"routing": {category: email}}` (effektive Map).
  - `PUT /app/api/routing` body `{"routing": {category: email}}` → speichert Overrides + `routing_change`-Audit.

- [ ] **Step 1: Failing test schreiben**

`tests/test_routing_api.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import app_router
from app.services import routing_config


@pytest.fixture
def client(monkeypatch):
    # Auth umgehen: require_auth-Dependency überschreiben
    app = FastAPI()
    app.include_router(app_router.router)
    app.dependency_overrides[app_router.require_auth] = lambda: "stn.mueller@gmail.com"

    store = {"data": {}}

    async def _load():
        return dict(store["data"])
    async def _save(overrides):
        store["data"].update(overrides)
    monkeypatch.setattr(routing_config, "load_overrides", _load)
    monkeypatch.setattr(routing_config, "save_overrides", _save)
    monkeypatch.setattr(app_router, "_audit_routing_change", lambda *a, **k: None)

    c = TestClient(app)
    c._store = store
    return c


def test_get_routing_returns_effective_map(client):
    r = client.get("/app/api/routing")
    assert r.status_code == 200
    routing = r.json()["routing"]
    assert routing["fibu"] == "Stephan.Mueller@sopra-system.com"


def test_put_routing_saves_override(client):
    r = client.put("/app/api/routing", json={"routing": {"erp": "neu@sopra-system.com"}})
    assert r.status_code == 200
    assert client._store["data"]["erp"] == "neu@sopra-system.com"
    # GET reflektiert den Override
    routing = client.get("/app/api/routing").json()["routing"]
    assert routing["erp"] == "neu@sopra-system.com"


def test_put_routing_rejects_invalid_email(client):
    r = client.put("/app/api/routing", json={"routing": {"erp": "keine-email"}})
    assert r.status_code == 422
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_routing_api.py -v`
Expected: FAIL (404 / kein /app/api/routing).

- [ ] **Step 3: Implementierung — an `app_router.py` anhängen**

Imports oben in `app_router.py` ergänzen:

```python
from app.tools import recipients
from app.services import routing_config
```

Endpoints + Audit-Helfer anhängen (ans Dateiende):

```python
# ── Routing-Config API ───────────────────────────────────────

_EMAIL_RE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _audit_routing_change(category: str, old: str, new: str) -> None:
    """Leichtes Audit einer Empfänger-Umstellung."""
    try:
        _db.collection("tool_audit").add({
            "tool": "routing_change", "category": category,
            "old": old, "new": new,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.warning("routing_change-Audit fehlgeschlagen: %s", exc)


class RoutingUpdate(BaseModel):
    routing: dict


@router.get("/api/routing")
async def get_routing(email: str = Depends(require_auth)):
    overrides = await routing_config.load_overrides()
    return {"routing": recipients.merge_routing(overrides)}


@router.put("/api/routing")
async def put_routing(body: RoutingUpdate, email: str = Depends(require_auth)):
    overrides = {}
    current = recipients.merge_routing(await routing_config.load_overrides())
    for category, addr in body.routing.items():
        if category not in recipients.DEFAULT_ROUTING:
            continue   # unbekannte Keys / phonebook ignorieren
        addr = (addr or "").strip()
        if not addr:
            continue   # leer -> Default behalten
        if not _EMAIL_RE.match(addr):
            raise HTTPException(status_code=422, detail=f"ungültige E-Mail: {addr}")
        if addr != current.get(category):
            _audit_routing_change(category, current.get(category, ""), addr)
        overrides[category] = addr
    await routing_config.save_overrides(overrides)
    return {"success": True, "routing": recipients.merge_routing(
        await routing_config.load_overrides())}
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_routing_api.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/routers/app_router.py tests/test_routing_api.py
git commit -m "feat: PWA Routing-Config-API (GET/PUT /app/api/routing) + Audit

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: PWA Frontend — Empfänger-Settings-Sektion

**Files:**
- Modify: `app/static/index.html`
- Test: manuell (kein Unit-Test für statisches HTML; Smoke über bestehende API-Tests aus Task 12)

**Interfaces:**
- Consumes: `GET/PUT /app/api/routing` aus Task 12.

- [ ] **Step 1: Bestehende Struktur sichten**

Run: `uv run python -m pytest tests/test_routing_api.py -v` (muss weiter grün sein)
Dann `app/static/index.html` öffnen und die vorhandene Abwesenheits-Sektion + den fetch-Stil (Auth via Cookie, `/app/...`-Endpoints) als Vorlage identifizieren.

- [ ] **Step 2: Settings-Sektion + JS ergänzen**

In `app/static/index.html` eine neue Sektion nach der Abwesenheits-Sektion einfügen (Klassen/Stil an Bestehendes anlehnen):

```html
<section id="routing-settings">
  <h2>Empfänger</h2>
  <p class="hint">Ziel-E-Mail je Kategorie. Leeres Feld = Standard.</p>
  <div id="routing-list"></div>
  <button id="routing-save">Speichern</button>
  <span id="routing-status"></span>
</section>
```

JS (im bestehenden `<script>`-Block, gleicher fetch-Stil mit `credentials: "include"`):

```javascript
async function loadRouting() {
  const res = await fetch("/app/api/routing", { credentials: "include" });
  if (!res.ok) return;
  const { routing } = await res.json();
  const list = document.getElementById("routing-list");
  list.innerHTML = "";
  Object.keys(routing).sort().forEach((cat) => {
    const row = document.createElement("div");
    row.className = "routing-row";
    row.innerHTML =
      `<label>${cat}</label>` +
      `<input type="email" data-cat="${cat}" value="${routing[cat]}">`;
    list.appendChild(row);
  });
}

document.getElementById("routing-save").addEventListener("click", async () => {
  const inputs = document.querySelectorAll("#routing-list input[data-cat]");
  const routing = {};
  inputs.forEach((i) => { routing[i.dataset.cat] = i.value.trim(); });
  const res = await fetch("/app/api/routing", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ routing }),
  });
  document.getElementById("routing-status").textContent =
    res.ok ? "Gespeichert ✓" : "Fehler beim Speichern";
});

// beim Laden (nach erfolgreichem Auth-Check) aufrufen:
loadRouting();
```

(Den `loadRouting()`-Aufruf an dieselbe Stelle hängen, an der die Abwesenheitsliste nach Auth geladen wird.)

- [ ] **Step 3: Manueller Smoke-Test (lokal, optional)**

Wenn lokal mit Login testbar: `uv run uvicorn app.main:app --reload`, einloggen, Empfänger ändern, speichern, neu laden → Wert bleibt. Andernfalls in Cloud-Run-Deploy verifizieren.

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat: PWA Settings-Sektion zum Editieren der Empfänger

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: Playbook-YAML — Schema-Doku + Beispiel + Smoke-Test

**Files:**
- Create: `app/playbooks/README.md`, `app/playbooks/fibu-periode-gesperrt.yaml`
- Test: `tests/test_playbooks.py`

**Interfaces:**
- Produces: validierbare Playbook-YAMLs (Pflichtfelder: `id, title, area, trigger, diagnose, loesung, verifikation, eskalation, handbuch_refs`).

- [ ] **Step 1: Failing test schreiben**

`tests/test_playbooks.py`:

```python
import glob
import os
import yaml

_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "playbooks")
_REQUIRED = {"id", "title", "area", "trigger", "diagnose",
             "loesung", "verifikation", "eskalation", "handbuch_refs"}
_AREAS = {"FIBU", "ERP", "EVS", "HR", "IT", "Verwaltung"}


def _playbook_entries():
    for path in glob.glob(os.path.join(_DIR, "*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, list), f"{path}: muss eine Liste sein"
        for entry in data:
            yield path, entry


def test_at_least_one_playbook_exists():
    assert list(_playbook_entries()), "kein Playbook gefunden"


def test_required_fields_present():
    for path, entry in _playbook_entries():
        missing = _REQUIRED - set(entry.keys())
        assert not missing, f"{path}: fehlende Felder {missing}"


def test_area_valid():
    for path, entry in _playbook_entries():
        assert entry["area"] in _AREAS, f"{path}: ungültige area {entry['area']}"


def test_eskalation_has_bedingung_and_aktion():
    for path, entry in _playbook_entries():
        for esk in entry["eskalation"]:
            assert "bedingung" in esk and "aktion" in esk, f"{path}: eskalation unvollständig"
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `uv run python -m pytest tests/test_playbooks.py -v`
Expected: FAIL (`test_at_least_one_playbook_exists` — kein Playbook).

- [ ] **Step 3: Beispiel-Playbook anlegen**

`app/playbooks/fibu-periode-gesperrt.yaml`:

```yaml
- id: fibu-periode-gesperrt
  title: "Buchung nicht möglich – Periode gesperrt"
  area: FIBU
  trigger:
    - "kann nicht buchen"
    - "Periode ist gesperrt"
    - "Buchung wird abgelehnt"
  diagnose:
    - "Welcher Buchungsmonat bzw. welche Periode betrifft es?"
    - "Erscheint eine konkrete Fehlermeldung? Wenn ja, welche genau?"
  loesung:
    - "<<aus Handbuch/Fachwissen befüllen – z. B. Pfad zur Periodenverwaltung>>"
    - "<<Schritt 2 – aus Handbuch befüllen>>"
  verifikation:
    - "Bitten Sie den Anrufer, die Buchung erneut zu versuchen."
  eskalation:
    - bedingung: "Anrufer hat keine Berechtigung zum Entsperren"
      aktion: transfer
    - bedingung: "Fehlermeldung deutet auf Datenbank-/Integritätsproblem"
      aktion: ticket_hoch
  handbuch_refs:
    - "ProFI FIBU – Periodenverwaltung"
```

- [ ] **Step 4: Schema-README anlegen**

`app/playbooks/README.md`:

```markdown
# Troubleshooting-Playbooks

Strukturierte YAML-Dokumente für die ElevenLabs Knowledge Base. Jede Datei ist
eine YAML-**Liste** von Playbook-Einträgen.

## Pflichtfelder

| Feld           | Zweck                                                        |
|----------------|-------------------------------------------------------------|
| `id`           | eindeutiger Slug                                            |
| `title`        | sprechender Titel                                          |
| `area`         | FIBU \| ERP \| EVS \| HR \| IT \| Verwaltung                |
| `trigger`      | Symptom-Sprache des Anrufers (Erkennung, nicht Keywords)   |
| `diagnose`     | gezielte Rückfragen zur Eingrenzung                        |
| `loesung`      | sprechbare Lösungsschritte (kurz, gesprochen)              |
| `verifikation` | wie bestätigt wird, dass der Fall gelöst ist               |
| `eskalation`   | Liste aus `{bedingung, aktion}` — aktion: transfer \| ticket_hoch \| ticket |
| `handbuch_refs`| Querverweis auf KB-Handbuch für Faktenrückhalt            |

## WICHTIG
Die `loesung`-Schritte MÜSSEN aus echtem Fachwissen / den Handbüchern stammen.
Platzhalter `<<...>>` markieren ungefüllten Fachinhalt — vor Produktivnutzung ersetzen.
Ein selbstbewusst falsch antwortender Agent ist schlechter als ein Anrufbeantworter.
```

- [ ] **Step 5: Test laufen lassen — muss bestehen**

Run: `uv run python -m pytest tests/test_playbooks.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add app/playbooks/README.md app/playbooks/fibu-periode-gesperrt.yaml tests/test_playbooks.py
git commit -m "feat: Playbook-YAML-Schema + FIBU-Beispiel + Smoke-Test

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 15: Gesamt-Suite grün + Status

**Files:**
- Modify: `docs/superpowers/specs/2026-06-22-elevenlabs-tool-backend-design.md:5` (Status)

**Interfaces:** keine.

- [ ] **Step 1: Komplette Suite mit Coverage laufen lassen**

Run: `uv run python -m pytest --cov=app/tools --cov=app/routers/tools_router --cov-report=term-missing -v`
Expected: alle Tests PASS; Coverage auf `app/tools/*` ~95 %+.

- [ ] **Step 2: Spec-Status auf umgesetzt setzen**

In `docs/superpowers/specs/2026-06-22-elevenlabs-tool-backend-design.md` Zeile 5:

```markdown
**Status:** Phase-1-Code implementiert (pytest grün). Dashboard-Config + L2-Eval offen.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-22-elevenlabs-tool-backend-design.md
git commit -m "chore: Phase-1-Tool-Backend implementiert, Suite grün

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (gegen Spec)

**Spec-Coverage:**
- §3.1 lookup_phonebook → Task 3 (Core) + Task 9 (Endpoint) ✅
- §3.2 check_absence (Webhook-Envelope, Graceful Degradation) → Task 4 (Core) + Task 9 (Endpoint) ✅
- §3.3 send_email (Guard, ticket_ref) → Task 7 (raw) + Task 10 ✅
- §3.4 create_ticket (Counter-Txn, Partial-Fail) → Task 6 + Task 11 ✅
- §3 Auth/Audit/Idempotenz (atomar) → Task 9 (reserve/finalize) + genutzt in 10/11 ✅
- §5 Routing-Map konfigurierbar (kein Cache, defensive Merge, fibu) → Task 5 + Task 8 + Task 12 + Task 13 ✅
- §6 Tests (TDD-Reihenfolge, alle genannten Fälle) → Tasks 2–14 ✅
- §7 Playbook-YAML → Task 14 ✅
- §8 Setup (Commit, Branch, CLAUDE.md, requirements, PROJEKTSTAND) → Task 1 ✅

**Platzhalter-Scan:** Einziger bewusster Platzhalter ist `<<...>>` in `loesung` (per Spec gefordert — Fachinhalt vom Nutzer). Kein TODO/TBD in Code.

**Typ-Konsistenz:** `reserve/finalize`, `next_ticket_seq/save_ticket`, `send_email_raw -> (bool, str)`, `merge_routing/resolve_recipient/validate_override`, `fuzzy_lookup -> list[dict]`, `build_sofia_text -> str` — Signaturen in Definitions- und Konsumtasks identisch.

**Caveat (im Spec vermerkt):** check_absence trägt in Phase-1 `require_tool_token`; die echte Conversation-Initiation-Webhook-Auth (ElevenLabs HMAC) wird beim Dashboard-Wiring final abgeglichen.
