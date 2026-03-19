/**
 * config.js — Configuration de l'URL de l'API
 * =============================================
 * Détecte automatiquement l'environnement :
 *   - Développement local  → http://localhost:8000
 *   - Production (Render)  → URL définie dans window.PHYSIOAI_API_URL
 *
 * Pour déployer sur Render, remplacer la valeur ci-dessous
 * par l'URL réelle de votre service backend Render :
 *   window.PHYSIOAI_API_URL = "https://physioai-lab-api.onrender.com";
 */

(function () {
  // ── Modifier cette ligne avec votre URL Render backend ──────────────────────
  const RENDER_API_URL = "https://physioai-backend-6iqm.onrender.com";
  // ────────────────────────────────────────────────────────────────────────────

  const isLocal =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1";

  window.PHYSIOAI_CONFIG = {
    // URL de base de l'API — sans /api/v1
    API_BASE_URL: isLocal ? "http://localhost:8000" : RENDER_API_URL,
    VERSION: "1.0.0",
    ENV: isLocal ? "development" : "production",
  };

  console.log(
    `[PhysioAI] Mode: ${window.PHYSIOAI_CONFIG.ENV} | API: ${window.PHYSIOAI_CONFIG.API_BASE_URL}`
  );
})();
