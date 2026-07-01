# PWA Zwei-Tab-Umbau + Service-Worker-Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die bestehende `/app/`-PWA bekommt zwei Reiter — „Abwesenheit" und „Team-Adressen" — bei einer Google-OAuth-Session; und der Service Worker wird so gefixt, dass Updates die installierte PWA tatsächlich erreichen.

**Architecture:** Reines Frontend (`app/static/index.html`, `app/static/sw.js`). Beide Reiter nutzen dieselbe Session und die bestehenden Endpoints (`/app/absence`, `/app/api/routing`) — keine Backend-Änderung. Der SW wechselt von „cache-first für alles" auf „network-first für die App-Shell" + Versions-Bump, damit die stale gecachte Shell abgelöst wird.

**Tech Stack:** Vanilla HTML/CSS/JS, PWA Service Worker. Kein JS-Testframework im Repo → Verifikation manuell im Browser.

## Global Constraints

- `index.html` wird serverseitig bei jedem Request frisch von Platte gelesen (`app_router.py:149-154`) — es gibt KEINEN Server-Cache; einziger Update-Blocker war der Service Worker.
- Routing-Endpoint: `GET/PUT /app/api/routing` (auth via Session-Cookie), akzeptiert nur Keys aus `recipients.DEFAULT_ROUTING`.
- Auth unverändert (Google OAuth, nur `stn.mueller@gmail.com`).
- Live-URL: `https://telefon-agent-1051648887841.europe-west3.run.app/app/`.

---

### Task 1: Service-Worker-Fix (Update-Propagation)

**Files:**
- Modify: `app/static/sw.js` (komplett ersetzen)

**Interfaces:**
- Produces: SW mit `CACHE="sofia-v2"`, App-Shell (`/app/`) network-first, API-Calls (`/app/absence`, `/app/auth`, `/app/api/`) nie gecacht.

- [ ] **Step 1: `sw.js` komplett ersetzen**

`app/static/sw.js` vollständig durch diesen Inhalt ersetzen:

```js
// Sofia PWA Service Worker
const CACHE = "sofia-v2";
const SHELL = "/app/";

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.add(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const url = e.request.url;
  // API-Calls immer live (nie cachen)
  if (url.includes("/app/absence") || url.includes("/app/auth") || url.includes("/app/api/")) {
    return;
  }
  // App-Shell: network-first (Updates kommen sofort an), Cache nur Offline-Fallback
  if (e.request.mode === "navigate" || url.endsWith("/app/") || url.endsWith("/app")) {
    e.respondWith(
      fetch(e.request)
        .then(resp => {
          const copy = resp.clone();
          caches.open(CACHE).then(c => c.put(SHELL, copy));
          return resp;
        })
        .catch(() => caches.match(SHELL))
    );
    return;
  }
  // Übrige statische Assets: cache-first
  e.respondWith(caches.match(e.request).then(cached => cached || fetch(e.request)));
});
```

- [ ] **Step 2: Syntax prüfen**

Run: `node --check app/static/sw.js`
Expected: keine Ausgabe (Exit 0). Falls `node` fehlt: überspringen, in Step-Verifikation von Task 3 fällt ein Syntaxfehler ohnehin auf.

- [ ] **Step 3: Commit**

```bash
git add app/static/sw.js
git commit -m "fix: PWA Service Worker network-first + Cache-Bump (v2)"
```

---

### Task 2: Zwei-Tab-Layout in `index.html`

**Files:**
- Modify: `app/static/index.html` (CSS-Block, Body-Struktur ~357-410, JS ~426-441 und ~605-613)

**Interfaces:**
- Consumes: bestehende Funktionen `loadAbsences()`, `loadRouting()`.
- Produces: `showTab(tab: string)`; zwei `.tab-view`-Container `#tab-abwesenheit` / `#tab-adressen`; Routing-Labels via `ROUTING_LABELS`.

- [ ] **Step 1: CSS für Tabbar ergänzen**

Im `<style>`-Block von `app/static/index.html` (vor `</style>`) einfügen:

```css
    .tabbar { display: flex; gap: 8px; margin: 0 0 16px; }
    .tab-btn {
      flex: 1; padding: 12px; border: none; border-radius: 10px;
      background: #eceff3; color: #555; font-size: 15px; font-weight: 600; cursor: pointer;
    }
    .tab-btn.active { background: #003366; color: #fff; }
    .tab-view[hidden] { display: none; }
```

- [ ] **Step 2: Tabbar + Tab-Container in die Body-Struktur einbauen**

In `app/static/index.html` zwischen dem schließenden `</div>` des `.header` (Zeile 357) und dem `<!-- Neue Abwesenheit -->`-Kommentar (Zeile 359) einfügen:

```html
  <div class="tabbar">
    <button class="tab-btn active" data-tab="abwesenheit" onclick="showTab('abwesenheit')">Abwesenheit</button>
    <button class="tab-btn" data-tab="adressen" onclick="showTab('adressen')">Team-Adressen</button>
  </div>

  <div id="tab-abwesenheit" class="tab-view">
```

Direkt VOR der `<!-- Empfänger-Settings -->`-Card (Zeile 403) den Abwesenheits-Tab schließen und den Adressen-Tab öffnen:

```html
  </div><!-- /tab-abwesenheit -->

  <div id="tab-adressen" class="tab-view" hidden>
```

Direkt NACH der Empfänger-Card (nach `</div>` in Zeile 410, vor dem `</div>` das `#main-screen` schließt, Zeile 412) den Adressen-Tab schließen:

```html
  </div><!-- /tab-adressen -->
```

Ergebnis: `#tab-abwesenheit` umschließt die Cards „Neue Abwesenheit" + „Eingetragene Abwesenheiten"; `#tab-adressen` umschließt die „Empfänger"-Card.

- [ ] **Step 3: `showTab`-Funktion ergänzen**

Im `<script>` von `app/static/index.html`, direkt nach der `init()`-Funktion (nach Zeile 441) einfügen:

```javascript
function showTab(tab) {
  document.querySelectorAll(".tab-view").forEach(v => { v.hidden = (v.id !== "tab-" + tab); });
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
}
```

- [ ] **Step 4: Freundliche Routing-Labels (inkl. `fibu_absence`)**

In `app/static/index.html`, `loadRouting()` (Zeile 599-613) anpassen. Direkt vor `async function loadRouting()` die Label-Map einfügen:

```javascript
const ROUTING_LABELS = {
  erp: "ERP-Support", evs: "EVS-Support", hr: "HR-Support", it: "IT-Support",
  verwaltung: "Verwaltung / Verträge", nachricht: "Nachricht (Sofia)",
  fibu: "FIBU", fibu_absence: "FIBU-Eskalation bei Abwesenheit",
};
```

Und in der `forEach`-Schleife die Label-Zeile ersetzen:

```javascript
    row.innerHTML =
      `<label>${ROUTING_LABELS[cat] || cat}</label>` +
      `<input type="email" data-cat="${cat}" value="${routing[cat]}">`;
```

- [ ] **Step 5: Manuell verifizieren (Inkognito, um SW-Cache zu umgehen)**

Lokal ist kein Server nötig — nach dem Deploy (Task 3) prüfen. Falls lokal getestet wird: Datei im Browser öffnen ist wegen der `/app/`-Fetches nicht sinnvoll → Verifikation erfolgt in Task 3.

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html
git commit -m "feat: PWA Zwei-Tab-Layout (Abwesenheit / Team-Adressen) + Routing-Labels"
```

---

### Task 3: Deploy & Update-Propagation verifizieren

**Files:** keine (Deployment).

**Interfaces:** Consumes: Task 1 + 2 committed.

- [ ] **Step 1: Image bauen**

Run: `gcloud builds submit --tag gcr.io/boxwood-mantra-489408-c0/telefon-agent:latest --project boxwood-mantra-489408-c0 .`
Expected: `STATUS: SUCCESS`.

- [ ] **Step 2: Revision ausrollen**

Run: `gcloud run services update telefon-agent --project boxwood-mantra-489408-c0 --region europe-west3 --image gcr.io/boxwood-mantra-489408-c0/telefon-agent:latest`
Expected: `... serving 100 percent of traffic.`

- [ ] **Step 3: Frischer Client (Inkognito) — Tabs vorhanden**

`https://telefon-agent-1051648887841.europe-west3.run.app/app/` im **Inkognito-Fenster** öffnen, einloggen.
Expected: Oben zwei Reiter „Abwesenheit" / „Team-Adressen"; Umschalten zeigt die jeweiligen Cards; unter „Team-Adressen" u.a. das Feld „FIBU-Eskalation bei Abwesenheit" (= `kuehn@eevolution.de`), Speichern liefert „Gespeichert ✓".

- [ ] **Step 4: Installierte PWA — Update kommt an**

Auf dem iPhone die installierte Sofia-PWA öffnen. Der neue `sw.js` (v2) wird beim Start im Hintergrund erkannt, installiert und aktiviert (`skipWaiting`+`clients.claim`); die alte `sofia-v1`-Shell wird gelöscht. Ggf. **einmal die App schließen und neu öffnen** (oder Seite neu laden).
Expected: nach spätestens einem Neustart sind die zwei Tabs sichtbar. (Grund: v2-SW liefert die Shell jetzt network-first.)

- [ ] **Step 5: Fallback dokumentieren, falls die alte PWA hartnäckig cached**

Sollte die installierte PWA nach zwei Neustarts noch die alte Ansicht zeigen: PWA vom Homescreen entfernen und neu „Zum Home-Bildschirm hinzufügen". (Einmalig; künftige Updates propagieren dank network-first automatisch.)

---

## Self-Review

- **Spec-Abdeckung:** ein Login/eine App/zwei Reiter (Task 2) ✅; „Team-Adressen" spricht `/api/routing` als Formular an (bestehende Card, jetzt eigener Tab) ✅; SW-Fix, damit Updates ankommen (Task 1, verifiziert in Task 3 Step 4) ✅; `fibu_absence`-Feld sichtbar/editierbar (Task 2 Step 4) ✅.
- **Placeholder-Scan:** keine — sw.js vollständig, CSS/HTML/JS-Snippets vollständig.
- **Typ-Konsistenz:** `showTab(tab)` matcht `data-tab`/`id="tab-..."`; `ROUTING_LABELS`-Keys matchen `DEFAULT_ROUTING`-Keys inkl. `fibu_absence`.
- **Abhängigkeit:** `fibu_absence`-Feld erscheint nur, wenn Backend-Plan Task 2 (Default in `DEFAULT_ROUTING`) deployt ist — sonst zeigt die Adressen-Card die übrigen Kategorien korrekt und `fibu_absence` fehlt schlicht. Reihenfolge: Backend-Plan zuerst.
