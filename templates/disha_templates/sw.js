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

const CACHE = "disha-shell-v10";

// Resolve paths relative to the service worker's actual location
// so it works both at root (/) and in sub-apps (/learning_games/)
const basePath = self.location.pathname.replace(/\/sw\.js$/, '') || '';

const APP_SHELL = [
  `${basePath}/`,
  `${basePath}/index.html`,
  `${basePath}/jee.html`,
  `${basePath}/kcet/index.html`,
  `${basePath}/comedk/index.html`,
  `${basePath}/comedk/js/app.js`,
  `${basePath}/stats`,
  `${basePath}/css/style.css`,
  `${basePath}/js/landing.js`,
  `${basePath}/js/config.js`,
  `${basePath}/js/i18n.js`,
  `${basePath}/js/api.js`,
  `${basePath}/js/app.js`,
  `${basePath}/assets/favicon.svg`,
  `${basePath}/manifest.json`,
  `${basePath}/sw.js`,
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
    p === `${basePath}/index.html` ||
    p === `${basePath}/jee.html` ||
    p === `${basePath}/kcet/index.html` ||
    p === `${basePath}/comedk/index.html` ||
    p === `${basePath}/stats` ||
    p.endsWith(".js") ||
    p.endsWith(".css") ||
    p === `${basePath}/manifest.json`
  );
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // POST /api/recommend etc. → straight to network

  const url = new URL(req.url);

  // API: network-first, never block on cache, no offline compute.
  if (url.origin === self.location.origin && url.pathname.startsWith(`${basePath}/api/`)) {
    event.respondWith(fetch(req).catch(() => caches.match(req)));
    return;
  }

  // SPA navigations: network-first so deploys show up immediately.
  if (req.mode === "navigate") {
    if (url.pathname === `${basePath}/stats` || url.pathname.endsWith("/stats")) {
      event.respondWith(networkFirst(new Request(`${basePath}/stats`, { cache: "no-store" })));
    } else if (url.pathname.includes("/exam/jee")) {
      event.respondWith(networkFirst(new Request(`${basePath}/jee.html`, { cache: "no-store" })));
    } else if (url.pathname.includes("/exam/kcet")) {
      event.respondWith(networkFirst(new Request(`${basePath}/kcet/index.html`, { cache: "no-store" })));
    } else if (url.pathname.includes("/exam/comedk")) {
      event.respondWith(networkFirst(new Request(`${basePath}/comedk/index.html`, { cache: "no-store" })));
    } else {
      event.respondWith(networkFirst(new Request(`${basePath}/index.html`, { cache: "no-store" })));
    }
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
