// API base URL. Empty string = same origin (FastAPI serves both portal and API).
// Override for separate deployments, e.g.: "https://api.yourdomain.com"
//
// When index.html is opened directly from disk (file://) there is no origin to
// resolve against, so fall back to the default local backend address.
window.APP_CONFIG = {
  API_BASE_URL: window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "",
};
