/**
 * api.js — Client HTTP PhysioAI Lab
 * Version PRODUCTION : détecte automatiquement si on est sur GitHub Pages
 * et utilise l'URL du backend configurée en conséquence.
 *
 * Priorité de résolution de l'URL backend :
 *   1. localStorage (saisie manuelle par l'utilisateur)
 *   2. Variable globale PHYSIOAI_BACKEND_URL (injectée par CI/CD)
 *   3. Valeur par défaut (localhost pour développement local)
 */
"use strict";

// ── URL par défaut (remplacée automatiquement par le CI/CD) ──────────────────
// Le GitHub Actions remplace "http://localhost:8000" par l'URL Render/Railway
const DEFAULT_BACKEND_URL = "http://localhost:8000";

const API = {
  _base:    null,
  _timeout: 120000,  // 2 min (entraînement DL)

  /** Initialise l'URL du backend selon les priorités */
  init() {
    // 1. Préférence sauvegardée par l'utilisateur
    const saved = this._loadSaved();
    if (saved) { this._base = saved; return; }

    // 2. Variable globale injectée par CI (window.PHYSIOAI_BACKEND_URL)
    if (typeof window !== "undefined" && window.PHYSIOAI_BACKEND_URL) {
      this._base = window.PHYSIOAI_BACKEND_URL;
      return;
    }

    // 3. Défaut
    this._base = DEFAULT_BACKEND_URL;
  },

  setBase(url) {
    this._base = url.replace(/\/$/, "");
    try { localStorage.setItem("physioai_backend_url", this._base); } catch {}
  },

  _loadSaved() {
    try { return localStorage.getItem("physioai_backend_url") || null; }
    catch { return null; }
  },

  getBase() { return this._base; },

  // ── Transport ──────────────────────────────────────────────────────────────
  async _fetch(path, method = "GET", body = null, params = null) {
    if (!this._base) this.init();

    let url = `${this._base}${path}`;
    if (params) url += `?${new URLSearchParams(params)}`;

    const ctrl    = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), this._timeout);

    try {
      const resp = await fetch(url, {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        body:    body ? JSON.stringify(body) : undefined,
        signal:  ctrl.signal,
        // Nécessaire pour les requêtes cross-origin depuis Excel Online
        credentials: "omit",
        mode:        "cors",
      });
      clearTimeout(timeout);

      const data = await resp.json().catch(() => ({ error: resp.statusText }));
      if (!resp.ok) throw new Error(data?.detail || data?.error || `HTTP ${resp.status}`);
      return data;
    } catch (e) {
      clearTimeout(timeout);
      if (e.name === "AbortError") throw new Error(`Timeout (${this._timeout/1000}s) — Backend non joignable.`);
      throw e;
    }
  },

  // ── Endpoints ─────────────────────────────────────────────────────────────
  async health()       { return this._fetch("/health"); },

  async stats(data)    { return this._fetch("/analyze/stats",       "POST", { data }); },
  async corr(data)     { return this._fetch("/analyze/correlation",  "POST", { data }); },
  async recommend(data, target, domain = "auto") {
    return this._fetch("/analyze/recommend", "POST", { data, target, domain, include_recommendation: true });
  },
  async fullAnalysis(data, target, domain = "auto") {
    return this._fetch("/analyze/full", "POST", { data, target, domain, include_recommendation: true });
  },

  async regression(x, y, type, degree = 2, alpha = 1.0) {
    return this._fetch("/model/regression", "POST", { x, y, type, degree, alpha });
  },
  async physics(payload)  { return this._fetch("/model/physics",   "POST", payload); },
  async simulate(model, params, t_start, t_end, n_points, compare_with = null) {
    return this._fetch("/simulate/", "POST", { model, params, t_start, t_end, n_points, compare_with });
  },
  async trainML(payload)  { return this._fetch("/train_ai/ml",     "POST", payload); },
  async trainDL(payload)  { return this._fetch("/train_ai/dl",     "POST", payload); },
  async predict(payload)  { return this._fetch("/predict/",        "POST", payload); },
  async calibrate(payload){ return this._fetch("/optimize/calibrate","POST", payload); },
  async autoOptimize(x_data, y_data, model = "kinetics", method = "curve_fit") {
    return this._fetch("/optimize/auto", "POST", { x_data, y_data }, { model, method });
  },
};

// Initialisation automatique au chargement
API.init();
window.API = API;
