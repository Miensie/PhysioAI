/**
 * PhysioAI Lab — Office Add-in JavaScript
 * =========================================
 * Gère toute la logique frontend :
 *   - Lecture de données depuis Excel (Office.js)
 *   - Appels API REST vers le backend FastAPI
 *   - Rendu des graphiques Chart.js
 *   - Affichage des résultats
 */

// ── Configuration API (chargée depuis js/config.js) ─────────────────────────
// ✏️  Pour changer l'URL du backend : modifier js/config.js → RENDER_API_URL
const API_BASE = (window.PHYSIOAI_CONFIG?.API_BASE_URL || "http://localhost:8000") + "/api/v1";

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
  // Cinétique
  kinetics_order0: [["C₀ (mol/L)","C0","1.0"], ["k (mol/L/s)","k","0.05"]],
  kinetics_order1: [["C₀ (mol/L)","C0","1.0"], ["k (s⁻¹)","k","0.05"]],
  kinetics_order2: [["C₀ (mol/L)","C0","1.0"], ["k (L/mol/s)","k","0.05"]],
  // Réacteurs
  cstr: [["Volume V (L)","V","10"], ["Débit F (L/s)","F","1"],
         ["C entrée (mol/L)","C_in","1.0"], ["C initial","C0","0"], ["k (s⁻¹)","k","0.1"]],
  pfr:  [["Débit F (L/s)","F","1"], ["Section A (m²)","A","0.1"],
         ["C₀ (mol/L)","C0","1.0"], ["k","k","0.1"], ["Longueur L (m)","L","1.0"]],
  // Transport
  diffusion: [["D (m²/s)","D","1e-9"], ["C₀ initial","C0","0"],
              ["Cs (surface)","Cs","1.0"], ["t (s)","t","100"]],
  darcy:     [["ΔP (Pa)","dP","1000"], ["Viscosité μ (Pa·s)","mu","0.001"],
              ["Perméabilité k (m²)","k_perm","1e-12"], ["Longueur L (m)","L","1.0"], ["Section A (m²)","A","0.01"]],
  // Thermique
  heat:    [["T₀ (°C)","T0","100"], ["T∞ (°C)","T_inf","20"],
            ["h·A (W/K)","h","10"], ["Masse m (kg)","m","1"], ["Cp (J/kg/K)","cp","4186"]],
  antoine: [["A (NIST)","A","8.07131"], ["B (NIST)","B","1730.63"], ["C (NIST)","C","233.426"]],
  // Hydrodynamique
  rtd: [["Temps séjour τ (s)","tau","10"], ["Nb réacteurs N","N","3"]],
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
  const model  = document.getElementById("physicalModel").value;
  const params = getPhysicalParams();
  const tStart = parseFloat(document.getElementById("tStart").value) || 0;
  const tEnd   = parseFloat(document.getElementById("tEnd").value)   || 100;
  const doFit  = document.getElementById("fitToggle").checked;

  if (doFit && !state.xData.length) {
    showToast("Chargez des données pour calibration", "error"); return;
  }

  showLoader("Simulation en cours…");
  try {
    let res;

    if (doFit && model.startsWith("kinetics")) {
      // Calibration sur données Excel
      const order = model.includes("order0") ? 0 : model.includes("order2") ? 2 : 1;
      res = await apiPost("/physical/kinetics", {
        t: state.xData, C: state.yData,
        C0: params.C0 || 1.0, k: params.k || 0.1,
        order, fit: true,
      });
    } else if (model === "darcy") {
      // Darcy = calcul scalaire direct, pas de simulation temporelle
      res = await apiPost("/physical/darcy", params);
    } else if (model === "antoine") {
      // Antoine = domaine de température
      res = await apiPost("/physical/antoine", {
        T_range: Array.from({length:200}, (_,i) => tStart + i*(tEnd-tStart)/199),
        A: params.A || 8.07131, B: params.B || 1730.63, C: params.C || 233.426,
      });
    } else if (model === "pfr") {
      res = await apiPost("/physical/pfr", {
        z: Array.from({length:200}, (_,i) => i*(params.L||1.0)/199),
        F: params.F, A: params.A, C0: params.C0, k: params.k, order: 1,
      });
    } else {
      // Tous les autres via /simulate (génère le domaine t automatiquement)
      res = await apiPost("/simulate", { model, params, t_start: tStart, t_end: tEnd, n_points: 200 });
    }

    renderPhysicalResult(res, doFit);
    showToast("✓ Simulation terminée", "success");
  } catch(e) {
    showToast("Erreur: " + e.message, "error");
  } finally { hideLoader(); }
}

function renderPhysicalResult(res, doFit) {
  resultCache.physical = res;  // sauvegarde pour Décision
  const chartCard = document.getElementById("physChart");
  chartCard.style.display = "block";
  destroyChart("physicalChart");

  // Darcy est scalaire — afficher seulement les métriques
  if (res.model === "darcy_flow") {
    const el = document.getElementById("physResult");
    el.style.display = "block";
    document.getElementById("physChart").style.display = "none";
    el.innerHTML = `<h4>Loi de Darcy</h4>
      <div class="equation">${res.equation}</div>
      <div class="metric-row"><span class="metric-label">Débit Q (m³/s)</span>
        <span class="metric-value">${res.Q.toExponential(4)}</span></div>
      <div class="metric-row"><span class="metric-label">Vitesse Darcy (m/s)</span>
        <span class="metric-value">${res.v_darcy.toExponential(4)}</span></div>`;
    return;
  }
  const t = res.t || res.z || res.x || res.T;
  const y = res.C || res.T_val || res.E || res.P_sat;
  // Renommer la clé T (température) pour éviter collision avec vecteur T (Antoine)
  const yData = res.C ?? res.T ?? res.E ?? res.P_sat;

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

  const s    = res.summary   || {};
  const recs = res.recommendations || {};
  const all  = recs.all_recommendations || [];
  const dq   = recs.data_quality || {};
  const warnings = recs.warnings || [];

  // Regrouper par type pour affichage structuré
  const byType = {};
  all.forEach(r => {
    if (!byType[r.type]) byType[r.type] = [];
    byType[r.type].push(r);
  });

  // Badges couleur par type
  const typeStyle = {
    regression:   "background:rgba(255,183,0,.2);color:var(--amber)",
    physical:     "background:var(--cyan-dim);color:var(--cyan)",
    ml:           "background:rgba(61,255,160,.1);color:var(--green)",
    deep_learning:"background:rgba(160,108,255,.15);color:#a06cff",
    hybrid:       "background:rgba(0,229,200,.1);color:var(--cyan)",
  };
  const typeLabel = {
    regression:   "Régression",
    physical:     "Modèle Physique",
    ml:           "Machine Learning",
    deep_learning:"Deep Learning",
    hybrid:       "Modèle Hybride",
  };

  // Sections par type
  let sectionsHtml = Object.entries(byType).map(([type, items]) => `
    <div class="ai-section">
      <div class="ai-section-title">${typeLabel[type] || type}</div>
      ${items.map(r => `
        <div style="margin-bottom:6px">
          <span class="ai-badge" style="${typeStyle[type] || ''}">${r.model}</span>
          <span class="ai-badge" style="font-size:9px;opacity:.7">${r.confidence}</span>
          <div class="hint" style="margin-top:3px">${r.reason}</div>
        </div>`).join('')}
    </div>`).join('');

  // Qualité données
  const qScore = dq.score || 0;
  const qLabel = dq.label || '';
  const qColor = qScore >= 80 ? 'var(--green)' : qScore >= 60 ? 'var(--amber)' : 'var(--red)';

  // Alertes
  const warningsHtml = warnings.length
    ? `<div class="ai-section">
        <div class="ai-section-title">Alertes</div>
        ${warnings.map(w => `<div class="hint" style="color:var(--amber);margin-bottom:3px">${w}</div>`).join('')}
       </div>` : '';

  el.innerHTML = `
    <div class="ai-section">
      <div class="ai-section-title">Résumé des données</div>
      <span class="ai-badge">${s.n_points || '?'} points</span>
      <span class="ai-badge">${s.trend || '?'}</span>
      <span class="ai-badge">${s.complexity || '?'}</span>
      <span class="ai-badge">bruit: ${s.noise || '?'}</span>
      <div style="margin-top:8px;font-size:10px;color:var(--text-muted)">
        Qualité données :
        <span style="color:${qColor};font-weight:700">${qScore}/100 — ${qLabel}</span>
      </div>
    </div>

    ${sectionsHtml}
    ${warningsHtml}

    <div style="background:var(--amber-dim);border:1px solid rgba(255,183,0,.2);border-radius:6px;padding:8px;margin-top:8px;font-size:11px;color:var(--amber)">
      🎯 ${res.priority_action || ''}
    </div>
  `;

  // Sauvegarder pour Gemini
  resultCache.advisor = res;
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


// ═══════════════════════════════════════════════════════════════════════════
// TAB PRÉDICTION
// ═══════════════════════════════════════════════════════════════════════════

// ── Cache des derniers résultats pour Gemini ─────────────────────────────────
const resultCache = {
  regression: null,
  physical:   null,
  advisor:    null,
};

// Intercepter les résultats existants pour les mettre en cache
const _origRenderRegression = typeof renderRegressionResult === 'function'
  ? renderRegressionResult : null;

// ── Init des boutons Prédiction & Décision ───────────────────────────────────
(function initNewTabs() {
  // Attendre que le DOM soit prêt
  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btnGenerateRange")
      ?.addEventListener("click", generateXRange);
    document.getElementById("btnPredict")
      ?.addEventListener("click", runPrediction);
    document.getElementById("btnExportPredict")
      ?.addEventListener("click", exportPredictions);
    document.getElementById("btnQuickDecision")
      ?.addEventListener("click", runQuickDecision);
    document.getElementById("btnGeminiDecision")
      ?.addEventListener("click", runGeminiDecision);

    // Boutons langue
    document.querySelectorAll(".lang-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".lang-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
      });
    });
  });
})();

// ── Mise à jour statut données ────────────────────────────────────────────────
function updatePredictDataStatus() {
  const el = document.getElementById("predictDataStatus");
  if (!el) return;
  if (state.xData.length) {
    el.innerHTML = `<span class="status-badge online">
      ✓ ${state.xData.length} points chargés</span>`;
  } else {
    el.innerHTML = `<span class="status-badge offline">
      Aucune donnée — chargez depuis l'onglet Analyser</span>`;
  }
}

// ── Générer une plage X ───────────────────────────────────────────────────────
function generateXRange() {
  const from = parseFloat(document.getElementById("predictXFrom").value);
  const to   = parseFloat(document.getElementById("predictXTo").value);
  const n    = parseInt(document.getElementById("predictXN").value) || 20;
  if (isNaN(from) || isNaN(to)) {
    showToast("Entrez les bornes 'De' et 'À'", "error"); return;
  }
  const step = (to - from) / (n - 1);
  const vals = Array.from({length: n}, (_, i) => parseFloat((from + i*step).toFixed(6)));
  document.getElementById("predictXInput").value = vals.join(", ");
  showToast(`✓ ${n} valeurs générées [${from} → ${to}]`, "info");
}

// ── Lancer la prédiction ──────────────────────────────────────────────────────
async function runPrediction() {
  updatePredictDataStatus();
  if (!state.xData.length) {
    showToast("Chargez des données d'entraînement d'abord (onglet Analyser)", "error");
    return;
  }

  const rawInput = document.getElementById("predictXInput").value.trim();
  if (!rawInput) { showToast("Entrez les valeurs X à prédire", "error"); return; }

  // Parser les X de prédiction
  const xPred = rawInput
    .split(/[\s,;]+/)
    .map(v => parseFloat(v))
    .filter(v => !isNaN(v));

  if (!xPred.length) { showToast("Valeurs X invalides", "error"); return; }

  const modelType = document.getElementById("predictModel").value;
  const ci        = document.getElementById("predictCI")?.checked ?? true;
  const X_train   = state.xData.map(v => [v]);
  const X_predict = xPred.map(v => [v]);

  // Paramètres propres à l'onglet Prédiction
  const degree      = parseInt(document.getElementById("predictDegree")?.value)  || 3;
  const alpha       = parseFloat(document.getElementById("predictAlpha")?.value)  || 1.0;
  const nEstim      = parseInt(document.getElementById("predictNEstim")?.value)   || 100;
  const dlHidden    = (document.getElementById("predictHidden")?.value || "64,32,16")
                        .split(",").map(v => parseInt(v.trim())).filter(v => !isNaN(v));
  const dlEpochs    = parseInt(document.getElementById("predictEpochs")?.value)   || 200;

  showLoader(`Prédiction (${modelType})…`);
  try {
    const res = await apiPost("/predict/new", {
      X_train, y_train: state.yData, X_predict,
      model_type:           modelType,
      confidence_interval:  ci,
      degree:               degree,
      alpha:                alpha,
      n_estimators:         nEstim,
      hidden_layers:        dlHidden,
      epochs:               dlEpochs,
    });

    renderPredictionResult(res, xPred);
    showToast(`✓ ${res.predictions.length} valeurs prédites`, "success");
  } catch(e) {
    showToast("Erreur prédiction : " + e.message, "error");
  } finally { hideLoader(); }
}

// ── Afficher les résultats de prédiction ──────────────────────────────────────
function renderPredictionResult(res, xPred) {
  // Graphique
  const chartCard = document.getElementById("predictChartCard");
  chartCard.style.display = "block";
  destroyChart("predictChart");

  const ctx = document.getElementById("predictChart").getContext("2d");
  const datasets = [
    {
      label: "Données entraînement",
      data: state.xData.map((x,i) => ({x, y: state.yData[i]})),
      backgroundColor: "rgba(255,183,0,.7)",
      pointRadius: 4,
      type: "scatter",
    },
    {
      label: `Prédictions (${res.model_type})`,
      data: xPred.map((x,i) => ({x, y: res.predictions[i]})),
      borderColor: "#6495ff",
      backgroundColor: "rgba(100,149,255,.15)",
      borderWidth: 2.5,
      pointRadius: 6,
      pointStyle: "diamond",
      type: "scatter",
    },
  ];

  // Intervalles de confiance
  if (res.ci_lower && res.ci_upper) {
    datasets.push({
      label: `IC ${res.ci_level || "95%"}`,
      data: xPred.map((x,i) => ({x, y: res.ci_upper[i]})),
      borderColor: "rgba(100,149,255,.3)",
      backgroundColor: "rgba(100,149,255,.07)",
      borderWidth: 1,
      borderDash: [4,3],
      pointRadius: 0,
      type: "line",
      fill: "-1",
    });
    datasets.push({
      label: `IC lower`,
      data: xPred.map((x,i) => ({x, y: res.ci_lower[i]})),
      borderColor: "rgba(100,149,255,.3)",
      backgroundColor: "transparent",
      borderWidth: 1,
      borderDash: [4,3],
      pointRadius: 0,
      type: "line",
    });
  }

  state.charts["predictChart"] = new Chart(ctx, {
    type: "scatter",
    data: { datasets },
    options: chartOptions(`Prédictions — ${res.model_type}  (R²train=${res.train_r2})`),
  });

  // Résumé métriques
  const elRes = document.getElementById("predictResult");
  elRes.style.display = "block";
  const ps = res.pred_stats || {};
  elRes.innerHTML = `
    <h4>Résultats de prédiction</h4>
    <div class="metric-row"><span class="metric-label">Modèle</span>
      <span class="metric-value">${res.model_type}</span></div>
    <div class="metric-row"><span class="metric-label">R² entraînement</span>
      <span class="metric-value ${res.train_r2>0.9?'good':res.train_r2>0.7?'warn':'bad'}">
        ${res.train_r2?.toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">RMSE entraînement</span>
      <span class="metric-value">${res.train_rmse?.toFixed(6)}</span></div>
    <div class="metric-row"><span class="metric-label">N prédictions</span>
      <span class="metric-value">${res.n_predict}</span></div>
    <div class="metric-row"><span class="metric-label">Moy. prédite</span>
      <span class="metric-value">${ps.mean?.toFixed(6) ?? '—'}</span></div>
    <div class="metric-row"><span class="metric-label">Plage [min, max]</span>
      <span class="metric-value">[${ps.min?.toFixed(4) ?? '—'}, ${ps.max?.toFixed(4) ?? '—'}]</span></div>
    ${res.ci_level ? `<div class="metric-row"><span class="metric-label">Intervalle confiance</span>
      <span class="metric-value cyan">${res.ci_level}</span></div>` : ''}
  `;

  // Tableau
  state._lastPredictions = { xPred, res };
  renderPredictTable(xPred, res);
}

function renderPredictTable(xPred, res) {
  const panel = document.getElementById("predictTablePanel");
  panel.style.display = "block";
  const hasCI = !!(res.ci_lower && res.ci_upper);
  const rows = xPred.map((x,i) => `
    <tr>
      <td>${x.toFixed(4)}</td>
      <td style="color:var(--cyan)">${res.predictions[i]?.toFixed(6) ?? '—'}</td>
      ${hasCI ? `<td class="ci-col">${res.ci_lower[i]?.toFixed(4) ?? '—'}</td>
                 <td class="ci-col">${res.ci_upper[i]?.toFixed(4) ?? '—'}</td>` : ''}
      <td style="color:var(--text-muted);font-size:9px">${res.ci_std?.[i]?.toFixed(4) ?? '—'}</td>
    </tr>`).join('');

  document.getElementById("predictTableWrap").innerHTML = `
    <table>
      <thead><tr>
        <th>x</th><th>ŷ prédit</th>
        ${hasCI ? '<th>IC inf.</th><th>IC sup.</th>' : ''}
        <th>σ</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function exportPredictions() {
  if (!state.officeReady || !state._lastPredictions) {
    showToast("Aucune prédiction à exporter", "info"); return;
  }
  const { xPred, res } = state._lastPredictions;
  showLoader("Export…");
  try {
    await Excel.run(async ctx => {
      const sheet = ctx.workbook.worksheets.add("PhysioAI_Prédictions");
      sheet.getRange("A1").values = [["PhysioAI Lab — Prédictions"]];
      sheet.getRange("A1").format.font.bold = true;
      sheet.getRange("A1").format.font.color = "#6495ff";

      const headers = [["x", "y_prédit", "IC_inférieur", "IC_supérieur", "σ"]];
      sheet.getRange("A3:E3").values = headers;
      sheet.getRange("A3:E3").format.font.bold = true;

      const rows = xPred.map((x,i) => [
        x,
        res.predictions[i] ?? "",
        res.ci_lower?.[i] ?? "",
        res.ci_upper?.[i] ?? "",
        res.ci_std?.[i] ?? "",
      ]);
      sheet.getRange(`A4:E${3+rows.length}`).values = rows;
      sheet.getUsedRange().format.autofitColumns();
      await ctx.sync();
      showToast("✓ Exporté vers 'PhysioAI_Prédictions'", "success");
    });
  } catch(e) { showToast("Erreur export : " + e.message, "error"); }
  finally { hideLoader(); }
}


// ═══════════════════════════════════════════════════════════════════════════
// TAB DÉCISION GLOBALE
// ═══════════════════════════════════════════════════════════════════════════

function toggleKeyVisibility() {
  const el = document.getElementById("geminiKey");
  if (!el) return;
  el.type = document.getElementById("showKey").checked ? "text" : "password";
}

function getSelectedLanguage() {
  const active = document.querySelector(".lang-btn.active");
  return active?.dataset.lang || "fr";
}

// ── Décision rapide (sans Gemini) ─────────────────────────────────────────────
async function runQuickDecision() {
  if (!state.xData.length) {
    showToast("Chargez des données d'abord", "error"); return;
  }
  showLoader("Analyse complète en cours…");
  try {
    // Étape 1 — lancer la meilleure régression si pas encore fait
    if (!resultCache.regression) {
      showLoader("1/3 — Régression automatique…");
      try {
        const regRes = await apiPost("/model", {
          x: state.xData, y: state.yData, model_type: "auto"
        });
        resultCache.regression = regRes;
      } catch(e) { console.warn("Régression échouée:", e); }
    }

    // Étape 2 — lancer l'analyse IA si pas encore fait
    if (!resultCache.advisor) {
      showLoader("2/3 — Analyse IA Advisor…");
      try {
        const advRes = await apiPost("/ai/advise", {
          x: state.xData, y: state.yData
        });
        resultCache.advisor = advRes;
      } catch(e) { console.warn("AI Advisor échoué:", e); }
    }

    // Étape 3 — décision rapide avec tout le contexte disponible
    showLoader("3/3 — Décision globale…");
    const res = await apiPost("/decision/quick", {
      x: state.xData, y: state.yData,
      gemini_api_key: "local",
      context: document.getElementById("decisionContext").value,
      language: getSelectedLanguage(),
      regression_result:  document.getElementById("includeRegression")?.checked
                          ? resultCache.regression : null,
      physical_result:    document.getElementById("includePhysical")?.checked
                          ? resultCache.physical   : null,
      ai_advisor_result:  document.getElementById("includeAdvisor")?.checked
                          ? resultCache.advisor    : null,
    });

    // Enrichir le rapport avec les vrais résultats de régression
    if (resultCache.regression && res.report) {
      const best = resultCache.regression.best_model || resultCache.regression.model || "?";
      const allM = resultCache.regression.all_models || {};
      const models = Object.entries(allM).map(([k,v]) =>
        `${k}: R²=${v.metrics?.r2?.toFixed(4) || '?'}`).join(' | ');
      res.report._regression_detail = `Meilleur: ${best} | Tous: ${models}`;
    }

    renderDecisionReport(res, false);
    showToast("✓ Décision rapide complète générée", "success");
  } catch(e) {
    showToast("Erreur : " + e.message, "error");
  } finally { hideLoader(); }
}

// ── Décision Gemini ───────────────────────────────────────────────────────────
async function runGeminiDecision() {
  if (!state.xData.length) {
    showToast("Chargez des données d'abord", "error"); return;
  }
  const apiKey = document.getElementById("geminiKey").value.trim();
  if (!apiKey) {
    showToast("Entrez votre clé API Google AI Studio", "error"); return;
  }

  showLoader("✦ Gemini analyse vos données…");
  try {
    const payload = {
      x: state.xData, y: state.yData,
      gemini_api_key: apiKey,
      context: document.getElementById("decisionContext").value,
      language: getSelectedLanguage(),
      regression_result:  document.getElementById("includeRegression").checked
                          ? resultCache.regression : null,
      physical_result:    document.getElementById("includePhysical").checked
                          ? resultCache.physical   : null,
      ai_advisor_result:  document.getElementById("includeAdvisor").checked
                          ? resultCache.advisor    : null,
    };
    const res = await apiPost("/decision/global", payload);
    renderDecisionReport(res, true);
    showToast("✓ Rapport Gemini généré", "success");
  } catch(e) {
    showToast("Erreur Gemini : " + e.message, "error");
  } finally { hideLoader(); }
}

// ── Rendu du rapport de décision ──────────────────────────────────────────────
function renderDecisionReport(res, isGemini) {
  const el = document.getElementById("decisionReport");
  el.style.display = "block";

  const r   = res.report;
  const lang = res.language || "fr";
  const isFr = lang === "fr";

  // Clés selon langue
  const dg  = r.decision_globale  || r.global_decision  || {};
  const ip  = r.interpretation_physique || r.physical_interpretation || {};
  const vc  = r.validation_croisee || r.cross_validation || {};
  const rec = r.recommandations_prioritaires || r.priority_recommendations || [];
  const ns  = r.prochaines_etapes  || r.next_steps || {};
  const risks = r.risques || r.risks || [];
  const exec = r.resume_executif || r.executive_summary || "";
  const note = r.note || "";

  const score = dg.score_qualite_donnees ?? dg.data_quality_score ?? 0;
  const conf  = (dg.confiance || dg.confidence || "?").toLowerCase();
  const confClass = conf.includes("haut") || conf === "high" ? "high"
                  : conf.includes("moy")  || conf === "medium" ? "medium" : "low";

  // Construire les sections
  let html = `
  <div class="dr-section">
    <div class="dr-title">${isGemini ? '✦ Gemini' : '⚡ Analyse locale'} — ${isFr ? 'Décision Globale' : 'Global Decision'}</div>
    <div class="dr-verdict">
      <div class="dr-verdict-text">${dg.verdict || dg.verdict || '—'}</div>
      <div class="dr-confidence ${confClass}">● ${isFr ? 'Confiance' : 'Confidence'} : ${dg.confiance || dg.confidence || '?'}</div>
    </div>
    <div style="font-size:9px;color:var(--text-muted);margin-bottom:3px">
      ${isFr ? 'Qualité des données' : 'Data quality'} : ${score}/100
    </div>
    <div class="dr-score-bar">
      <div class="dr-score-fill" style="width:${Math.min(score,100)}%"></div>
    </div>
  </div>`;

  // Interprétation physique
  if (ip && Object.keys(ip).length) {
    const ph = ip.phenomene_detecte || ip.detected_phenomenon || '';
    const mec = ip.mecanisme || ip.mechanism || '';
    const sig = ip.signification_physique || ip.physical_meaning || '';
    const params = ip.parametres_cles || ip.key_parameters || [];
    html += `
  <div class="dr-section">
    <div class="dr-title">${isFr ? '⚗ Interprétation Physique' : '⚗ Physical Interpretation'}</div>
    ${ph ? `<div class="metric-row"><span class="metric-label">${isFr?'Phénomène':'Phenomenon'}</span><span class="metric-value">${ph}</span></div>` : ''}
    ${mec ? `<div class="metric-row"><span class="metric-label">${isFr?'Mécanisme':'Mechanism'}</span><span style="font-size:11px;color:var(--text-secondary)">${mec}</span></div>` : ''}
    ${sig ? `<div class="hint" style="margin-top:6px">${sig}</div>` : ''}
    ${params.length ? `<div style="margin-top:6px">${params.map(p=>`<span class="ai-badge cyan">${p}</span>`).join('')}</div>` : ''}
  </div>`;
  }

  // Validation croisée
  if (vc && Object.keys(vc).length) {
    const points = vc.points_forts || vc.strengths || [];
    const concerns = vc.points_attention || vc.concerns || [];
    html += `
  <div class="dr-section">
    <div class="dr-title">${isFr ? '✓ Validation Croisée' : '✓ Cross Validation'}</div>
    ${points.map(p=>`<div style="display:flex;gap:6px;margin-bottom:4px;font-size:11px">
      <span style="color:var(--green)">✓</span><span>${p}</span></div>`).join('')}
    ${concerns.map(c=>`<div style="display:flex;gap:6px;margin-bottom:4px;font-size:11px">
      <span style="color:var(--amber)">⚠</span><span>${c}</span></div>`).join('')}
  </div>`;
  }

  // Recommandations prioritaires
  if (rec.length) {
    html += `<div class="dr-section"><div class="dr-title">${isFr?'🎯 Recommandations':'🎯 Recommendations'}</div>`;
    rec.slice(0,4).forEach((r,i) => {
      const action = r.action || '';
      const just   = r.justification || r.reason || '';
      const impact = r.impact_attendu || r.expected_impact || '';
      html += `<div class="dr-reco">
        <div class="dr-reco-num">${isFr?'PRIORITÉ':'PRIORITY'} ${r.priorite||r.priority||i+1}</div>
        <div class="dr-reco-action">${action}</div>
        <div class="dr-reco-why">${just}</div>
        ${impact?`<div class="dr-reco-why" style="color:var(--cyan)">→ ${impact}</div>`:''}
      </div>`;
    });
    html += `</div>`;
  }

  // Prochaines étapes
  const ct = ns.court_terme || ns.short_term || [];
  const mt = ns.moyen_terme || ns.medium_term || [];
  const exp = ns.experiences_suggerees || ns.suggested_experiments || [];
  if (ct.length || mt.length || exp.length) {
    html += `<div class="dr-section"><div class="dr-title">${isFr?'📅 Prochaines Étapes':'📅 Next Steps'}</div>`;
    if (ct.length) {
      html += `<div style="font-size:9px;color:var(--amber);margin:6px 0 3px;text-transform:uppercase;letter-spacing:1px">${isFr?'Court terme':'Short term'}</div>`;
      html += `<ul class="dr-list">${ct.map(s=>`<li>${s}</li>`).join('')}</ul>`;
    }
    if (mt.length) {
      html += `<div style="font-size:9px;color:var(--cyan);margin:8px 0 3px;text-transform:uppercase;letter-spacing:1px">${isFr?'Moyen terme':'Medium term'}</div>`;
      html += `<ul class="dr-list">${mt.map(s=>`<li>${s}</li>`).join('')}</ul>`;
    }
    if (exp.length) {
      html += `<div style="font-size:9px;color:var(--text-muted);margin:8px 0 3px;text-transform:uppercase;letter-spacing:1px">${isFr?'Expériences suggérées':'Suggested experiments'}</div>`;
      html += `<ul class="dr-list">${exp.map(s=>`<li>${s}</li>`).join('')}</ul>`;
    }
    html += `</div>`;
  }

  // Risques
  if (risks.length) {
    html += `<div class="dr-section"><div class="dr-title">⚠ ${isFr?'Risques':'Risks'}</div>`;
    risks.forEach(r => {
      const prob  = r.probabilite || r.probability || 'low';
      const risk  = r.risque || r.risk || '';
      const mit   = r.mitigation || '';
      html += `<div class="dr-risk">
        <span class="dr-risk-badge ${prob.toLowerCase()}">${prob}</span>
        <div><div style="font-size:11px">${risk}</div>
          ${mit?`<div style="font-size:10px;color:var(--text-muted);margin-top:2px">→ ${mit}</div>`:''}
        </div>
      </div>`;
    });
    html += `</div>`;
  }

  // Résumé exécutif
  if (exec) {
    html += `<div class="dr-section">
      <div class="dr-title">${isFr?'📋 Résumé Exécutif':'📋 Executive Summary'}</div>
      <div class="dr-executive">${exec}</div>
    </div>`;
  }

  if (note) {
    html += `<div class="hint" style="margin-top:8px;padding:8px;border:1px dashed var(--border);border-radius:6px">${note}</div>`;
  }

  // Détail des régressions testées (injecté par runQuickDecision)
  if (r._regression_detail) {
    html += `<div class="dr-section">
      <div class="dr-title">📊 ${isFr?'Régressions comparées':'Compared regressions'}</div>
      <div class="hint" style="font-family:var(--font-mono);line-height:1.8">
        ${r._regression_detail.replace(/\|/g,'<br>')}
      </div>
    </div>`;
  }

  el.innerHTML = html;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── Patch pour mettre à jour le statut dès que les données sont chargées ─────
const _origRenderDataPreview = renderDataPreview;
window.renderDataPreview = function(values, startRow) {
  _origRenderDataPreview(values, startRow);
  updatePredictDataStatus();
};

// ── Patch pour cacher resultCache après régression ───────────────────────────
const _origRenderReg = renderRegressionResult;
window.renderRegressionResult = function(res) {
  _origRenderReg(res);
  resultCache.regression = res;
};