/* ════════════════════════════════════════════════════════════════════════
   Disha — service worker (PWA-lite)

   Goal: repeat visits load instantly and survive flaky connections by caching
   the static app shell (html / css / js / fonts / assets). API calls stay
   NETWORK-FIRST — we never serve stale recommendations and do not attempt any
   offline compute in this milestone.

   Strategy:
     - /api/*            → network-first (fall back to cache only if present).
     - navigations       → cached index.html first, refreshed in background.
     - same-origin GETs  → stale-while-revalidate (instant, self-healing).
     - cross-origin (e.g. Google Fonts) → cache opaque responses best-effort.
   Bump CACHE when shipping changes so old caches are purged on activate.
   ════════════════════════════════════════════════════════════════════════ */

const CACHE = "disha-shell-v2";

const APP_SHELL = [
  "/",
  "/index.html",
  "/css/style.css",
  "/js/config.js",
  "/js/i18n.js",
  "/js/api.js",
  "/js/app.js",
  "/assets/favicon.svg",
  "/manifest.json",
  "/sw.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function networkFirst(request) {
  return caches.open(CACHE).then((cache) =>
    fetch(request)
      .then((res) => {
        if (res && (res.status === 200 || res.type === "opaque")) {
          cache.put(request, res.clone());
        }
        return res;
      })
      .catch(() => cache.match(request))
  );
}

function staleWhileRevalidate(request) {
  return caches.open(CACHE).then((cache) =>
    cache.match(request).then((cached) => {
      const network = fetch(request)
        .then((res) => {
          if (res && (res.status === 200 || res.type === "opaque")) {
            cache.put(request, res.clone());
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
}

function isAppShellAsset(url) {
  if (url.origin !== self.location.origin) return false;
  const p = url.pathname;
  return (
    p === "/index.html" ||
    p.endsWith(".js") ||
    p.endsWith(".css") ||
    p === "/manifest.json"
  );
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // POST /api/recommend etc. → straight to network

  const url = new URL(req.url);

  // API: network-first, never block on cache, no offline compute.
  if (url.origin === self.location.origin && url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(req).catch(() => caches.match(req)));
    return;
  }

  // SPA navigations: network-first so deploys show up immediately.
  if (req.mode === "navigate") {
    event.respondWith(networkFirst(new Request("/index.html", { cache: "no-store" })));
    return;
  }

  // App shell assets: network-first (avoid serving stale JS/CSS after deploy).
  if (isAppShellAsset(url)) {
    event.respondWith(networkFirst(req));
    return;
  }

  // Everything else (fonts, images): stale-while-revalidate.
  event.respondWith(staleWhileRevalidate(req));
});
