// Disha — runtime configuration.
//
// Auto-detects the URL prefix under which the app is deployed so that API
// calls resolve correctly in both standalone mode (root "/") and as a sub-app
// on the UTMT portal (e.g. "/learning_games").
//
// Detection uses the URL of this very script:
//   Standalone:  /js/config.js           → API_BASE_URL = ""
//   UTMT portal: /learning_games/js/config.js → API_BASE_URL = "/learning_games"
//
// When opened from the filesystem (file://) falls back to localhost.
(function () {
  if (window.location.protocol === "file:") {
    window.APP_CONFIG = { API_BASE_URL: "http://127.0.0.1:8000" };
    return;
  }

  var prefix = "";
  var scriptEl = document.currentScript;
  if (scriptEl && scriptEl.src) {
    try {
      var pathname = new URL(scriptEl.src).pathname;          // e.g. "/learning_games/js/config.js"
      prefix = pathname.replace(/\/js\/config\.js$/i, "");    // e.g. "/learning_games"
    } catch (_) { /* graceful fallback to empty prefix */ }
  }

  window.APP_CONFIG = { API_BASE_URL: prefix };
})();
