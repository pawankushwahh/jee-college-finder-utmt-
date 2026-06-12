# Frontend — JEE College Recommender

Static **HTML + CSS + vanilla JavaScript** portal for the JEE College Recommender.
Newton School–inspired layout with a centered predictor form, light theme, and
marketing sections (testimonials, features, FAQ). No build step required.

The frontend is fully decoupled from the backend and talks to it exclusively over
the JSON API in the sibling [`backend/`](../backend) project.

## Configuration

Set the backend API URL in `js/config.js`:

```js
window.APP_CONFIG = {
  API_BASE_URL: "http://127.0.0.1:8000",
};
```

For production, point `API_BASE_URL` at your deployed API origin and ensure the
backend's `CORS_ORIGINS` includes your frontend URL.

## Running locally

1. Start the backend (see [`backend/README.md`](../backend/README.md)).
2. Serve this folder with any static file server:

```bash
cd frontend
python3 -m http.server 5173
```

Then open <http://localhost:5173>.

## Deployment

Deploy the entire `frontend/` folder to any static host (nginx, S3 + CloudFront,
Netlify, GitHub Pages, etc.). No build step required.

## Layout

```
index.html           page structure
css/style.css        design system + component styles
js/
  config.js          API base URL (edit per environment)
  api.js             fetch wrapper + error normalization
  app.js             form, validation, rendering, filters
assets/favicon.svg
```
