/**
 * config.js — Configuration URL API PhysioAI Lab
 * ================================================
 * Détecte automatiquement l'environnement :
 *   - localhost / 127.0.0.1 → développement local
 *   - GitHub Pages          → backend Render
 *
 * ⚠️  SEULE LIGNE À MODIFIER APRÈS DÉPLOIEMENT :
 *       const RENDER_API_URL = "https://VOTRE-BACKEND.onrender.com";
 */

(function () {
  // ── ✏️ Mettre ici l'URL exacte de votre backend Render ───────────────────
  const RENDER_API_URL = "https://physioai-backend-6iqm.onrender.com";
  // ─────────────────────────────────────────────────────────────────────────

  const hostname = window.location.hostname;
  const isLocal  = hostname === "localhost" || hostname === "127.0.0.1";

  window.PHYSIOAI_CONFIG = {
    API_BASE_URL: isLocal ? "http://localhost:8000" : RENDER_API_URL,
    VERSION:      "2.0.0",
    ENV:          isLocal ? "development" : "production",
  };

  console.log(
    `%c[PhysioAI Lab v${window.PHYSIOAI_CONFIG.VERSION}]`,
    "color:#ffb700;font-weight:bold",
    `${window.PHYSIOAI_CONFIG.ENV} | API → ${window.PHYSIOAI_CONFIG.API_BASE_URL}`
  );
})();