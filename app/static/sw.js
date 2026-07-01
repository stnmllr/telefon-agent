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
