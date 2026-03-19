/**
 * PhysioAI Lab — Office Add-in JavaScript
 * =========================================
 * Gère toute la logique frontend :
 *   - Lecture de données depuis Excel (Office.js)
 *   - Appels API REST vers le backend FastAPI
 *   - Rendu des graphiques Chart.js
 *   - Affichage des résultats
 */

// ── Configuration API ──────────────────────────────────────────────────────
// Modifier RENDER_API_URL avec votre URL backend Render après déploiement
const RENDER_API_URL = "https://physioai-lab-api.onrender.com";
const _isLocal = location.hostname === "localhost" || location.hostname === "127.0.0.1";
const API_BASE = (_isLocal ? "http://localhost:8000" : RENDER_API_URL) + "/api/v1";

// ── État global ──────────────────────────────────────────────────────────────
let state = {
  xData:    [],
  yData:    [],
  rawData:  [],
  charts:   {},       // instances Chart.js actives
  officeReady: false,
};

// ── Initialisation Office.js ─────────────────────────────────────────────────
Office.onReady((info) => {
  if (info.host === Office.HostType.Excel) {
    state.officeReady = true;
  }
  initApp();
});

function initApp() {
  setupTabs();
  setupButtons();
  updateParamsUI();
  checkAPIHealth();
  setInterval(checkAPIHealth, 30000);
}

// ── Health Check ─────────────────────────────────────────────────────────────
async function checkAPIHealth() {
  try {
    const r = await fetch(`${API_BASE.replace("/api/v1","")}/health`, { signal: AbortSignal.timeout(3000) });
    const dot = document.getElementById("statusDot");
    if (r.ok) {
      dot.className = "status-dot online";
      dot.title = "API connectée";
    } else { throw new Error(); }
  } catch {
    document.getElementById("statusDot").className = "status-dot offline";
    document.getElementById("statusDot").title = "API déconnectée";
  }
}

// ── Navigation par onglets ───────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    });
  });
}

// ── Boutons ──────────────────────────────────────────────────────────────────
function setupButtons() {
  document.getElementById("btnReadRange").addEventListener("click", () => readExcelRange("rangeInput"));
  document.getElementById("btnAnalyze").addEventListener("click", runRegression);
  document.getElementById("btnStats").addEventListener("click", runStats);
  document.getElementById("btnSimulate").addEventListener("click", runPhysical);
  document.getElementById("btnReadSim").addEventListener("click", () => readExcelRange("simRange"));
  document.getElementById("btnCompare").addEventListener("click", runComparison);
  document.getElementById("btnExportResults").addEventListener("click", exportToExcel);
  document.getElementById("btnAIAdvise").addEventListener("click", runAIAdvise);
  document.getElementById("btnTrainML").addEventListener("click", runML);
  document.getElementById("btnTrainDL").addEventListener("click", runDL);
  document.getElementById("btnHybrid").addEventListener("click", runHybrid);
  document.getElementById("physicalModel").addEventListener("change", updateParamsUI);
}

// ═══════════════════════════════════════════════════════════════════════════
// EXCEL — LECTURE DE DONNÉES
// ═══════════════════════════════════════════════════════════════════════════

async function readExcelRange(inputId = "rangeInput") {
  // Guard : s'assurer qu'on a bien un string (pas un MouseEvent)
  if (typeof inputId !== "string") inputId = "rangeInput";
  const el = document.getElementById(inputId);
  if (!el) { showToast("Élément introuvable : " + inputId, "error"); return; }
  const rangeAddr = el.value.trim();
  if (!rangeAddr) { showToast("Entrez une plage valide (ex: A1:B50)", "error"); return; }

  if (!state.officeReady) {
    // Mode démo hors Excel
    loadDemoData();
    showToast("Mode démo — données simulées chargées", "info");
    return;
  }

  showLoader("Lecture Excel…");
  try {
    await Excel.run(async (context) => {
      const sheet = context.workbook.worksheets.getActiveWorksheet();
      const range = sheet.getRange(rangeAddr);
      range.load(["values", "numberFormat"]);
      await context.sync();

      const values = range.values;
      if (!values || values.length < 2) {
        throw new Error("Plage trop petite (min 2 lignes)");
      }

      // Détection en-têtes
      let startRow = 0;
      const firstRow = values[0];
      if (firstRow.some(v => typeof v === "string" && isNaN(parseFloat(v)))) {
        startRow = 1;
      }

      state.rawData = values;
      const numCols = values[0].length;

      if (numCols >= 2) {
        state.xData = values.slice(startRow).map(r => parseFloat(r[0])).filter(v => !isNaN(v));
        state.yData = values.slice(startRow).map(r => parseFloat(r[1])).filter(v => !isNaN(v));
      }

      renderDataPreview(values, startRow);
      showToast(`✓ ${state.xData.length} points chargés`, "success");
    });
  } catch(e) {
    showToast("Erreur lecture: " + e.message, "error");
  } finally {
    hideLoader();
  }
}

function loadDemoData() {
  // Données cinétiques simulées (ordre 1 + bruit)
  const t = Array.from({length: 30}, (_,i) => i * 3);
  const C = t.map(ti => 1.0 * Math.exp(-0.05 * ti) + (Math.random()-0.5)*0.04);
  state.xData = t;
  state.yData = C;
  const values = [["Temps (s)", "Concentration (mol/L)"], ...t.map((ti,i) => [ti, C[i]])];
  state.rawData = values;
  renderDataPreview(values, 1);
}

function renderDataPreview(values, startRow) {
  const el = document.getElementById("dataPreview");
  const cols = values[0];
  const rows = values.slice(startRow, startRow + 8);
  el.innerHTML = `<table>
    <thead><tr>${cols.map(c=>`<th>${c}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r=>`<tr>${r.map(v=>`<td>${typeof v==="number"?v.toFixed(4):v}</td>`).join("")}</tr>`).join("")}</tbody>
  </table>
  <div style="color:var(--text-muted);font-size:9px;margin-top:4px;">
    ${values.length - startRow} lignes chargées
  </div>`;
}

// ═══════════════════════════════════════════════════════════════════════════
// RÉGRESSION
// ═══════════════════════════════════════════════════════════════════════════

async function runRegression() {
  if (!state.xData.length) { showToast("Chargez des données d'abord", "error"); return; }

  const modelType = document.getElementById("regressionType").value;
  const degree    = parseInt(document.getElementById("polyDegree").value) || 3;
  const alpha     = parseFloat(document.getElementById("regAlpha").value) || 1.0;

  showLoader(`Régression ${modelType}…`);
  try {
    const res = await apiPost("/model", { x: state.xData, y: state.yData, model_type: modelType, degree, alpha });
    renderRegressionResult(res);
    showToast("✓ Régression terminée", "success");
  } catch(e) {
    showToast("Erreur: " + e.message, "error");
  } finally { hideLoader(); }
}

function renderRegressionResult(res) {
  // Graphique
  const isAuto = res.best_model !== undefined;
  const data   = isAuto ? res.all_models[res.best_model] : res;

  const chartCard = document.getElementById("chartCard");
  chartCard.style.display = "block";
  destroyChart("mainChart");

  const ctx = document.getElementById("mainChart").getContext("2d");
  state.charts["mainChart"] = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Données",
          data: state.xData.map((x,i) => ({x, y: state.yData[i]})),
          backgroundColor: "rgba(255,183,0,.7)",
          pointRadius: 4,
          pointHoverRadius: 6,
        },
        {
          label: data.model || "Modèle",
          data: data.x_fit.map((x,i) => ({x, y: data.y_fit[i]})),
          type: "line",
          borderColor: "#00e5c8",
          backgroundColor: "transparent",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
        },
      ],
    },
    options: chartOptions("Régression"),
  });

  // Résultats
  const el = document.getElementById("regressionResult");
  el.style.display = "block";

  const models = isAuto
    ? Object.entries(res.all_models).map(([k,v]) =>
        `<div class="metric-row">
          <span class="metric-label">${k}</span>
          <span class="metric-value ${v.metrics.r2 > 0.9 ? 'good' : v.metrics.r2 > 0.7 ? 'warn' : 'bad'}">
            R²=${v.metrics.r2.toFixed(4)}
          </span>
        </div>`).join("")
    : "";

  const m = data.metrics;
  el.innerHTML = `
    <h4>${isAuto ? `🏆 Meilleur: ${res.best_model}` : `Modèle: ${data.model}`}</h4>
    <div class="equation">${data.equation || ""}</div>
    <div class="metric-row"><span class="metric-label">R²</span>
      <span class="metric-value ${m.r2>0.9?'good':m.r2>0.7?'warn':'bad'}">${m.r2.toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">RMSE</span>
      <span class="metric-value">${m.rmse.toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">MAE</span>
      <span class="metric-value">${m.mae.toFixed(6)}</span></div>
    ${isAuto ? `<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:8px">${models}</div>` : ""}
  `;
}

// ═══════════════════════════════════════════════════════════════════════════
// STATISTIQUES DESCRIPTIVES
// ═══════════════════════════════════════════════════════════════════════════

async function runStats() {
  if (!state.xData.length) { showToast("Chargez des données d'abord", "error"); return; }

  showLoader("Analyse statistique…");
  try {
    const res = await apiPost("/analyze", {
      data: { x: state.xData, y: state.yData }
    });
    renderStats(res);
  } catch(e) {
    showToast("Erreur: " + e.message, "error");
  } finally { hideLoader(); }
}

function renderStats(res) {
  const el = document.getElementById("statsResult");
  el.style.display = "block";
  const stats = res.descriptive_stats;
  const corr  = res.correlation?.pearson_matrix;

  let html = "<h4>Statistiques Descriptives</h4>";
  for (const [col, s] of Object.entries(stats)) {
    html += `<div style="margin-bottom:8px;color:var(--amber);font-size:9px;letter-spacing:1px">${col.toUpperCase()}</div>`;
    const keys = ["count","mean","std","min","median","max","skewness","kurtosis"];
    for (const k of keys) {
      html += `<div class="metric-row">
        <span class="metric-label">${k}</span>
        <span class="metric-value">${typeof s[k]==="number"?s[k].toFixed(4):s[k]}</span>
      </div>`;
    }
  }

  if (corr) {
    const r = corr?.x?.y ?? corr?.y?.x;
    if (r !== undefined) {
      html += `<div class="metric-row" style="margin-top:8px">
        <span class="metric-label">Corrélation X↔Y</span>
        <span class="metric-value ${Math.abs(r)>0.7?'good':Math.abs(r)>0.4?'warn':'bad'}">${r.toFixed(4)}</span>
      </div>`;
      const interp = res.correlation?.interpretations?.["x_vs_y"] || "";
      if (interp) html += `<div class="hint" style="margin-top:4px">${interp}</div>`;
    }
  }

  el.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════════════════════
// MODÈLES PHYSIQUES — UI DYNAMIQUE
// ═══════════════════════════════════════════════════════════════════════════

const PHYSICAL_PARAMS = {
  kinetics_order0: [["C₀ (mol/L)","C0","1.0"],["k (ordre 0)","k","0.05"]],
  kinetics_order1: [["C₀ (mol/L)","C0","1.0"],["k (s⁻¹)","k","0.05"]],
  kinetics_order2: [["C₀ (mol/L)","C0","1.0"],["k (L/mol/s)","k","0.05"]],
  cstr:            [["Volume V (L)","V","10"],["Débit F (L/s)","F","1"],
                    ["C entrée","C_in","1.0"],["C initial","C0","0"],["k (s⁻¹)","k","0.1"]],
  diffusion:       [["D (m²/s)","D","1e-9"],["C₀","C0","0"],["Cs (surface)","Cs","1.0"],["t (s)","t","100"]],
  heat:            [["T₀ (°C)","T0","100"],["T∞ (°C)","T_inf","20"],["h (W/m²K)","h","10"],["m (kg)","m","1"],["Cp","cp","4186"]],
  rtd:             [["τ moyen (s)","tau","10"],["N réacteurs","N","3"]],
};

function updateParamsUI() {
  const model  = document.getElementById("physicalModel").value;
  const panel  = document.getElementById("paramsPanel");
  const params = PHYSICAL_PARAMS[model] || [];
  panel.innerHTML = `<label class="field-label">Paramètres du modèle</label>` +
    params.reduce((html, [label, id, defVal], i) => {
      const open = i % 2 === 0 ? `<div class="param-row">` : "";
      const close = i % 2 === 1 || i === params.length-1 ? `</div>` : "";
      return html + open + `<div>
        <div class="param-label">${label}</div>
        <input class="field-input" id="param_${id}" type="number" value="${defVal}" step="any"/>
      </div>` + close;
    }, "");
}

function getPhysicalParams() {
  const model  = document.getElementById("physicalModel").value;
  const params = PHYSICAL_PARAMS[model] || [];
  const result = {};
  params.forEach(([,id]) => {
    const el = document.getElementById("param_" + id);
    if (el) result[id] = parseFloat(el.value);
  });
  return result;
}

// ═══════════════════════════════════════════════════════════════════════════
// SIMULATION PHYSIQUE
// ═══════════════════════════════════════════════════════════════════════════

async function runPhysical() {
  const model   = document.getElementById("physicalModel").value;
  const params  = getPhysicalParams();
  const tStart  = parseFloat(document.getElementById("tStart").value) || 0;
  const tEnd    = parseFloat(document.getElementById("tEnd").value) || 100;
  const doFit   = document.getElementById("fitToggle").checked;

  if (doFit && !state.xData.length) {
    showToast("Chargez des données pour calibration", "error"); return;
  }

  showLoader("Simulation en cours…");
  try {
    let res;
    if (doFit) {
      // Calibration cinétique
      const order = model.includes("order0") ? 0 : model.includes("order2") ? 2 : 1;
      res = await apiPost("/physical/kinetics", {
        t: state.xData, C: state.yData,
        C0: params.C0 || 1, k: params.k || 0.1,
        order, fit: true,
      });
    } else {
      res = await apiPost("/simulate", { model, params, t_start: tStart, t_end: tEnd, n_points: 200 });
    }
    renderPhysicalResult(res, doFit);
    showToast("✓ Simulation terminée", "success");
  } catch(e) {
    showToast("Erreur: " + e.message, "error");
  } finally { hideLoader(); }
}

function renderPhysicalResult(res, doFit) {
  const chartCard = document.getElementById("physChart");
  chartCard.style.display = "block";
  destroyChart("physicalChart");

  const t = res.t || res.z || res.x;
  const y = res.C || res.T || res.E;

  const datasets = [{
    label: doFit ? "Modèle calibré" : "Simulation",
    data: t.map((ti,i) => ({x: ti, y: y[i]})),
    type: "line",
    borderColor: "#ffb700",
    backgroundColor: "rgba(255,183,0,.1)",
    borderWidth: 2.5,
    pointRadius: 0,
    tension: 0.4,
    fill: true,
  }];

  if (doFit && state.xData.length) {
    datasets.unshift({
      label: "Données expérimentales",
      data: state.xData.map((x,i) => ({x, y: state.yData[i]})),
      backgroundColor: "rgba(0,229,200,.7)",
      pointRadius: 5,
      type: "scatter",
    });
  }

  const ctx = document.getElementById("physicalChart").getContext("2d");
  state.charts["physicalChart"] = new Chart(ctx, {
    type: "scatter",
    data: { datasets },
    options: chartOptions(res.model || "Modèle physique"),
  });

  const el = document.getElementById("physResult");
  el.style.display = "block";
  const p = res.params || res;
  let paramsHtml = Object.entries(p)
    .filter(([k]) => !["t","C","T","E","z","x","y","t_fit","C_fit"].includes(k))
    .map(([k,v]) => `<div class="metric-row">
      <span class="metric-label">${k}</span>
      <span class="metric-value">${typeof v === "number" ? v.toFixed(6) : v}</span>
    </div>`).join("");

  el.innerHTML = `
    <h4>${res.model || "Résultats"}</h4>
    <div class="equation">${res.equation || ""}</div>
    ${res.r2 !== undefined ? `<div class="metric-row"><span class="metric-label">R²</span>
      <span class="metric-value ${res.r2>0.9?'good':'warn'}">${res.r2.toFixed(6)}</span></div>` : ""}
    ${paramsHtml}
  `;
}

// ═══════════════════════════════════════════════════════════════════════════
// COMPARAISON MODÈLE vs DONNÉES
// ═══════════════════════════════════════════════════════════════════════════

async function runComparison() {
  if (!state.xData.length) { showToast("Chargez des données d'abord", "error"); return; }

  const model = document.getElementById("simModel").value;
  showLoader("Comparaison…");
  try {
    const res = await apiPost("/physical/kinetics", {
      t: state.xData, C: state.yData,
      C0: 1.0, k: 0.05,
      order: model.includes("order2") ? 2 : model.includes("order0") ? 0 : 1,
      fit: true,
    });

    const simCard = document.getElementById("simChartCard");
    simCard.style.display = "block";
    destroyChart("simChart");

    const ctx = document.getElementById("simChart").getContext("2d");
    state.charts["simChart"] = new Chart(ctx, {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Données expérimentales",
            data: state.xData.map((x,i) => ({x, y: state.yData[i]})),
            backgroundColor: "rgba(255,183,0,.8)",
            pointRadius: 5,
          },
          {
            label: `Modèle (k=${res.k?.toFixed(4)})`,
            data: res.t_fit.map((t,i) => ({x: t, y: res.C_fit[i]})),
            type: "line",
            borderColor: "#00e5c8",
            backgroundColor: "transparent",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.4,
          },
        ],
      },
      options: chartOptions("Modèle vs Données"),
    });

    const el = document.getElementById("simResult");
    el.style.display = "block";
    el.innerHTML = `
      <h4>Calibration — Modèle ${model}</h4>
      <div class="metric-row"><span class="metric-label">C₀ calibré</span>
        <span class="metric-value">${res.C0?.toFixed(6)}</span></div>
      <div class="metric-row"><span class="metric-label">k calibré (s⁻¹)</span>
        <span class="metric-value">${res.k?.toFixed(6)}</span></div>
      <div class="metric-row"><span class="metric-label">R²</span>
        <span class="metric-value ${res.r2>0.9?'good':'warn'}">${res.r2?.toFixed(6)}</span></div>
    `;
    showToast("✓ Comparaison terminée", "success");
  } catch(e) {
    showToast("Erreur: " + e.message, "error");
  } finally { hideLoader(); }
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORT VERS EXCEL
// ═══════════════════════════════════════════════════════════════════════════

async function exportToExcel() {
  if (!state.officeReady) {
    showToast("Export Excel non disponible en mode démo", "info"); return;
  }

  showLoader("Export vers Excel…");
  try {
    await Excel.run(async (context) => {
      const sheet = context.workbook.worksheets.add("PhysioAI_Résultats");

      // Titre
      sheet.getRange("A1").values = [["PhysioAI Lab — Résultats d'analyse"]];
      sheet.getRange("A1").format.font.bold = true;
      sheet.getRange("A1").format.font.size = 14;
      sheet.getRange("A1").format.font.color = "#FFB700";

      // Données
      const headers = [["x", "y_données", "y_modèle"]];
      sheet.getRange("A3").values = headers;
      sheet.getRange("A3:C3").format.font.bold = true;
      sheet.getRange("A3:C3").format.fill.color = "#141720";
      sheet.getRange("A3:C3").format.font.color = "#00e5c8";

      const rows = state.xData.map((x,i) => [x, state.yData[i], ""]);
      if (rows.length > 0) {
        sheet.getRange(`A4:C${3+rows.length}`).values = rows;
      }

      sheet.getUsedRange().format.autofitColumns();
      await context.sync();
      showToast("✓ Exporté vers la feuille 'PhysioAI_Résultats'", "success");
    });
  } catch(e) {
    showToast("Erreur export: " + e.message, "error");
  } finally { hideLoader(); }
}

// ═══════════════════════════════════════════════════════════════════════════
// IA ADVISOR
// ═══════════════════════════════════════════════════════════════════════════

async function runAIAdvise() {
  if (!state.xData.length) {
    loadDemoData();
    showToast("Données démo chargées", "info");
  }

  showLoader("Analyse IA en cours…");
  try {
    const res = await apiPost("/ai/advise", { x: state.xData, y: state.yData });
    renderAIReport(res);
    showToast("✓ Analyse IA terminée", "success");
  } catch(e) {
    showToast("Erreur IA: " + e.message, "error");
  } finally { hideLoader(); }
}

function renderAIReport(res) {
  const el = document.getElementById("aiReport");
  el.style.display = "block";

  const s   = res.summary;
  const rec = res.recommendations;

  el.innerHTML = `
    <div class="ai-section">
      <div class="ai-section-title">Résumé des données</div>
      <span class="ai-badge">${s.n_points} points</span>
      <span class="ai-badge">${s.trend}</span>
      <span class="ai-badge">${s.complexity}</span>
      <span class="ai-badge">bruit: ${s.noise}</span>
    </div>

    <div class="ai-section">
      <div class="ai-section-title">Régression recommandée</div>
      <span class="ai-badge" style="background:rgba(255,183,0,.2)">${rec.regression.model}</span>
      <div class="hint" style="margin-top:4px">${rec.regression.reason}</div>
    </div>

    <div class="ai-section">
      <div class="ai-section-title">Modèle physique suggéré</div>
      <span class="ai-badge cyan">${rec.physical_model.model}</span>
      <div class="hint" style="margin-top:4px">${rec.physical_model.reason}</div>
    </div>

    <div class="ai-section">
      <div class="ai-section-title">Approche Machine Learning</div>
      <span class="ai-badge green">${rec.ml_model.model}</span>
      <div class="hint" style="margin-top:4px">${rec.ml_model.reason}</div>
    </div>

    <div class="ai-section">
      <div class="ai-section-title">Modèle hybride</div>
      <span class="ai-badge ${rec.hybrid_model.recommended ? 'cyan' : ''}">
        ${rec.hybrid_model.recommended ? '✓ Recommandé' : 'Non nécessaire'}
      </span>
      <div class="hint" style="margin-top:4px">${rec.hybrid_model.description}</div>
    </div>

    <div style="background:var(--amber-dim);border:1px solid rgba(255,183,0,.2);border-radius:6px;padding:8px;margin-top:8px;font-size:11px;color:var(--amber)">
      🎯 ${res.priority_action}
    </div>
  `;
}

// ═══════════════════════════════════════════════════════════════════════════
// MACHINE LEARNING
// ═══════════════════════════════════════════════════════════════════════════

async function runML() {
  if (!state.xData.length) { showToast("Chargez des données d'abord", "error"); return; }

  const modelType  = document.getElementById("mlModelType").value;
  const nEstim     = parseInt(document.getElementById("nEstimators").value) || 100;
  const X          = state.xData.map(v => [v]);

  showLoader(`Entraînement ${modelType}…`);
  try {
    const res = await apiPost("/train_ai", {
      X, y: state.yData,
      model_type: modelType,
      n_estimators: nEstim,
      n_clusters: nEstim,
    });
    renderMLResult(res);
    showToast("✓ Entraînement terminé", "success");
  } catch(e) {
    showToast("Erreur ML: " + e.message, "error");
  } finally { hideLoader(); }
}

function renderMLResult(res) {
  const el = document.getElementById("mlResult");
  el.style.display = "block";

  if (res.model === "kmeans") {
    el.innerHTML = `
      <h4>K-Means Clustering</h4>
      <div class="metric-row"><span class="metric-label">Clusters</span>
        <span class="metric-value">${res.n_clusters}</span></div>
      <div class="metric-row"><span class="metric-label">Silhouette</span>
        <span class="metric-value ${res.silhouette>0.5?'good':'warn'}">${res.silhouette.toFixed(4)}</span></div>
      <div class="metric-row"><span class="metric-label">Inertie</span>
        <span class="metric-value">${res.inertia.toFixed(4)}</span></div>
    `;
    return;
  }

  el.innerHTML = `
    <h4>${res.model}</h4>
    <div class="metric-row"><span class="metric-label">R² Train</span>
      <span class="metric-value ${res.train_r2>0.9?'good':'warn'}">${(res.train_r2||0).toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">R² Test</span>
      <span class="metric-value ${res.test_r2>0.9?'good':'warn'}">${res.test_r2.toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">RMSE Test</span>
      <span class="metric-value">${res.test_rmse.toFixed(6)}</span></div>
    ${res.cv_r2_mean !== undefined ? `
    <div class="metric-row"><span class="metric-label">CV R² moyen</span>
      <span class="metric-value">${res.cv_r2_mean.toFixed(4)} ± ${res.cv_r2_std.toFixed(4)}</span></div>` : ""}
    ${res.feature_importances ? `
    <div class="metric-row"><span class="metric-label">Importance feat.</span>
      <span class="metric-value">${res.feature_importances.map(v=>v.toFixed(4)).join(", ")}</span></div>` : ""}
  `;
}

// ═══════════════════════════════════════════════════════════════════════════
// DEEP LEARNING
// ═══════════════════════════════════════════════════════════════════════════

async function runDL() {
  if (!state.xData.length) { showToast("Chargez des données d'abord", "error"); return; }

  const epochs  = parseInt(document.getElementById("dlEpochs").value) || 200;
  const hidden  = document.getElementById("dlHidden").value
                    .split(",").map(v => parseInt(v.trim())).filter(v => !isNaN(v));
  const X       = state.xData.map(v => [v]);

  showLoader(`Deep Learning — ${epochs} epochs…`);
  try {
    const res = await apiPost("/predict", { X, y: state.yData, hidden_layers: hidden, epochs });
    renderDLResult(res);
    showToast(`✓ DL terminé — R²=${res.test_r2.toFixed(4)}`, "success");
  } catch(e) {
    showToast("Erreur DL: " + e.message, "error");
  } finally { hideLoader(); }
}

function renderDLResult(res) {
  const dlCard = document.getElementById("dlChartCard");
  dlCard.style.display = "block";
  destroyChart("dlChart");

  // Courbe de perte
  const ctx = document.getElementById("dlChart").getContext("2d");
  const epochs = res.history.train_loss.map((_,i) => i * 20);
  state.charts["dlChart"] = new Chart(ctx, {
    type: "line",
    data: {
      labels: epochs,
      datasets: [
        {
          label: "Train Loss",
          data: res.history.train_loss,
          borderColor: "#ffb700",
          backgroundColor: "transparent",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
        },
        {
          label: "Val Loss",
          data: res.history.val_loss,
          borderColor: "#00e5c8",
          backgroundColor: "transparent",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
          borderDash: [4,3],
        },
      ],
    },
    options: chartOptions("Courbe d'apprentissage"),
  });

  const el = document.getElementById("dlResult");
  el.style.display = "block";
  el.innerHTML = `
    <h4>MLP — Architecture [${res.architecture.join("→")}]</h4>
    <div class="metric-row"><span class="metric-label">R² Test</span>
      <span class="metric-value ${res.test_r2>0.9?'good':'warn'}">${res.test_r2.toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">RMSE Test</span>
      <span class="metric-value">${res.test_rmse.toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">Best Val Loss</span>
      <span class="metric-value">${res.best_val_loss.toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">Device</span>
      <span class="metric-value">${res.device}</span></div>
  `;
}

// ═══════════════════════════════════════════════════════════════════════════
// MODÈLE HYBRIDE
// ═══════════════════════════════════════════════════════════════════════════

async function runHybrid() {
  if (!state.xData.length) { showToast("Chargez des données d'abord", "error"); return; }

  const C0     = parseFloat(document.getElementById("hybC0").value) || 1.0;
  const k      = parseFloat(document.getElementById("hybK").value) || 0.05;

  showLoader("Entraînement modèle hybride…");
  try {
    const res = await apiPost("/predict/hybrid", {
      t: state.xData, C: state.yData, C0, k, epochs: 300
    });
    renderHybridResult(res);
    showToast("✓ Modèle hybride entraîné", "success");
  } catch(e) {
    showToast("Erreur hybride: " + e.message, "error");
  } finally { hideLoader(); }
}

function renderHybridResult(res) {
  const hybCard = document.getElementById("hybridChartCard");
  hybCard.style.display = "block";
  destroyChart("hybridChart");

  const ctx = document.getElementById("hybridChart").getContext("2d");
  state.charts["hybridChart"] = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Données exp.",
          data: res.t.map((t,i) => ({x: t, y: res.C_data[i]})),
          backgroundColor: "rgba(255,183,0,.7)",
          pointRadius: 5,
        },
        {
          label: "Modèle physique",
          data: res.t.map((t,i) => ({x: t, y: res.C_physics[i]})),
          type: "line", borderColor: "#8b93a8",
          backgroundColor: "transparent",
          borderWidth: 1.5, borderDash: [4,3], pointRadius: 0, tension: 0.4,
        },
        {
          label: "Modèle hybride",
          data: res.t.map((t,i) => ({x: t, y: res.C_hybrid[i]})),
          type: "line", borderColor: "#00e5c8",
          backgroundColor: "rgba(0,229,200,.08)",
          borderWidth: 2.5, pointRadius: 0, tension: 0.4, fill: true,
        },
      ],
    },
    options: chartOptions("Physique + NN"),
  });

  const el = document.getElementById("hybridResult");
  el.style.display = "block";
  el.innerHTML = `
    <h4>Modèle Hybride Physique + Réseau de Neurones</h4>
    <div class="metric-row"><span class="metric-label">R² Modèle physique</span>
      <span class="metric-value warn">${res.physics_r2.toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">R² Hybride</span>
      <span class="metric-value ${res.hybrid_r2>0.9?'good':'warn'}">${res.hybrid_r2.toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">Amélioration ΔR²</span>
      <span class="metric-value ${res.improvement>0?'good':'bad'}">+${res.improvement.toFixed(6)}</span></div>
  `;
}

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS — API
// ═══════════════════════════════════════════════════════════════════════════

async function apiPost(endpoint, payload) {
  const res = await fetch(API_BASE + endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({detail: res.statusText}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS — CHART.JS
// ═══════════════════════════════════════════════════════════════════════════

function chartOptions(title) {
  return {
    responsive: true,
    animation: { duration: 600, easing: "easeInOutQuart" },
    plugins: {
      legend: {
        labels: { color: "#8b93a8", font: { family: "'DM Sans'", size: 10 }, boxWidth: 12 }
      },
      title: { display: true, text: title, color: "#ffb700",
               font: { family: "'Space Mono'", size: 10 } },
    },
    scales: {
      x: {
        grid:   { color: "rgba(255,255,255,.04)" },
        ticks:  { color: "#4a5168", font: { size: 9 } },
        border: { color: "rgba(255,255,255,.07)" },
      },
      y: {
        grid:   { color: "rgba(255,255,255,.04)" },
        ticks:  { color: "#4a5168", font: { size: 9 } },
        border: { color: "rgba(255,255,255,.07)" },
      },
    },
  };
}

function destroyChart(id) {
  if (state.charts[id]) {
    state.charts[id].destroy();
    delete state.charts[id];
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS — UI
// ═══════════════════════════════════════════════════════════════════════════

function showLoader(text = "Traitement…") {
  document.getElementById("loaderText").textContent = text;
  document.getElementById("loaderOverlay").style.display = "flex";
}
function hideLoader() {
  document.getElementById("loaderOverlay").style.display = "none";
}

let toastTimeout;
function showToast(msg, type = "info") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = `toast ${type} show`;
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => el.classList.remove("show"), 3500);
}