# FIBU-Abwesenheits-Eskalation (E-Mail an Kühn) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wenn ein FIBU-Eskalationsticket (`create_ticket` mit `category="fibu"`) eingeht UND Stephan Müller laut Firestore gerade abwesend ist, geht die Ticket-Benachrichtigung an `kuehn@eevolution.de` mit Stephan im CC; sonst unverändert.

**Architecture:** Rein serverseitig im Tool-Backend (`app/`). Die Eskalation ist bereits das Signal „konnte nicht lösen" — kein neuer Intent nötig. Die Umleitung passiert im `create_ticket`-Handler; die Kühn-Adresse ist ein über die bestehende Routing-Config editierbarer Schlüssel; CC ist eine neue, generische Fähigkeit von `send_email_raw`.

**Tech Stack:** Python 3.12, FastAPI, Resend (raw httpx), Firestore, pytest (`uv run python -m pytest`).

## Global Constraints

- Tests IMMER via `uv run python -m pytest` (nie `pytest.exe` direkt) — EPDR blockiert den Entrypoint.
- Pure-Logic-Kerne unter `app/tools/` bleiben I/O-frei (nur CSV-Read).
- Kein Secret/Key-Logging in `email_service`.
- Empfänger-Auflösung ist case-insensitiv (`resolve_recipient` normalisiert `.strip().lower()`).
- Abwesenheits-Check darf die Ticket-Erstellung NIE blockieren (graceful: Fehler → wie „nicht abwesend").
- Firestore-Collection der Abwesenheiten: `absence`; aktiver Eintrag via `absence_service.get_active_absence()`.

---

### Task 1: CC-Unterstützung in `send_email_raw`

**Files:**
- Modify: `app/services/email_service.py:42-84` (`_resend_send`), `app/services/email_service.py:219-...` (`send_email_raw`)
- Test: `tests/test_email_raw.py`

**Interfaces:**
- Consumes: nichts Neues.
- Produces:
  - `_resend_send(recipient_email: str, subject: str, html_body: str, text_body: str, cc: list[str] | None = None) -> tuple[bool, str]`
  - `send_email_raw(recipient_email, subject, plain_body, ticket_ref=None, callback=False, header_rows=None, cc: list[str] | None = None) -> tuple[bool, str]`
  - Resend-Payload enthält `"cc": [...]` NUR wenn `cc` nicht leer ist.

- [ ] **Step 1: Failing Test schreiben**

In `tests/test_email_raw.py` ergänzen:

```python
@pytest.mark.asyncio
async def test_send_email_raw_sets_cc(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"id": "re_cc"})

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_live_key")
    monkeypatch.setattr(email_service, "_client", _mock_client(handler))

    ok, _ = await email_service.send_email_raw(
        "to@x.de", "B", "Body", cc=["cc@x.de"])
    assert ok is True
    assert captured["json"]["cc"] == ["cc@x.de"]


@pytest.mark.asyncio
async def test_send_email_raw_no_cc_key_when_absent(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"id": "re_nocc"})

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "re_live_key")
    monkeypatch.setattr(email_service, "_client", _mock_client(handler))

    await email_service.send_email_raw("to@x.de", "B", "Body")
    assert "cc" not in captured["json"]
```

- [ ] **Step 2: Test laufen lassen (muss failen)**

Run: `uv run python -m pytest tests/test_email_raw.py::test_send_email_raw_sets_cc -v`
Expected: FAIL (`TypeError: unexpected keyword argument 'cc'`).

- [ ] **Step 3: `_resend_send` um `cc` erweitern**

In `app/services/email_service.py`, Signatur und Payload von `_resend_send`:

```python
async def _resend_send(
    recipient_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    cc: list[str] | None = None,
) -> tuple[bool, str]:
    """Versendet eine E-Mail über die Resend-API. Returns (ok, message_id)."""
    key = RESEND_API_KEY.strip()
    if not key:
        logger.warning("RESEND_API_KEY nicht gesetzt — E-Mail wird nicht gesendet")
        return False, ""

    payload = {
        "from": f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>",
        "to": [recipient_email],
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }
    if cc:
        payload["cc"] = cc
```

(Rest der Funktion unverändert.)

- [ ] **Step 4: `send_email_raw` um `cc` erweitern**

Signatur und der abschließende `_resend_send`-Aufruf in `send_email_raw`:

```python
async def send_email_raw(
    recipient_email: str,
    subject: str,
    plain_body: str,
    ticket_ref: str | None = None,
    callback: bool = False,
    header_rows: list[tuple[str, str]] | None = None,
    cc: list[str] | None = None,
) -> tuple[bool, str]:
```

Und die Rückgabezeile:

```python
    return await _resend_send(recipient_email, full_subject, html, plain, cc=cc)
```

- [ ] **Step 5: Tests laufen lassen (müssen passen)**

Run: `uv run python -m pytest tests/test_email_raw.py -v`
Expected: PASS (alle, inkl. der zwei neuen).

- [ ] **Step 6: Commit**

```bash
git add app/services/email_service.py tests/test_email_raw.py
git commit -m "feat: CC-Support in send_email_raw (Resend cc-Feld)"
```

---

### Task 2: Kühn-Adresse als editierbarer Routing-Default

**Files:**
- Modify: `app/tools/recipients.py:3-11` (`DEFAULT_ROUTING`)
- Test: `tests/test_recipients.py`

**Interfaces:**
- Produces: `recipients.DEFAULT_ROUTING["fibu_absence"] == "kuehn@eevolution.de"`. Über `merge_routing`/`config/routing` überschreibbar; via `resolve_recipient("fibu_absence", routing)` bzw. `routing.get("fibu_absence")` lesbar.

- [ ] **Step 1: Failing Test schreiben**

In `tests/test_recipients.py` ergänzen:

```python
def test_fibu_absence_default_is_kuehn():
    assert DEFAULT_ROUTING["fibu_absence"] == "kuehn@eevolution.de"


def test_fibu_absence_override_wins():
    merged = merge_routing({"fibu_absence": "neu@extern.de"})
    assert merged["fibu_absence"] == "neu@extern.de"
```

- [ ] **Step 2: Test laufen lassen (muss failen)**

Run: `uv run python -m pytest tests/test_recipients.py::test_fibu_absence_default_is_kuehn -v`
Expected: FAIL (`KeyError: 'fibu_absence'`).

- [ ] **Step 3: Default ergänzen**

In `app/tools/recipients.py` `DEFAULT_ROUTING` um den Schlüssel erweitern:

```python
DEFAULT_ROUTING: dict[str, str] = {
    "erp": "erp-support@sopra-system.com",
    "evs": "evs-support@sopra-system.com",
    "hr": "hr-support@sopra-system.com",
    "it": "it-support@sopra-system.com",
    "verwaltung": "Stephan.Mueller@sopra-system.com",
    "nachricht": "Stephan.Mueller@sopra-system.com",
    "fibu": "Stephan.Mueller@sopra-system.com",
    "fibu_absence": "kuehn@eevolution.de",
}
```

- [ ] **Step 4: Tests laufen lassen (müssen passen)**

Run: `uv run python -m pytest tests/test_recipients.py -v`
Expected: PASS (alle). `merge_routing`/`resolve_recipient` sind generisch → keine weitere Änderung nötig; `/app/api/routing` akzeptiert den Key automatisch (validiert gegen `DEFAULT_ROUTING`).

- [ ] **Step 5: Commit**

```bash
git add app/tools/recipients.py tests/test_recipients.py
git commit -m "feat: fibu_absence-Routing-Default (kuehn@eevolution.de), editierbar"
```

---

### Task 3: Abwesenheits-Reroute in `create_ticket`

**Files:**
- Modify: `app/routers/tools_router.py:63-65` (`get_active_absence_safe` robust machen), `app/routers/tools_router.py:186-...` (`create_ticket`)
- Test: `tests/test_create_ticket_endpoint.py`

**Interfaces:**
- Consumes: `email_service.send_email_raw(..., cc=...)` (Task 1), `recipients.DEFAULT_ROUTING["fibu_absence"]` (Task 2), `get_active_absence_safe() -> dict | None`.
- Produces: bei `category=="fibu"` (case-insensitiv) UND aktiver Abwesenheit UND **ohne gezielte Personenbitte** (`recipient_override` nicht gültig gesetzt) → `recipient = routing["fibu_absence"]`, `cc = [<normaler fibu-Empfänger>]`, Header-Zeile „Hinweis". Bei gültiger Personenbitte gewinnt IMMER die Person (kein Reroute). Sonst unverändert, `cc=None`.

- [ ] **Step 1: `get_active_absence_safe` robust machen**

In `app/routers/tools_router.py` die bestehende Funktion ersetzen (fängt Fehler ab, damit die Ticket-Erstellung nie bricht):

```python
async def get_active_absence_safe() -> dict | None:
    from app.services.absence_service import get_active_absence
    try:
        return await get_active_absence()
    except Exception as exc:  # Graceful: Abwesenheit unbekannt -> wie "nicht abwesend"
        logger.warning("get_active_absence fehlgeschlagen: %s", exc)
        return None
```

- [ ] **Step 2: Failing Tests schreiben**

In `tests/test_create_ticket_endpoint.py` ergänzen (die Fixture mockt bereits `reserve`/`finalize`/`save_ticket`/`load_overrides`):

```python
def test_fibu_ticket_reroutes_to_kuehn_when_absent(client, monkeypatch):
    captured = {}

    async def _send(recipient, subject, body, **k):
        captured["recipient"] = recipient
        captured["kwargs"] = k
        return True, "m"
    monkeypatch.setattr(email_service, "send_email_raw", _send)

    async def _absent():
        return {"type": "urlaub", "start": "2026-07-01", "end": "2026-07-31"}
    monkeypatch.setattr(tools_router, "get_active_absence_safe", _absent)

    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "fibu", "summary": "Ungelöste FIBU-Frage", "caller_number": "+49"})
    assert r.status_code == 200
    assert captured["recipient"] == "kuehn@eevolution.de"
    assert captured["kwargs"]["cc"] == ["Stephan.Mueller@sopra-system.com"]


def test_fibu_ticket_normal_when_present(client, monkeypatch):
    captured = {}

    async def _send(recipient, subject, body, **k):
        captured["recipient"] = recipient
        captured["kwargs"] = k
        return True, "m"
    monkeypatch.setattr(email_service, "send_email_raw", _send)

    async def _present():
        return None
    monkeypatch.setattr(tools_router, "get_active_absence_safe", _present)

    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "fibu", "summary": "X"})
    assert r.status_code == 200
    assert captured["recipient"] == "Stephan.Mueller@sopra-system.com"
    assert captured["kwargs"].get("cc") is None


def test_non_fibu_ticket_never_reroutes_even_if_absent(client, monkeypatch):
    captured = {}

    async def _send(recipient, subject, body, **k):
        captured["recipient"] = recipient
        captured["kwargs"] = k
        return True, "m"
    monkeypatch.setattr(email_service, "send_email_raw", _send)

    async def _absent():
        return {"type": "urlaub", "start": "2026-07-01", "end": "2026-07-31"}
    monkeypatch.setattr(tools_router, "get_active_absence_safe", _absent)

    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "it", "summary": "X"})
    assert r.status_code == 200
    assert captured["recipient"] == "it-support@sopra-system.com"
    assert captured["kwargs"].get("cc") is None


def test_fibu_ticket_with_valid_override_goes_to_person_even_if_absent(client, monkeypatch):
    """Gezielte Personenbitte gewinnt immer — kein Kühn-Reroute trotz Abwesenheit."""
    captured = {}

    async def _send(recipient, subject, body, **k):
        captured["recipient"] = recipient
        captured["kwargs"] = k
        return True, "m"
    monkeypatch.setattr(email_service, "send_email_raw", _send)

    async def _absent():
        return {"type": "urlaub", "start": "2026-07-01", "end": "2026-07-31"}
    monkeypatch.setattr(tools_router, "get_active_absence_safe", _absent)

    r = client.post("/tools/create_ticket", headers=_h(), json={
        "category": "fibu", "summary": "X",
        "recipient_override": "Severin.Schindler@sopra-system.com"})
    assert r.status_code == 200
    assert captured["recipient"] == "Severin.Schindler@sopra-system.com"
    assert captured["kwargs"].get("cc") is None
```

- [ ] **Step 3: Tests laufen lassen (müssen failen)**

Run: `uv run python -m pytest tests/test_create_ticket_endpoint.py::test_fibu_ticket_reroutes_to_kuehn_when_absent -v`
Expected: FAIL (`recipient` == Stephan statt kuehn; `cc` fehlt in kwargs).

- [ ] **Step 4: Reroute-Logik im Handler ergänzen**

In `app/routers/tools_router.py`, im `create_ticket`-Handler, den bestehenden Empfänger-Auflösungs-Block ERSETZEN, sodass eine gültige gezielte Personenbitte als `directed` markiert wird:

```python
    routing = recipients.merge_routing(await routing_config.load_overrides())
    recipient = None
    directed = False
    if req.recipient_override:
        if recipients.validate_override(req.recipient_override, phonebook.all_emails()):
            recipient = req.recipient_override
            directed = True
        else:
            logger.warning("create_ticket: recipient_override nicht im Telefonbuch — ignoriert")
    if not recipient:
        recipient = recipients.resolve_recipient(req.category, routing) \
            or recipients.DEFAULT_ROUTING["verwaltung"]

    # FIBU-Eskalation während Abwesenheit von Stephan -> an Vertretung (Kühn),
    # Stephan im CC. NUR ohne gezielte Personenbitte (directed gewinnt immer);
    # nur für category "fibu"; nie blockierend.
    cc: list[str] | None = None
    if not directed and req.category.strip().lower() == "fibu" and await get_active_absence_safe():
        recipient = routing.get("fibu_absence") or recipients.DEFAULT_ROUTING["fibu_absence"]
        cc = [recipients.resolve_recipient("fibu", routing)
              or recipients.DEFAULT_ROUTING["fibu"]]
```

Hinweis: Falls im aktuellen Code der Empfänger-Block leicht abweicht, nur die zwei Ergänzungen übernehmen — `directed = False` initial und `directed = True` im gültigen `recipient_override`-Zweig — und die `if not directed and ...`-Bedingung.

Die `save_ticket`-Payload um `"cc"` ergänzen (Zeile `"recipient": recipient,`):

```python
        "recipient": recipient, "cc": cc,
```

Header-Zeile „Hinweis" ergänzen — direkt nach der `header_rows`-Definition (nach der `if req.caller_name`-Ergänzung, vor dem `header_rows += [...]`-Block):

```python
    if cc:
        header_rows.append(
            ("Hinweis", "FIBU-Eskalation während Abwesenheit von Stephan Müller"))
```

Den `send_email_raw`-Aufruf um `cc=cc` erweitern:

```python
    ok, message_id = await email_service.send_email_raw(
        recipient, f"Ticket {ticket_id}: {req.summary[:60]}", req.summary,
        ticket_ref=ticket_id, callback=req.callback_requested,
        header_rows=header_rows, cc=cc)
```

- [ ] **Step 5: Tests laufen lassen (müssen passen)**

Run: `uv run python -m pytest tests/test_create_ticket_endpoint.py -v`
Expected: PASS (alle, inkl. der vier neuen). Verhalten: gültige gezielte Personenbitte (`recipient_override`) gewinnt IMMER — kein Kühn-Reroute; der Reroute greift nur bei generischer FIBU-Eskalation.

- [ ] **Step 6: Volle Suite**

Run: `uv run python -m pytest -q`
Expected: PASS (alle grün).

- [ ] **Step 7: Commit**

```bash
git add app/routers/tools_router.py tests/test_create_ticket_endpoint.py
git commit -m "feat: FIBU-Ticket bei Abwesenheit an Kühn umleiten (CC Stephan)"
```

---

### Task 4: Deploy & Live-Verifikation

**Files:** keine (Deployment).

**Interfaces:** Consumes: Tasks 1–3 committed, Suite grün.

- [ ] **Step 1: Image bauen**

Run: `gcloud builds submit --tag gcr.io/boxwood-mantra-489408-c0/telefon-agent:latest --project boxwood-mantra-489408-c0 .`
Expected: `STATUS: SUCCESS`.

- [ ] **Step 2: Revision ausrollen**

Run: `gcloud run services update telefon-agent --project boxwood-mantra-489408-c0 --region europe-west3 --image gcr.io/boxwood-mantra-489408-c0/telefon-agent:latest`
Expected: `... has been deployed and is serving 100 percent of traffic.`

- [ ] **Step 3: Live-Verifikation**

Da eine Abwesenheit aktiv ist (Urlaub), `create_ticket` gegen die Live-URL testen (Token aus Secret) und prüfen, dass `recipient=kuehn` in den Logs steht:

```bash
TOKEN="$(gcloud secrets versions access latest --secret=tool-auth-token --project boxwood-mantra-489408-c0)"
curl -s -X POST "https://telefon-agent-1051648887841.europe-west3.run.app/tools/create_ticket" \
  -H "X-Tool-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"category":"fibu","summary":"Plan-Verifikation Abwesenheits-Reroute","caller_number":"+49"}'
```
Expected: `{"created":true,"ticket_id":"SOF-2026-...","email_sent":true}`; in den Cloud-Run-Logs „E-Mail via Resend gesendet an kuehn@eevolution.de". Postfach Kühn (+ CC Stephan) prüfen.

---

## Self-Review

- **Spec-Abdeckung:** To=kuehn/CC=stephan bei fibu+absent (Task 3) ✅; Ticket-Nr. in Betreff/Header (bestehend) ✅; unverändert bei Anwesenheit (Task 3, `test_..._normal_when_present`) ✅; CC-Fähigkeit (Task 1) ✅; Kühn-Adresse editierbar via config/routing (Task 2, greift in PWA-Plan) ✅.
- **Placeholder-Scan:** keine.
- **Typ-Konsistenz:** `cc: list[str] | None` durchgängig (`send_email_raw`, `_resend_send`, Handler); `get_active_absence_safe() -> dict | None` konsistent gemockt.
- **Edge case bewusst:** gültige gezielte Personenbitte (`recipient_override`) + fibu + absent → Person gewinnt, KEIN Reroute (Test `test_fibu_ticket_with_valid_override_goes_to_person_even_if_absent`). Nur generische FIBU-Eskalation wird umgeleitet.
