/**
 * PhysioAI Lab — Module API
 * Communication REST entre le frontend Excel et le backend FastAPI
 */

const API_BASE = "http://localhost:8000/api/v1";
const TIMEOUT_MS = 60000; // 60s pour les opérations DL

class PhysioAPI {
  constructor(baseUrl = API_BASE) {
    this.baseUrl = baseUrl;
    this.isOnline = false;
  }

  // ─── Méthode générique fetch avec timeout ───────────────────────────────

  async _request(endpoint, method = "GET", body = null) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const options = {
      method,
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    };
    if (body) options.body = JSON.stringify(body);

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, options);
      clearTimeout(timeoutId);

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(err.detail || `Erreur HTTP ${response.status}`);
      }
      const data = await response.json();
      return data.data || data;
    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === "AbortError") throw new Error("Timeout: opération trop longue");
      throw err;
    }
  }

  // ─── Vérification de connexion ──────────────────────────────────────────

  async checkHealth() {
    try {
      const resp = await fetch(`${this.baseUrl.replace("/api/v1", "")}/health`, { signal: AbortSignal.timeout(3000) });
      this.isOnline = resp.ok;
      return resp.ok;
    } catch {
      this.isOnline = false;
      return false;
    }
  }

  // ─── Endpoints ─────────────────────────────────────────────────────────

  async analyze(x, y, xLabel = "x", yLabel = "y") {
    return this._request("/analyze", "POST", { x, y, x_label: xLabel, y_label: yLabel });
  }

  async fitModel(x, y, modelType, degree = 2, alpha = 1.0) {
    return this._request("/model", "POST", { x, y, model_type: modelType, degree, alpha });
  }

  async simulate(modelType, parameters, tStart, tEnd, nPoints, expX = null, expY = null, calibrate = false) {
    return this._request("/simulate", "POST", {
      model_type: modelType,
      parameters,
      t_start: tStart,
      t_end: tEnd,
      n_points: nPoints,
      experimental_x: expX,
      experimental_y: expY,
      calibrate,
    });
  }

  async trainAI(x, y, modelType, hyperparams = {}, epochs = 150, physicalModel = null, physicalParams = null) {
    return this._request("/train_ai", "POST", {
      x,
      y,
      model_type: modelType,
      hyperparams,
      epochs,
      physical_model: physicalModel,
      physical_params: physicalParams,
    });
  }

  async predict(modelId, xNew) {
    return this._request("/predict", "POST", { model_id: modelId, x_new: xNew });
  }

  async getAdvice(x, y) {
    return this._request("/advisor", "POST", { x, y });
  }
}

// Instance globale
window.physioAPI = new PhysioAPI();
