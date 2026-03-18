/**
 * charts.js — Moteur de graphiques Chart.js pour PhysioAI Lab
 * Thème sombre cohérent avec l'interface principale.
 */
"use strict";

const CHART_COLORS = {
  green:  "#00FFB3",
  cyan:   "#00D4FF",
  blue:   "#3B82F6",
  orange: "#FF8C00",
  red:    "#FF4444",
  purple: "#B57FFF",
  yellow: "#FFD700",
  teal:   "#00B4A0",
};

const PALETTE = Object.values(CHART_COLORS);

// Store des instances de graphiques pour destroy() avant re-render
const _charts = {};

function _destroy(id) {
  if (_charts[id]) {
    _charts[id].destroy();
    delete _charts[id];
  }
}

function _baseOptions(title = "", xLabel = "x", yLabel = "y") {
  return {
    responsive:          true,
    maintainAspectRatio: false,
    animation:           { duration: 400 },
    plugins: {
      legend: {
        labels: { color: "#6B8DAA", font: { family: "JetBrains Mono", size: 10 } },
      },
      title: title ? {
        display: true, text: title,
        color: "#00FFB3",
        font: { family: "DM Sans", size: 12, weight: "700" },
        padding: { bottom: 8 },
      } : { display: false },
      tooltip: {
        backgroundColor: "#0E1D30",
        borderColor:      "#152840",
        borderWidth:      1,
        titleColor:       "#C8DCF0",
        bodyColor:        "#6B8DAA",
        titleFont:        { family: "JetBrains Mono", size: 10 },
        bodyFont:         { family: "JetBrains Mono", size: 10 },
      },
    },
    scales: {
      x: {
        title: { display: true, text: xLabel, color: "#6B8DAA", font: { size: 10 } },
        ticks: { color: "#6B8DAA", font: { family: "JetBrains Mono", size: 9 } },
        grid:  { color: "#152840" },
      },
      y: {
        title: { display: true, text: yLabel, color: "#6B8DAA", font: { size: 10 } },
        ticks: { color: "#6B8DAA", font: { family: "JetBrains Mono", size: 9 } },
        grid:  { color: "#152840" },
      },
    },
  };
}

/** Graphique scatter + ligne de fit */
function renderScatterFit(canvasId, x, y_true, y_pred = null, x_curve = null, y_curve = null, title = "", xLabel = "x", yLabel = "y") {
  _destroy(canvasId);
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  const datasets = [{
    label:           "Données",
    data:            x.map((xi, i) => ({ x: xi, y: y_true[i] })),
    type:            "scatter",
    backgroundColor: CHART_COLORS.cyan + "BB",
    pointRadius:     4,
    pointHoverRadius: 6,
  }];

  if (y_pred) {
    datasets.push({
      label:       "Modèle (points obs.)",
      data:        x.map((xi, i) => ({ x: xi, y: y_pred[i] })),
      type:        "scatter",
      borderColor: CHART_COLORS.orange,
      backgroundColor: "transparent",
      pointRadius: 3,
      pointStyle:  "cross",
    });
  }

  if (x_curve && y_curve) {
    datasets.push({
      label:       "Courbe ajustée",
      data:        x_curve.map((xi, i) => ({ x: xi, y: y_curve[i] })),
      type:        "line",
      borderColor: CHART_COLORS.green,
      borderWidth: 2,
      pointRadius: 0,
      fill:        false,
      tension:     0.4,
    });
  }

  _charts[canvasId] = new Chart(ctx, {
    type: "scatter",
    data: { datasets },
    options: { ..._baseOptions(title, xLabel, yLabel) },
  });
}

/** Graphique prédit vs réel */
function renderPredVsReal(canvasId, y_true, y_pred, title = "Prédit vs Réel") {
  _destroy(canvasId);
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  const allVals = [...y_true, ...y_pred].filter(isFinite);
  const lo = Math.min(...allVals), hi = Math.max(...allVals);
  const perfect = [{ x: lo, y: lo }, { x: hi, y: hi }];

  _charts[canvasId] = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label:           "Prédictions",
          data:            y_true.map((yt, i) => ({ x: yt, y: y_pred[i] })),
          backgroundColor: CHART_COLORS.green + "AA",
          pointRadius:     4,
        },
        {
          label:       "Idéal (y = x)",
          data:        perfect,
          type:        "line",
          borderColor: CHART_COLORS.orange,
          borderWidth: 1,
          borderDash:  [4, 4],
          pointRadius: 0,
          fill:        false,
        },
      ],
    },
    options: _baseOptions(title, "y réel", "y prédit"),
  });
}

/** Graphique de simulation temporelle (multi-courbes) */
function renderTimeSeries(canvasId, curves, title = "", xLabel = "t", yLabel = "C") {
  _destroy(canvasId);
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  const datasets = curves.map((curve, i) => ({
    label:       curve.label || `Courbe ${i+1}`,
    data:        curve.t.map((ti, j) => ({ x: ti, y: curve.y[j] })),
    type:        "line",
    borderColor: PALETTE[i % PALETTE.length],
    borderWidth: curve.isData ? 0 : 2,
    pointRadius: curve.isData ? 4 : 0,
    backgroundColor: curve.isData ? (PALETTE[i % PALETTE.length] + "AA") : "transparent",
    fill:        false,
    tension:     0.3,
    showLine:    !curve.isData,
  }));

  _charts[canvasId] = new Chart(ctx, {
    type: "line",
    data: { datasets },
    options: { ..._baseOptions(title, xLabel, yLabel) },
  });
}

/** Graphique d'importance des features (barres horizontales) */
function renderFeatureImportance(canvasId, names, importance, title = "VIP / Importance") {
  _destroy(canvasId);
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  // Trier par importance décroissante
  const order = importance.map((v, i) => ({ v, i })).sort((a, b) => b.v - a.v).slice(0, 15);
  const sortedNames = order.map(o => names[o.i] || `V${o.i+1}`);
  const sortedVals  = order.map(o => o.v);

  _charts[canvasId] = new Chart(ctx, {
    type: "bar",
    data: {
      labels:   sortedNames,
      datasets: [{
        label:            "Importance",
        data:             sortedVals,
        backgroundColor:  sortedVals.map(v => v >= 1 ? CHART_COLORS.orange : CHART_COLORS.cyan),
        borderRadius:     3,
      }],
    },
    options: {
      ..._baseOptions(title, "Variable", "Importance"),
      indexAxis: "y",
    },
  });
}

/** Courbe de loss (entraînement DL) */
function renderLossCurve(canvasId, epochs, losses, title = "Courbe de perte") {
  _destroy(canvasId);
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  _charts[canvasId] = new Chart(ctx, {
    type: "line",
    data: {
      labels:   epochs,
      datasets: [{
        label:       "Train Loss",
        data:        losses,
        borderColor: CHART_COLORS.purple,
        borderWidth: 2,
        pointRadius: 0,
        fill:        true,
        backgroundColor: CHART_COLORS.purple + "22",
        tension:     0.3,
      }],
    },
    options: { ..._baseOptions(title, "Epoch", "Loss (MSE)") },
  });
}

/** Heatmap de corrélation (simulée avec Chart.js) */
function renderCorrChart(canvasId, cols, corrMatrix) {
  _destroy(canvasId);
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  // Paires de corrélations
  const labels   = cols;
  const datasets = cols.map((c1, i) => ({
    label:           c1,
    data:            cols.map(c2 => ({ x: c2, y: Math.abs(corrMatrix[c1]?.[c2] ?? 0) })),
    backgroundColor: PALETTE[i % PALETTE.length] + "BB",
  }));

  // Simplification : graphique à barres groupées (corrélations vs c1)
  const xLabels = cols;
  const ds = cols.map((c1, i) => ({
    label:           c1,
    data:            cols.map(c2 => parseFloat((corrMatrix[c1]?.[c2] ?? 0).toFixed(3))),
    backgroundColor: PALETTE[i % PALETTE.length] + "99",
    borderRadius:    2,
  }));

  _charts[canvasId] = new Chart(ctx, {
    type: "bar",
    data: { labels: xLabels, datasets: ds },
    options: {
      ..._baseOptions("Corrélations de Pearson", "Variable", "r"),
      scales: {
        ..._baseOptions().scales,
        y: { ..._baseOptions().scales.y, min: -1, max: 1 },
      },
    },
  });
}

/** Graphique hybride : physique + résidu NN + total */
function renderHybridChart(canvasId, t, y_true, y_physics, y_hybrid) {
  _destroy(canvasId);
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  _charts[canvasId] = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label:           "Données",
          data:            t.map((ti, i) => ({ x: ti, y: y_true[i] })),
          backgroundColor: CHART_COLORS.cyan + "BB",
          pointRadius:     4,
        },
        {
          label:       "Modèle physique seul",
          data:        t.map((ti, i) => ({ x: ti, y: y_physics[i] })),
          type:        "line",
          borderColor: CHART_COLORS.orange,
          borderWidth: 2,
          pointRadius: 0,
          borderDash:  [5, 3],
          fill:        false,
        },
        {
          label:       "Modèle hybride (Physique + NN)",
          data:        t.map((ti, i) => ({ x: ti, y: y_hybrid[i] })),
          type:        "line",
          borderColor: CHART_COLORS.green,
          borderWidth: 2,
          pointRadius: 0,
          fill:        false,
        },
      ],
    },
    options: _baseOptions("Modèle hybride vs données", "t", "C"),
  });
}

window.Charts = {
  renderScatterFit, renderPredVsReal, renderTimeSeries,
  renderFeatureImportance, renderLossCurve, renderCorrChart, renderHybridChart,
};
