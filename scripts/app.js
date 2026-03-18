/**
 * app.js — Orchestrateur principal PhysioAI Lab
 * Coordonne : données, analyse, modèles physiques, simulation, IA, rapport
 */
"use strict";

// ── État global ───────────────────────────────────────────────────────────────
const APP = {
  data:         null,   // { headers, data, sampleNames, dataDict, nRows, nCols }
  colX:         null,   // Nom de la colonne X sélectionnée
  colY:         null,   // Nom de la colonne Y sélectionnée

  // Résultats des analyses
  results: {
    stats:     null,
    corr:      null,
    recommend: null,
    regression: null,
    physics:   null,
    simulation: null,
    ml:        null,
    dl:        null,
    hybrid:    null,
    optimize:  null,
  },

  // Graphiques Chart.js actifs
  charts: {},
};

// ── Init Office ───────────────────────────────────────────────────────────────
Office.onReady(info => {
  if (info.host !== Office.HostType.Excel) {
    setStatus("⚠ Excel requis");
    return;
  }

  setupNav();
  setupInnerTabs();
  setupDataPanel();
  setupAnalyzePanel();
  setupModelPanel();
  setupSimulatePanel();
  setupAIPanel();
  setupReportPanel();
  setupApiUrl();
  checkBackend();

  setStatus("PhysioAI Lab v2.0 ✓");
});

// ── Navigation principale ─────────────────────────────────────────────────────
function setupNav() {
  document.querySelectorAll(".ntab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".ntab, .panel").forEach(el => el.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.panel)?.classList.add("active");
    });
  });
}

// ── Onglets internes ──────────────────────────────────────────────────────────
function setupInnerTabs() {
  document.querySelectorAll(".itab").forEach(tab => {
    tab.addEventListener("click", () => {
      const container = tab.closest("section") || tab.closest(".panel");
      container?.querySelectorAll(".itab, .itab-panel").forEach(el => el.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`itab-${tab.dataset.itab}`)?.classList.add("active");
    });
  });
}

// ── URL API ───────────────────────────────────────────────────────────────────
function setupApiUrl() {
  const input = document.getElementById("api-url");
  input?.addEventListener("change", () => {
    API.setBase(input.value.trim());
    checkBackend();
  });
}

async function checkBackend() {
  const el = document.getElementById("api-status");
  if (!el) return;
  el.className = "api-status checking";
  el.title     = "Vérification…";
  try {
    const h = await API.health();
    el.className = "api-status online";
    el.title     = `Backend OK — PyTorch ${h.libs?.torch || "?"}, sklearn ${h.libs?.sklearn || "?"}`;
    log("Backend connecté ✓", "ok", "log-data");
  } catch {
    el.className = "api-status offline";
    el.title     = "Backend non joignable";
    log("Backend non joignable. Vérifiez que le serveur Python tourne sur " + API._base, "err", "log-data");
  }
}

// ── PANEL : DONNÉES ───────────────────────────────────────────────────────────
function setupDataPanel() {
  document.getElementById("btn-read-excel")?.addEventListener("click", handleReadExcel);
  document.getElementById("csv-file")?.addEventListener("change", handleCSVUpload);
  document.getElementById("btn-confirm-cols")?.addEventListener("click", confirmCols);

  // Changer le type de régression → afficher/masquer les champs
  document.getElementById("reg-type")?.addEventListener("change", e => {
    const t = e.target.value;
    document.getElementById("reg-degree-wrap").style.display = ["polynomial","ridge","lasso"].includes(t) ? "" : "none";
    document.getElementById("reg-alpha-wrap").style.display  = ["ridge","lasso"].includes(t) ? "" : "none";
  });
}

async function handleReadExcel() {
  setBtnLoading("btn-read-excel", true, "Lecture…");
  try {
    const hasHeader = document.getElementById("has-header").value === "1";
    const parsed    = await ExcelIO.readSelection(hasHeader);
    setData(parsed);
    toast(`✅ ${parsed.nRows} × ${parsed.nCols} lus depuis Excel`, "ok");
    log(`Plage ${parsed.address} — ${parsed.nRows} lignes, ${parsed.nCols} variables`, "ok", "log-data");
  } catch (e) {
    toast("Erreur : " + e.message, "err");
    log(e.message, "err", "log-data");
  }
  setBtnLoading("btn-read-excel", false, "⊞ Lire la sélection Excel");
}

async function handleCSVUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  const text   = await file.text();
  const sep    = document.getElementById("csv-sep").value;
  const hasHdr = document.getElementById("has-header").value === "1";
  try {
    const parsed = ExcelIO.parseCSV(text, sep === "\\t" ? "\t" : sep, hasHdr);
    setData(parsed);
    toast(`✅ CSV "${file.name}" — ${parsed.nRows} × ${parsed.nCols}`, "ok");
  } catch (e) {
    toast("Erreur CSV : " + e.message, "err");
  }
}

function setData(parsed) {
  APP.data = parsed;
  APP.results = { stats:null, corr:null, recommend:null, regression:null, physics:null, simulation:null, ml:null, dl:null, hybrid:null, optimize:null };

  renderDataPreview(parsed);
  populateColSelectors(parsed.headers);

  document.getElementById("preview-card")?.style && (document.getElementById("preview-card").style.display = "block");
  document.getElementById("col-assign-card")?.style && (document.getElementById("col-assign-card").style.display = "block");
  document.getElementById("analyze-card")?.style  && (document.getElementById("analyze-card").style.display  = "block");

  document.getElementById("data-shape").textContent = `${parsed.nRows} × ${parsed.nCols}`;

  const info = document.getElementById("data-info");
  if (info) info.innerHTML = [
    `<div class="data-badge">Échantillons : <strong>${parsed.nRows}</strong></div>`,
    `<div class="data-badge">Variables : <strong>${parsed.nCols}</strong></div>`,
    `<div class="data-badge">NaN : <strong>${parsed.data.flat().filter(isNaN).length}</strong></div>`,
  ].join("");

  populatePLSSelectors(parsed.headers);
}

function renderDataPreview(parsed) {
  const MAX_ROWS = 8, MAX_COLS = 8;
  const thead = document.getElementById("preview-thead");
  const tbody = document.getElementById("preview-tbody");
  if (!thead || !tbody) return;

  thead.innerHTML = `<tr><th>#</th>${parsed.headers.slice(0, MAX_COLS).map(h => `<th>${h}</th>`).join("")}${parsed.headers.length > MAX_COLS ? `<th>…</th>` : ""}</tr>`;

  tbody.innerHTML = parsed.data.slice(0, MAX_ROWS).map((row, i) =>
    `<tr><td style="color:var(--faint)">${parsed.sampleNames[i] || i+1}</td>
    ${row.slice(0, MAX_COLS).map(v => `<td>${isNaN(v) ? '<span style="color:var(--orange)">NaN</span>' : v.toFixed(4)}</td>`).join("")}
    ${row.length > MAX_COLS ? `<td style="color:var(--faint)">…</td>` : ""}</tr>`
  ).join("");
}

function populateColSelectors(headers) {
  ["col-x", "col-y"].forEach((id, i) => {
    const sel = document.getElementById(id);
    if (sel) {
      sel.innerHTML = headers.map((h, j) => `<option value="${h}" ${j === i ? "selected" : ""}>${h}</option>`).join("");
    }
  });
  APP.colX = headers[0];
  APP.colY = headers[headers.length - 1];
}

function populatePLSSelectors(headers) {
  const sel = document.getElementById("pls-y-col");
  if (sel) {
    sel.innerHTML = headers.map((h, i) => `<option value="${i}">${h}</option>`).join("");
    sel.value = String(headers.length - 1);
  }
}

function confirmCols() {
  APP.colX = document.getElementById("col-x").value;
  APP.colY = document.getElementById("col-y").value;
  toast(`✅ X = "${APP.colX}", Y = "${APP.colY}"`, "ok");
  log(`Colonnes assignées : X="${APP.colX}", Y="${APP.colY}"`, "ok", "log-data");
}

function getXY() {
  if (!APP.data) throw new Error("Aucune donnée chargée.");
  const colNames = APP.data.headers;
  const idxX = colNames.indexOf(APP.colX);
  const idxY = colNames.indexOf(APP.colY);
  if (idxX < 0 || idxY < 0) throw new Error(`Colonnes X="${APP.colX}" ou Y="${APP.colY}" introuvables.`);
  const x = APP.data.data.map(r => r[idxX]);
  const y = APP.data.data.map(r => r[idxY]);
  return { x, y };
}

// ── PANEL : ANALYSER ──────────────────────────────────────────────────────────
function setupAnalyzePanel() {
  document.getElementById("btn-stats")?.addEventListener("click", handleStats);
  document.getElementById("btn-corr")?.addEventListener("click", handleCorr);
  document.getElementById("btn-recommend")?.addEventListener("click", handleRecommend);
}

async function handleStats() {
  if (!APP.data) { toast("Importez des données d'abord", "warn"); return; }
  setBtnLoading("btn-stats", true, "Calcul…");
  try {
    const res = await API.stats(APP.data.dataDict);
    APP.results.stats = res.results;
    renderStatsTable(res.results);
    document.getElementById("stats-card").style.display = "block";
    toast("✅ Statistiques calculées", "ok");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-stats", false, "📊 Statistiques descriptives");
}

function renderStatsTable(stats) {
  const wrap = document.getElementById("stats-table-wrap");
  if (!wrap) return;
  const cols = Object.keys(stats);
  const fields = ["n","mean","std","min","q1","median","q3","max","skewness","kurtosis","n_outliers"];
  const labels  = ["n","Moyenne","Écart-type","Min","Q1","Médiane","Q3","Max","Skewness","Kurtosis","Outliers"];

  wrap.innerHTML = `<table class="dt">
    <thead><tr><th>Stat</th>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>
    <tbody>${fields.map((f, fi) => `<tr>
      <td style="color:var(--cyan)">${labels[fi]}</td>
      ${cols.map(c => `<td>${_fmt(stats[c]?.[f])}</td>`).join("")}
    </tr>`).join("")}</tbody>
  </table>`;
}

async function handleCorr() {
  if (!APP.data) { toast("Importez des données d'abord", "warn"); return; }
  setBtnLoading("btn-corr", true, "Calcul…");
  try {
    const res = await API.corr(APP.data.dataDict);
    APP.results.corr = res.results;
    renderCorrTable(res.results);
    Charts.renderCorrChart("corr-chart", res.results.columns, res.results.pearson);
    document.getElementById("corr-card").style.display = "block";
    toast("✅ Corrélations calculées", "ok");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-corr", false, "🔗 Corrélations");
}

function renderCorrTable(res) {
  const wrap = document.getElementById("corr-table-wrap");
  if (!wrap || !res.columns) return;
  const cols = res.columns;
  wrap.innerHTML = `<table class="dt">
    <thead><tr><th></th>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>
    <tbody>${cols.map(r => `<tr>
      <td style="color:var(--cyan)">${r}</td>
      ${cols.map(c => {
        const v = res.pearson[r]?.[c];
        const color = v === null ? "var(--faint)" : Math.abs(v) > 0.7 ? "var(--green)" : Math.abs(v) > 0.4 ? "var(--orange)" : "var(--text-dim)";
        return `<td style="color:${color}">${v !== null && v !== undefined ? v.toFixed(3) : "—"}</td>`;
      }).join("")}
    </tr>`).join("")}</tbody>
  </table>`;
}

async function handleRecommend() {
  if (!APP.data) { toast("Importez des données d'abord", "warn"); return; }
  setBtnLoading("btn-recommend", true, "Analyse IA…");
  try {
    const domain = document.getElementById("domain-sel").value;
    const res    = await API.recommend(APP.data.dataDict, APP.colY, domain);
    APP.results.recommend = res;
    renderRecommendation(res);
    document.getElementById("recommend-card").style.display = "block";
    toast("✅ Recommandation IA générée", "ok");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-recommend", false, "✦ Conseil IA");
}

function renderRecommendation(res) {
  const el   = document.getElementById("recommend-content");
  if (!el) return;
  const best = res.best_model;
  const conf = best ? (best.confidence * 100).toFixed(0) + "%" : "?";

  let html = "";
  if (best) {
    html += `<div class="rec-best">
      <div class="rec-title">✦ ${best.model}</div>
      <div class="rec-conf">Confiance : ${conf} · Type : ${best.type}</div>
      <div class="rec-reason">${best.reason}</div>
    </div>`;
  }

  if (res.warnings?.length) {
    html += `<div class="warn-box">⚠ ${res.warnings.join("<br>⚠ ")}</div>`;
  }

  html += `<div class="rec-list">`;
  (res.recommendations || []).slice(1).forEach(r => {
    html += `<div class="rec-item">
      <span class="rec-item-title">${r.model}</span>
      <span class="rec-item-type type-${r.type}">${r.type}</span>
      <div style="font-size:10px;color:var(--text-dim);margin-top:4px">${r.reason}</div>
    </div>`;
  });
  html += `</div>`;

  // Résumé
  const s = res.summary || {};
  html += `<div class="stat-grid mt8">
    ${[["n", s.n],["p", s.p],["R²_lin", _fmt(s.r2_linear)],["R²_RF", _fmt(s.r2_rf)],["Non-linéaire", s.nonlinear?"Oui":"Non"],["Bruit", s.noisy?"Oui":"Non"]].map(([l,v]) => `<div class="stat-item"><div class="stat-lbl">${l}</div><div class="stat-val">${v}</div></div>`).join("")}
  </div>`;

  el.innerHTML = html;
}

// ── PANEL : MODÈLES ───────────────────────────────────────────────────────────
function setupModelPanel() {
  document.getElementById("btn-run-regression")?.addEventListener("click", handleRegression);
  document.getElementById("btn-reg-to-excel")?.addEventListener("click", () => {
    if (APP.results.regression) ExcelIO.exportRegression(APP.results.regression, APP.data?.sampleNames).then(() => toast("✅ Export OK","ok")).catch(e => toast("Erreur : "+e.message,"err"));
  });
  document.getElementById("btn-run-physics")?.addEventListener("click", handlePhysics);
  document.getElementById("btn-phys-to-excel")?.addEventListener("click", () => {
    if (APP.results.physics) ExcelIO.exportPhysics(APP.results.physics, APP.data?.sampleNames).then(() => toast("✅ Export OK","ok")).catch(e => toast("Erreur : "+e.message,"err"));
  });
  document.getElementById("btn-run-optimize")?.addEventListener("click", handleOptimize);
  document.getElementById("btn-auto-optimize")?.addEventListener("click", handleAutoOptimize);

  document.getElementById("phys-model")?.addEventListener("change", e => {
    const m = e.target.value;
    document.getElementById("kinetics-params").style.display  = ["kinetics","batch_reactor","cstr"].includes(m) ? "" : "none";
    document.getElementById("diffusion-params").style.display = m === "diffusion" ? "" : "none";
    document.getElementById("cooling-params").style.display   = m === "cooling" ? "" : "none";
  });
}

async function handleRegression() {
  if (!APP.data) { toast("Importez des données d'abord", "warn"); return; }
  setBtnLoading("btn-run-regression", true, "Calcul…");
  try {
    const { x, y } = getXY();
    const type   = document.getElementById("reg-type").value;
    const degree = parseInt(document.getElementById("reg-degree").value);
    const alpha  = parseFloat(document.getElementById("reg-alpha").value);

    const res = await API.regression(x, y, type, degree, alpha);
    APP.results.regression = res;

    // Métriques
    renderStatGrid("reg-metrics", [["R²", res.r2, "good"], ["RMSE", res.rmse], ["MAE", res.mae],
      ...(res.slope !== undefined ? [["Pente", res.slope],["Intercept", res.intercept]] : [])
    ]);

    // Graphique
    Charts.renderScatterFit("reg-chart", x, y, res.y_pred, res.x_curve, res.y_curve, `Régression ${type}`, APP.colX, APP.colY);
    document.getElementById("reg-results-card").style.display = "block";
    toast(`✅ Régression ${type} : R²=${_fmt(res.r2)}`, "ok");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-run-regression", false, "∿ Lancer la régression");
}

async function handlePhysics() {
  if (!APP.data) { toast("Importez des données d'abord", "warn"); return; }
  setBtnLoading("btn-run-physics", true, "Calcul…");
  try {
    const model   = document.getElementById("phys-model").value;
    const calib   = document.getElementById("p-calibrate").value === "1";
    const t_end   = parseFloat(document.getElementById("p-tend").value);
    const { x: t, y: C } = getXY();

    let payload = { model };

    if (["kinetics", "batch_reactor", "cstr"].includes(model)) {
      payload = {
        ...payload,
        order:    parseInt(document.getElementById("k-order").value),
        C0_guess: parseFloat(document.getElementById("k-c0").value),
        k_guess:  parseFloat(document.getElementById("k-k").value),
        t_end,
        ...(calib ? { t, C } : {}),
      };
    } else if (model === "diffusion") {
      payload = {
        ...payload,
        D:        parseFloat(document.getElementById("d-D").value),
        C_surface: parseFloat(document.getElementById("d-cs").value),
        x_max:    parseFloat(document.getElementById("d-xmax").value),
      };
    } else if (model === "cooling") {
      payload = {
        ...payload,
        T0: parseFloat(document.getElementById("c-T0").value),
        T_env: parseFloat(document.getElementById("c-Tenv").value),
        h: parseFloat(document.getElementById("c-h").value),
        t_end,
        ...(calib ? { t_obs: t, T_data: C } : {}),
      };
    }

    const res = await API.physics(payload);
    APP.results.physics = res;

    const metricsArr = [["Modèle", res.model]];
    if (res.params?.k !== undefined)  metricsArr.push(["k", res.params.k]);
    if (res.params?.C0 !== undefined) metricsArr.push(["C₀", res.params.C0]);
    if (res.r2 !== null && res.r2 !== undefined) metricsArr.push(["R²", res.r2]);
    if (res.half_life) metricsArr.push(["Demi-vie", res.half_life]);
    renderStatGrid("phys-metrics", metricsArr.map(([l, v]) => [l, _fmt(typeof v === "number" ? v : v), "good"]));

    // Graphique
    const simCurve = { t: res.t_sim || res.t || [], y: res.C_sim || res.T_sim || [], label: "Modèle physique", isData: false };
    const dataCurve = (res.t_obs && res.C_obs) ? { t: res.t_obs, y: res.C_obs, label: "Données", isData: true } : null;
    Charts.renderTimeSeries("phys-chart", [simCurve, ...(dataCurve ? [dataCurve] : [])], res.model, "t", "C ou T");

    document.getElementById("phys-results-card").style.display = "block";
    toast(`✅ Modèle ${model} calculé${res.r2 ? ` (R²=${_fmt(res.r2)})` : ""}`, "ok");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-run-physics", false, "⚙ Calculer");
}

async function handleOptimize() {
  if (!APP.data) { toast("Importez des données d'abord", "warn"); return; }
  setBtnLoading("btn-run-optimize", true, "Optimisation…");
  try {
    const method = document.getElementById("opt-method").value;
    const model  = document.getElementById("opt-model").value;
    const { x, y } = getXY();

    const res = await API.calibrate({
      physics_model: model.startsWith("kinetics") ? "kinetics" : "cooling",
      x_data:  x, y_data: y,
      param_names: ["C0","k"],
      p0: [parseFloat(document.getElementById("k-c0").value), parseFloat(document.getElementById("k-k").value)],
      bounds_min: [0, 1e-6], bounds_max: [100, 100],
      method,
    });
    APP.results.optimize = res;

    const el = document.getElementById("opt-params-display");
    if (el) el.innerHTML = Object.entries(res.params).map(([k, v]) =>
      `<div class="opt-param-row"><span>${k}</span><span>${_fmt(v, 6)}</span></div>`
    ).join("") + `<div class="opt-param-row"><span>R²</span><span>${_fmt(res.r2, 4)}</span></div>`;

    Charts.renderScatterFit("opt-chart", x, y, res.y_pred, null, null, `Calibration ${method}`, APP.colX, APP.colY);
    document.getElementById("opt-results-card").style.display = "block";
    toast(`✅ Calibration terminée : R²=${_fmt(res.r2)}`, "ok");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-run-optimize", false, "⚡ Calibrer");
}

async function handleAutoOptimize() {
  if (!APP.data) { toast("Importez des données d'abord", "warn"); return; }
  setBtnLoading("btn-auto-optimize", true, "Auto-sélection…");
  try {
    const { x, y } = getXY();
    const res = await API.autoOptimize(x, y, "kinetics", "curve_fit");
    if (res.best) {
      toast(`✅ Meilleur modèle : ${res.best.model} (R²=${_fmt(res.best.r2)})`, "ok");
      const el = document.getElementById("opt-params-display");
      if (el) el.innerHTML = `<div class="rec-best">
        <div class="rec-title">✦ ${res.best.model}</div>
        <div class="rec-conf">R² = ${_fmt(res.best.r2, 4)}</div>
      </div>` + Object.entries(res.best.params || {}).map(([k, v]) =>
        `<div class="opt-param-row"><span>${k}</span><span>${_fmt(v, 6)}</span></div>`
      ).join("");
      document.getElementById("opt-results-card").style.display = "block";
    }
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-auto-optimize", false, "🔁 Auto-sélection meilleur modèle");
}

// ── PANEL : SIMULATION ────────────────────────────────────────────────────────
function setupSimulatePanel() {
  document.getElementById("btn-run-sim")?.addEventListener("click", handleSimulate);
  document.getElementById("btn-run-sim-multi")?.addEventListener("click", handleSimulateMulti);
  document.getElementById("btn-sim-to-excel")?.addEventListener("click", () => {
    if (APP.results.simulation) ExcelIO.exportSimulation(APP.results.simulation).then(() => toast("✅ Export OK","ok")).catch(e => toast("Erreur : "+e.message,"err"));
  });
}

async function handleSimulate() {
  setBtnLoading("btn-run-sim", true, "Simulation…");
  try {
    const model    = document.getElementById("sim-model").value;
    const t_start  = parseFloat(document.getElementById("sim-tstart").value);
    const t_end    = parseFloat(document.getElementById("sim-tend").value);
    const n_points = parseInt(document.getElementById("sim-npts").value);
    const C0       = parseFloat(document.getElementById("sim-c0").value);
    const k        = parseFloat(document.getElementById("sim-k").value);
    const order    = parseInt(document.getElementById("sim-order").value);

    const params = { C0, k, order, T0: C0, V: 1.0, D: 1e-9, T_env: 20 };
    const compare = document.getElementById("sim-compare").value === "1" && APP.data;
    const comp_with = compare && APP.colX && APP.colY ? {
      t: APP.data.dataDict[APP.colX],
      y: APP.data.dataDict[APP.colY],
    } : null;

    const res = await API.simulate(model, params, t_start, t_end, n_points, comp_with);
    APP.results.simulation = res;

    const curves = [{ t: res.t_sim || res.t || [], y: res.C_sim || res.T_sim || res.C || [], label: "Simulation", isData: false }];
    if (comp_with) curves.push({ t: comp_with.t, y: comp_with.y, label: "Données", isData: true });
    Charts.renderTimeSeries("sim-chart", curves, `Simulation — ${model}`, "t", "C");

    const metrics = [];
    if (res.conversion) metrics.push(["Conversion finale", res.conversion[res.conversion.length-1]]);
    if (res.params?.k)  metrics.push(["k", res.params.k]);
    if (res.r2)         metrics.push(["R²", res.r2]);
    renderStatGrid("sim-metrics", metrics.map(([l,v]) => [l, _fmt(v), "good"]));

    document.getElementById("sim-results-card").style.display = "block";
    toast("✅ Simulation terminée", "ok");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-run-sim", false, "▶ Lancer la simulation");
}

async function handleSimulateMulti() {
  setBtnLoading("btn-run-sim-multi", true, "Simulation…");
  try {
    const kValues = document.getElementById("sim-multi-k").value.split(";").map(Number).filter(isFinite);
    const C0      = parseFloat(document.getElementById("sim-multi-c0").value);
    const t_end   = parseFloat(document.getElementById("sim-tend").value) || 100;
    const n_pts   = 200;

    // Simuler en parallèle côté client (appels API séquentiels)
    const curves = [];
    for (const k of kValues) {
      try {
        const res = await API.simulate("kinetics", { C0, k, order: 1 }, 0, t_end, n_pts);
        curves.push({ t: res.t_sim, y: res.C_sim, label: `k = ${k}`, isData: false });
      } catch {}
    }

    if (curves.length > 0) {
      const wrap = document.getElementById("sim-multi-wrap");
      if (wrap) wrap.style.display = "block";
      Charts.renderTimeSeries("sim-multi-chart", curves, "Comparaison cinétique (ordre 1)", "t", "C(t)");
      toast(`✅ ${curves.length} courbes simulées`, "ok");
    }
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-run-sim-multi", false, "▶▶ Simulation comparative");
}

// ── PANEL : IA/DL ─────────────────────────────────────────────────────────────
function setupAIPanel() {
  document.getElementById("btn-run-ml")?.addEventListener("click", handleML);
  document.getElementById("btn-run-dl")?.addEventListener("click", handleDL);
  document.getElementById("btn-run-hybrid")?.addEventListener("click", handleHybrid);

  document.getElementById("ml-model")?.addEventListener("change", e => {
    document.getElementById("ml-n-est-wrap").style.display  = e.target.value !== "kmeans" ? "" : "none";
    document.getElementById("ml-k-wrap").style.display      = e.target.value === "kmeans" ? "" : "none";
  });
}

async function handleML() {
  if (!APP.data) { toast("Importez des données d'abord", "warn"); return; }
  setBtnLoading("btn-run-ml", true, "Entraînement…");
  try {
    const model = document.getElementById("ml-model").value;
    const k_val = document.getElementById("ml-k").value;
    const { x, y } = getXY();
    const X = x.map(v => [v]);  // 1 feature pour simplifier

    const payload = {
      X, y: model === "kmeans" ? x : y,
      model,
      n_estimators: parseInt(document.getElementById("ml-n-est").value),
      cv_folds:     parseInt(document.getElementById("ml-cv").value),
      k:            k_val ? parseInt(k_val) : null,
    };

    const res = await API.trainML(payload);
    APP.results.ml = res;

    renderStatGrid("ml-metrics", [
      ["R²",      res.r2,        "good"],
      ["RMSE",    res.rmse],
      ["CV R²",   res.cv_r2,     "good"],
      ["OOB",     res.oob_score, "good"],
      ["Silhouette", res.silhouette],
    ].filter(([,v]) => v !== null && v !== undefined));

    if (res.y_pred && res.y_true) {
      Charts.renderPredVsReal("ml-chart", res.y_true, res.y_pred, `${model} — Prédit vs Réel`);
    }
    if (res.feature_importance) {
      document.getElementById("feat-imp-wrap").style.display = "block";
      Charts.renderFeatureImportance("feat-imp-chart", APP.data.headers, res.feature_importance);
    }

    document.getElementById("ml-results-card").style.display = "block";
    toast(`✅ ${model} : R²=${_fmt(res.r2)}`, "ok");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-run-ml", false, "✦ Entraîner");
}

async function handleDL() {
  if (!APP.data) { toast("Importez des données d'abord", "warn"); return; }
  setBtnLoading("btn-run-dl", true, "Entraînement DL…");
  try {
    const hidden = document.getElementById("dl-hidden").value.split(",").map(Number).filter(n => n > 0);
    const { x, y } = getXY();

    const res = await API.trainDL({
      X:            x.map(v => [v]),
      y,
      model:        document.getElementById("dl-arch").value,
      hidden_dims:  hidden,
      activation:   document.getElementById("dl-act").value,
      dropout:      parseFloat(document.getElementById("dl-dropout").value),
      lr:           parseFloat(document.getElementById("dl-lr").value),
      epochs:       parseInt(document.getElementById("dl-epochs").value),
      patience:     parseInt(document.getElementById("dl-patience").value),
    });
    APP.results.dl = res;

    renderStatGrid("dl-metrics", [["R²", res.r2,"good"],["RMSE", res.rmse],["MAE", res.mae],["Epochs", res.epochs_done],["Temps (s)", res.training_time?.toFixed(1)]]);
    Charts.renderPredVsReal("dl-pred-chart", res.y_true, res.y_pred, "DL — Prédit vs Réel");
    Charts.renderLossCurve("dl-loss-chart", res.history?.epoch, res.history?.train_loss, "Courbe de perte");

    document.getElementById("dl-results-card").style.display = "block";
    toast(`✅ DL entraîné : R²=${_fmt(res.r2)}, ${res.epochs_done} epochs`, "ok");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-run-dl", false, "⚡ Entraîner le réseau");
}

async function handleHybrid() {
  if (!APP.data) { toast("Importez des données d'abord", "warn"); return; }
  setBtnLoading("btn-run-hybrid", true, "Modèle hybride…");
  try {
    const { x, y } = getXY();
    const hidden = document.getElementById("hyb-hidden").value.split(",").map(Number).filter(n => n > 0);

    const res = await API.trainDL({
      X: x.map(v => [v]),
      y,
      model:          "hybrid",
      physics_model:  "kinetics",
      physics_params: {
        C0:    parseFloat(document.getElementById("hyb-c0").value),
        k:     parseFloat(document.getElementById("hyb-k").value),
        order: 1,
      },
      hidden_dims: hidden,
      epochs: parseInt(document.getElementById("hyb-epochs").value),
      patience: 30,
    });
    APP.results.hybrid = res;

    renderStatGrid("hyb-metrics", [
      ["R² hybride",   res.r2,              "good"],
      ["R² physique",  res.r2_physics_only, "good"],
      ["Gain IA",      _fmt(res.r2 - res.r2_physics_only)],
      ["RMSE",         res.rmse],
    ]);

    Charts.renderHybridChart("hyb-chart", x, res.y_true, res.y_physics, res.y_pred_hybrid || res.y_pred);
    document.getElementById("hyb-results-card").style.display = "block";
    toast(`✅ Hybride : R²=${_fmt(res.r2)} (physique seul : ${_fmt(res.r2_physics_only)})`, "ok");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-run-hybrid", false, "⚗ Entraîner modèle hybride");
}

// ── PANEL : RAPPORT ───────────────────────────────────────────────────────────
function setupReportPanel() {
  document.getElementById("btn-gen-report")?.addEventListener("click", handleGenerateReport);
  document.getElementById("btn-export-excel")?.addEventListener("click", handleExportAll);
}

async function handleGenerateReport() {
  setBtnLoading("btn-gen-report", true, "Génération…");
  try {
    const r = APP.results;
    const opts = {
      title:   document.getElementById("rpt-title").value,
      author:  document.getElementById("rpt-author").value,
      org:     document.getElementById("rpt-org").value,
      ref:     document.getElementById("rpt-ref").value,
      stats:   document.getElementById("rpt-stats").checked,
      corr:    document.getElementById("rpt-corr").checked,
      model:   document.getElementById("rpt-model").checked,
      sim:     document.getElementById("rpt-sim").checked,
      ai:      document.getElementById("rpt-ai-sec").checked,
      rec:     document.getElementById("rpt-rec").checked,
    };

    const html = buildHTMLReport(opts, r);
    downloadHTML(html, `PhysioAI_Rapport_${new Date().toISOString().slice(0,10)}.html`);
    toast("✅ Rapport HTML téléchargé", "ok");
    log("Rapport généré", "ok", "log-report");
  } catch (e) { toast("Erreur : " + e.message, "err"); }
  setBtnLoading("btn-gen-report", false, "📄 Générer rapport HTML");
}

async function handleExportAll() {
  const r = APP.results;
  const tasks = [];
  if (r.regression) tasks.push(ExcelIO.exportRegression(r.regression, APP.data?.sampleNames));
  if (r.physics)    tasks.push(ExcelIO.exportPhysics(r.physics, APP.data?.sampleNames));
  if (r.simulation) tasks.push(ExcelIO.exportSimulation(r.simulation));
  if (r.ml)         tasks.push(ExcelIO.exportML(r.ml, APP.data?.headers, APP.data?.sampleNames));
  if (tasks.length === 0) { toast("Aucun résultat à exporter", "warn"); return; }
  try {
    for (const t of tasks) await t;
    toast(`✅ ${tasks.length} feuille(s) exportée(s)`, "ok");
  } catch (e) { toast("Erreur export : " + e.message, "err"); }
}

function buildHTMLReport(opts, results) {
  const date = new Date().toLocaleDateString("fr-FR", {year:"numeric",month:"long",day:"numeric"});
  const r = results;

  const section = (title, content) => content ? `<section class="s"><h2>${title}</h2>${content}</section>` : "";
  const statRow = items => `<div class="sg">${items.map(([l,v]) => `<div class="si"><div class="sl">${l}</div><div class="sv">${v ?? "—"}</div></div>`).join("")}</div>`;

  return `<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>${opts.title || "Rapport PhysioAI Lab"}</title>
<style>
body{font-family:'Segoe UI',sans-serif;font-size:12px;background:#050D1A;color:#C8DCF0;padding:28px 36px;max-width:1100px;margin:auto}
h1{font-size:22px;color:#00FFB3;border-bottom:2px solid #00FFB3;padding-bottom:8px;margin-bottom:8px}
h2{font-size:12px;font-weight:700;color:#6B8DAA;margin:22px 0 10px;padding:7px 12px;background:#091422;border-left:4px solid #00FFB3;border-radius:4px;text-transform:uppercase;letter-spacing:.06em}
.meta{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;background:#091422;border-radius:8px;padding:14px;margin:14px 0}
.ml{font-size:8px;color:#2A4060;text-transform:uppercase;letter-spacing:.05em}.mv{font-size:12px;font-weight:700;color:#00FFB3;margin-top:2px}
.sg{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.si{background:#0E1D30;border-radius:5px;padding:8px 12px;text-align:center;min-width:90px}
.sl{font-size:8px;color:#2A4060;text-transform:uppercase}.sv{font-size:13px;font-weight:700;color:#00FFB3;margin-top:2px}
table{width:100%;border-collapse:collapse;margin:8px 0;font-size:11px}
th{background:#050D1A;color:#00D4FF;padding:5px 8px;text-align:left;font-size:9px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #152840}
td{padding:4px 8px;border-bottom:1px solid #152840;color:#6B8DAA}
.footer{margin-top:30px;padding-top:10px;border-top:1px solid #152840;font-size:10px;color:#2A4060;text-align:center}
.s{margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid #152840}
</style></head><body>
<h1>${opts.title || "Rapport PhysioAI Lab"}</h1>
<div class="meta">
  ${[["Auteur",opts.author||"—"],["Organisation",opts.org||"—"],["Référence",opts.ref||"—"],["Date",date],
    ["Échantillons",APP.data?.nRows||"—"],["Variables",APP.data?.nCols||"—"],["Backend","FastAPI + PyTorch"],["Version","2.0.0"]]
    .map(([l,v])=>`<div><div class="ml">${l}</div><div class="mv">${v}</div></div>`).join("")}
</div>

${opts.stats && r.stats ? section("Statistiques descriptives", `<p>Analyse de ${Object.keys(r.stats).length} variable(s).</p>`) : ""}
${opts.model && r.regression ? section("Régression", statRow([["Type",r.regression.type],["R²",_fmt(r.regression.r2,4)],["RMSE",_fmt(r.regression.rmse,4)],["MAE",_fmt(r.regression.mae,4)]])) : ""}
${opts.model && r.physics ? section("Modèle physique", statRow(Object.entries(r.physics.params||{}).map(([k,v])=>[k,_fmt(v,4)]).concat([["R²",_fmt(r.physics.r2,4)]]))) : ""}
${opts.ai && r.ml ? section("Machine Learning", statRow([["Modèle",r.ml.model],["R²",_fmt(r.ml.r2,4)],["RMSE",_fmt(r.ml.rmse,4)],["CV R²",_fmt(r.ml.cv_r2,4)]])) : ""}
${opts.ai && r.dl ? section("Deep Learning", statRow([["Architecture",r.dl.architecture?.join("→")||"?"],["R²",_fmt(r.dl.r2,4)],["RMSE",_fmt(r.dl.rmse,4)],["Epochs",r.dl.epochs_done]])) : ""}
${opts.ai && r.hybrid ? section("Modèle hybride", statRow([["R² hybride",_fmt(r.hybrid.r2,4)],["R² physique",_fmt(r.hybrid.r2_physics_only,4)],["Gain IA",_fmt(r.hybrid.r2-(r.hybrid.r2_physics_only||0),4)]])) : ""}
${opts.rec && r.recommend?.best_model ? section("Recommandation IA", `<p><strong>${r.recommend.best_model.model}</strong> — Confiance : ${(r.recommend.best_model.confidence*100).toFixed(0)}%</p><p>${r.recommend.best_model.reason}</p>`) : ""}

<div class="footer">Rapport généré par <strong>PhysioAI Lab v2.0</strong> — ${date} | FastAPI + PyTorch + scikit-learn</div>
</body></html>`;
}

// ── Utilitaires ───────────────────────────────────────────────────────────────
function _fmt(v, d = 4) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") {
    if (!isFinite(v)) return "—";
    return parseFloat(v.toFixed(d)).toString();
  }
  return String(v);
}

function renderStatGrid(containerId, items) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = items.filter(([,v]) => v !== null && v !== undefined).map(([l, v, cls]) =>
    `<div class="stat-item"><div class="stat-lbl">${l}</div><div class="stat-val ${cls||""}">${_fmt(v)}</div></div>`
  ).join("");
}

function toast(msg, type, dur = 3500) {
  const el  = document.createElement("div");
  el.className = `toast ${type || "info"}`;
  el.innerHTML = `<span>${{ok:"✅",err:"❌",info:"ℹ",warn:"⚠"}[type]||"ℹ"}</span><span>${msg}</span>`;
  document.getElementById("toast-ct")?.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 250); }, dur);
}

function log(msg, type = "info", containerId = "log-data") {
  const el = document.getElementById(containerId);
  if (!el) return;
  const e = document.createElement("div");
  e.className = `le ${type}`;
  e.innerHTML = `<span class="ts">${new Date().toLocaleTimeString("fr-FR")}</span>${msg}`;
  el.appendChild(e);
  el.scrollTop = el.scrollHeight;
}

function setStatus(msg) {
  const el = document.getElementById("api-status");
  if (el) el.title = msg;
}

function setBtnLoading(id, loading, label) {
  const btn = document.getElementById(id);
  if (!btn) return;
  btn.disabled = loading;
  btn.innerHTML = loading ? `<span class="spinner"></span> ${label}` : label;
}

function downloadHTML(html, filename) {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
