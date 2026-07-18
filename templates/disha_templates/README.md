# Frontend — JEE College Recommender

Static **HTML + CSS + vanilla JavaScript** portal for the JEE College Recommender.
Newton School–inspired layout with a centered predictor form, light theme, and
marketing sections (testimonials, features, FAQ). No build step required.

The frontend is served directly as static files by the FastAPI backend, but it is fully decoupled structurally, communicating via API.

## Configuration

The backend API URL is configured in `js/config.js`. It dynamically auto-detects the mounting prefix (e.g. `/learning_games`) based on the URL from which the script is loaded:

```js
// Standalone: prefix is "" (relative to root)
// Sub-app: prefix is "/learning_games" (relative to mount path)
// Local filesystem: falls back to "http://127.0.0.1:8000"
```

No manual editing of `API_BASE_URL` is required for different deployment environments.

## Running locally

Refer to the main `README.md` in the root folder to run the unified FastAPI application using:
```bash
uvicorn main:app --reload --port 8000
```

## Deployment

Deploy the entire `frontend/` folder to any static host (nginx, S3 + CloudFront,
Netlify, GitHub Pages, etc.). No build step required.

## Features

- **Hindi / English toggle** — a persistent `EN / हिं` button in the header
  (saved to `localStorage`). All static UI strings live in
  [`js/i18n.js`](js/i18n.js) as one `en{} / hi{}` dictionary, applied to markup
  via `data-i18n*` attributes; backend-generated text is requested in the
  current language via `payload.lang`.
- **Share & shareable links** — the results view has a WhatsApp **Share** and a
  **Copy link** button. The link encodes the student's inputs as a query string
  (`?m=&a=&g=&s=&goal=&cat=&lang=`); opening it pre-fills the form and re-runs
  the request automatically (stateless, no backend session).
- **Print / Save PDF** — `window.print()` with a dedicated `@media print`
  stylesheet that hides chrome and lays out the profile + full grouped list +
  disclaimer on a clean, ink-friendly sheet.
- **PWA-lite** — non-blocking web fonts (system-font fallback for instant first
  paint), a [`manifest.json`](manifest.json), and a [`sw.js`](sw.js) service
  worker that caches the app shell (network-first for `/api/*`).

## Layout

```
index.html           page structure (data-i18n* attributes)
manifest.json        PWA manifest (install metadata)
sw.js                service worker (app-shell cache, network-first API)
css/style.css        design system + component styles + @media print
js/
  config.js          API base URL (edit per environment)
  i18n.js            en{} / hi{} string dictionary + t() + applyStaticI18n()
  api.js             fetch wrapper + error normalization
  app.js             form, validation, rendering, filters, share, language
assets/favicon.svg
```
