"use strict";

// Empty string means same-origin (unified Render/Docker deploy). Do not use ||
// here — "" is valid and must not fall back to localhost.
const configured = window.APP_CONFIG?.API_BASE_URL;
const API_BASE = (
  configured !== undefined ? configured : "http://127.0.0.1:8000"
).replace(/\/+$/, "");

async function apiRequest(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error(
      "Could not reach the recommendation service. Make sure the backend is running and reachable.",
    );
  }

  if (!res.ok) {
    let detail = null;
    try {
      const body = await res.json();
      detail = Array.isArray(body.detail)
        ? body.detail.map((d) => d.msg).join("; ")
        : body.detail;
    } catch {
      // non-JSON error body
    }
    throw new Error(detail || `Request failed with status ${res.status}.`);
  }

  return res.json();
}

function fetchMeta() {
  return apiRequest("/api/meta");
}

function fetchRecommendations(payload) {
  return apiRequest("/api/recommend", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
