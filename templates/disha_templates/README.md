# Frontend — `templates/disha_templates/`

> Docs-sync reminder: if you add/remove/rename a file in this directory, or change what's shared vs. per-exam, update this file **and** the root [README.md](../../README.md)'s Architecture/Directory-layout sections in the same change. See [CONTRIBUTING.md](../../CONTRIBUTING.md).

Static **HTML + CSS + vanilla JavaScript** — no framework, no build step, no `npm install`. Everything under this directory is served directly by the FastAPI backend (`main.py`'s static-file catch-all, or the equivalent `StaticFiles(html=True)` mount inside a host portal) — it is not deployed or built separately from the backend in practice, despite being written to fetch its data over `fetch()` calls rather than server-side templating.

There are currently **three separate exam frontends** here (JEE, COMEDK, KCET) plus one shared landing page. They are not variations of one configurable app — each is its own HTML shell + `app.js`, built by copying and adapting an earlier one. See the root README's [Architecture overview](../../README.md#architecture-overview) for why, and [Adding a new exam](../../README.md#adding-a-new-exam) if you're about to add a fourth.

## Layout

```text
templates/disha_templates/
├── index.html            # Landing page: exam picker. Loads ONLY css/style.css + js/landing.js.
├── jee.html               # JEE SPA shell. Loads js/config.js, js/i18n.js, js/api.js, js/app.js.
├── stats.html              # JEE insights dashboard (fetches /api/stats).
├── comedk/
│   ├── index.html         # COMEDK SPA shell. Loads js/config.js, js/api.js (NOT js/i18n.js), comedk/js/app.js.
│   ├── js/app.js           # All COMEDK app logic — views, state, rendering, submission. ~1800 lines.
│   └── stats.html          # COMEDK insights dashboard (fetches /api/comedk/stats).
├── kcet/
│   ├── index.html         # KCET SPA shell.
│   ├── js/app.js           # All KCET app logic. Self-described as "standalone SPA, NO shared JEE code".
│   └── stats.html          # KCET insights dashboard (fetches /api/kcet/stats).
├── css/
│   └── style.css           # Single shared design system — every exam's HTML reuses this file as-is. No per-exam stylesheet exists.
├── js/
│   ├── config.js           # SHARED. Auto-detects API_BASE_URL / mount prefix from its own <script src>. Used by jee.html, comedk/index.html, stats.html.
│   ├── api.js               # SHARED. Generic fetch wrapper + error message normalization. Used by jee.html and comedk/index.html.
│   ├── i18n.js               # JEE-ONLY. en/hi/gu/kn string dictionary + t() + applyStaticI18n(). Not loaded by comedk/index.html or kcet/index.html.
│   ├── landing.js            # Landing-page-only. Config-driven EXAMS array → renders the picker cards on index.html.
│   └── app.js                 # JEE-ONLY. JEE's ~3100-line SPA logic (views, guided flow, live panel, rank ruler, Choice List, share/print).
├── manifest.json          # SHARED PWA manifest — but its text (title, description) is JEE-flavored and hasn't been updated for the multi-exam app. See caveat below.
├── sw.js                   # SHARED service worker — precaches all three exams' shells and routes navigation by pathname. Has a known bug — see caveat below.
└── assets/favicon.svg      # Shared icon.
```

## What's actually shared vs. per-exam (verified, not assumed)

| File | Shared? | Who loads it |
|---|---|---|
| `css/style.css` | ✅ Fully shared | `index.html`, `jee.html`, `comedk/index.html`, `kcet/index.html`, all three `stats.html` |
| `js/config.js` | ✅ Fully shared | `jee.html`, `comedk/index.html`, `stats.html` (and presumably `kcet/index.html`) |
| `js/api.js` | ✅ Fully shared | `jee.html`, `comedk/index.html` |
| `js/i18n.js` | ❌ JEE-only | `jee.html` only — COMEDK and KCET are English-only, with no equivalent i18n layer |
| `js/app.js` | ❌ JEE-only | `jee.html` only — COMEDK has `comedk/js/app.js`, KCET has `kcet/js/app.js`, each a separate, independent file |
| `js/landing.js` | Landing-only | `index.html` only |
| `manifest.json` | Shared file, stale content | All three exam shells reference it, but its copy still describes a JEE-only app |
| `sw.js` | Shared, has a real bug | All three exam shells register it |

## Configuration

The backend API base URL is **not** hardcoded anywhere and needs no manual editing per environment. `js/config.js` inspects the URL its own `<script>` tag was loaded from and derives the mount prefix from it:

```js
// Standalone (main.py, mounted at "/"):        prefix = ""
// Inside a host portal (mounted at a prefix):  prefix = "/learning_games" (or whatever the host chose)
// Opened directly from the filesystem (file://): falls back to "http://127.0.0.1:8000"
```

This is what lets the exact same static files work unmodified whether `main.py` serves them at root or a host portal mounts them under a prefix — see [DISHA_INTEGRATION_QA.md](../../DISHA_INTEGRATION_QA.md).

## Running locally

There's no separate frontend dev server. Run the FastAPI app from the repo root (see the main [README.md](../../README.md#setup)):

```bash
uvicorn main:app --reload --port 8000
```

and the pages in this directory are served directly — `http://127.0.0.1:8000/` (landing), `/exam/jee`, `/exam/comedk`, `/exam/kcet`, `/stats`, `/exam/comedk/stats`, `/exam/kcet/stats`.

## Features (verified against the current code)

- **Language switching** — JEE only. A `en/hi/gu/kn` selector persisted to `localStorage`. Static UI strings live in `js/i18n.js`'s dictionary, applied via `data-i18n*` attributes; backend-generated text (guidance, notes, per-card reasons) is requested in the chosen language via the `lang` field on `/api/recommend`'s request body. COMEDK's backend accepts a `lang` field too, but `comedk/js/app.js` always sends `"en"` — there's no selector in its UI.
- **Share / copy link** (JEE) — the results view has a WhatsApp-style Share button and a Copy-link button; the link encodes the student's inputs as a query string and re-runs the request automatically on load (stateless — no backend session).
- **Print / Save PDF** (JEE and COMEDK) — `window.print()` with a `@media print` stylesheet.
- **Choice List / bookmarking with CSV/PDF export** — present in both JEE's and COMEDK's `app.js` (COMEDK's per its port-and-adapt history).
- **PWA shell** — `manifest.json` + `sw.js` cache the app shell and serve `/api/*` GET requests network-first with a cache fallback. Non-GET requests (e.g. the recommend POST calls) bypass the service worker entirely.
- A small inline `<script>` at the top of `index.html`, `jee.html`, and `comedk/index.html` unregisters any existing service worker and clears Cache Storage once per browser session (gated by a `sessionStorage` flag — `sw_cleared_v7` on the JEE pages, `sw_cleared_v8` on `comedk/index.html`, bumped independently when each was last updated) so that shipped frontend changes aren't masked by a stale cached shell.

## Known issues in this directory (verified, not hypothetical)

- **`manifest.json`'s copy is stale.** Its `name`/`description` still describe a JEE-only app ("Disha — Find your direction after JEE", mentions only IITs/NITs/IIITs/GFTIs) even though the same manifest is now referenced by the COMEDK and KCET pages too.
- **`sw.js` has a broken KCET route.** Its `APP_SHELL` precache list and navigation-routing logic both reference `${basePath}/kcet.html` — a file that does not exist. The real KCET shell is at `kcet/index.html`, served via the backend's `/exam/kcet` route. Confirmed: `GET /kcet.html` → `404`, `GET /exam/kcet` → `200`. This only bites once the service worker is actively controlling navigation (first load bypasses it), but it means the KCET page can break offline/on repeat visits even though the very first visit works. See [docs/API.md](../../docs/API.md#page-routes-html-not-json) for the reproduction.
- **No stylesheet or i18n fork exists for any exam** — if you're tempted to add exam-specific CSS overrides or translated strings, there is currently no established pattern for either; you'd be creating the first one.

If you fix either bug above, remove the corresponding bullet from this list in the same change — see [CONTRIBUTING.md](../../CONTRIBUTING.md).
