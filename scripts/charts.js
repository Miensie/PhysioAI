/**
 * PhysioAI Lab — Module Graphiques (Chart.js)
 * Gestion des graphiques dynamiques avec thème sombre
 */

// ─── Thème global Chart.js ────────────────────────────────────────────────────
Chart.defaults.color = "#8b949e";
Chart.defaults.borderColor = "#30363d";
Chart.defaults.font.family = "'IBM Plex Mono', monospace";
Chart.defaults.font.size = 10;

const COLORS = {
  cyan: "rgba(57, 208, 216, 1)",
  cyanFill: "rgba(57, 208, 216, 0.12)",
  amber: "rgba(240, 160, 0, 1)",
  amberFill: "rgba(240, 160, 0, 0.12)",
  green: "rgba(63, 185, 80, 1)",
  greenFill: "rgba(63, 185, 80, 0.12)",
  purple: "rgba(188, 140, 255, 1)",
  red: "rgba(248, 81, 73, 1)",
  redFill: "rgba(248, 81, 73, 0.12)",
};

// Registre des instances Chart.js (pour destruction propre)
const chartRegistry = {};

function destroyChart(id) {
  if (chartRegistry[id]) {
    chartRegistry[id].destroy();
    delete chartRegistry[id];
  }
}

function baseOptions(title = "", xLabel = "x", yLabel = "y") {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 400, easing: "easeOutQuart" },
    plugins: {
      legend: { display: true, position: "top", labels: { usePointStyle: true, pointStyleWidth: 8 } },
      title: title ? { display: true, text: title, color: "#e6edf3", font: { size: 12, weight: "600" } } : { display: false },
      tooltip: {
        backgroundColor: "#1c2230",
        borderColor: "#30363d",
        borderWidth: 1,
        titleColor: "#e6edf3",
        bodyColor: "#8b949e",
        callbacks: {
          label: (ctx) => ` ${ctx.dataset.label}: ${Number(ctx.raw).toFixed(4)}`,
        },
      },
    },
    scales: {
      x: {
        title: { display: true, text: xLabel, color: "#8b949e" },
        grid: { color: "#21262d" },
        ticks: { maxTicksLimit: 8 },
      },
      y: {
        title: { display: true, text: yLabel, color: "#8b949e" },
        grid: { color: "#21262d" },
        ticks: { maxTicksLimit: 6 },
      },
    },
  };
}

// ─── Graphique: données brutes ────────────────────────────────────────────────
function renderRawData(canvasId, x, y, xLabel, yLabel) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId).getContext("2d");

  const chart = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [{
        label: "Données expérimentales",
        data: x.map((xi, i) => ({ x: xi, y: y[i] })),
        backgroundColor: COLORS.cyan,
        pointRadius: 4,
        pointHoverRadius: 6,
      }],
    },
    options: {
      ...baseOptions("Données brutes", xLabel, yLabel),
      plugins: { ...baseOptions("", xLabel, yLabel).plugins, legend: { display: false } },
    },
  });

  chartRegistry[canvasId] = chart;
  return chart;
}

// ─── Graphique: régression ────────────────────────────────────────────────────
function renderRegressionChart(canvasId, xData, yData, curveX, curveY, modelType, xLabel, yLabel) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId).getContext("2d");

  const chart = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Données expérimentales",
          data: xData.map((xi, i) => ({ x: xi, y: yData[i] })),
          backgroundColor: COLORS.cyan,
          pointRadius: 5,
          pointHoverRadius: 7,
          order: 2,
        },
        {
          label: `Modèle (${modelType})`,
          data: curveX.map((xi, i) => ({ x: xi, y: curveY[i] })),
          type: "line",
          borderColor: COLORS.amber,
          backgroundColor: "transparent",
          borderWidth: 2.5,
          pointRadius: 0,
          tension: 0.3,
          order: 1,
        },
      ],
    },
    options: baseOptions("Ajustement du modèle", xLabel, yLabel),
  });

  chartRegistry[canvasId] = chart;
  return chart;
}

// ─── Graphique: simulation physique ──────────────────────────────────────────
function renderPhysicsChart(canvasId, t, y, expT = null, expY = null, modelType = "") {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId).getContext("2d");

  const datasets = [
    {
      label: `Simulation — ${modelType}`,
      data: t.map((ti, i) => ({ x: ti, y: y[i] })),
      type: "line",
      borderColor: COLORS.purple,
      backgroundColor: "transparent",
      borderWidth: 2.5,
      pointRadius: 0,
      tension: 0.2,
    },
  ];

  if (expT && expY) {
    datasets.push({
      label: "Données expérimentales",
      data: expT.map((ti, i) => ({ x: ti, y: expY[i] })),
      backgroundColor: COLORS.amber,
      pointRadius: 5,
      pointHoverRadius: 7,
    });
  }

  const chart = new Chart(ctx, {
    type: "scatter",
    data: { datasets },
    options: baseOptions("Simulation physique", "Temps", "Valeur"),
  });

  chartRegistry[canvasId] = chart;
  return chart;
}

// ─── Graphique: ML prédictions ────────────────────────────────────────────────
function renderAIChart(canvasId, yTrue, yPred, modelType, lossHistory = null) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId).getContext("2d");

  if (lossHistory && lossHistory.train) {
    // Courbe de perte (DL)
    const epochs = lossHistory.train.map((_, i) => i + 1);
    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: epochs,
        datasets: [
          {
            label: "Perte entraînement",
            data: lossHistory.train,
            borderColor: COLORS.cyan,
            backgroundColor: COLORS.cyanFill,
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
          },
          ...(lossHistory.validation ? [{
            label: "Perte validation",
            data: lossHistory.validation,
            borderColor: COLORS.amber,
            backgroundColor: "transparent",
            borderWidth: 2,
            pointRadius: 0,
            borderDash: [4, 4],
          }] : []),
        ],
      },
      options: {
        ...baseOptions("Courbe d'apprentissage", "Epoch", "Perte (MSE)"),
        scales: {
          ...baseOptions("", "", "").scales,
          y: { ...baseOptions("", "", "").scales.y, type: "linear" },
        },
      },
    });
    chartRegistry[canvasId] = chart;
    return chart;
  }

  // Prédiction vs réel
  const chart = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Prédictions vs Réel",
          data: yTrue.map((yi, i) => ({ x: yi, y: yPred[i] })),
          backgroundColor: COLORS.purple,
          pointRadius: 4,
        },
        {
          label: "Idéal (y = x)",
          data: [{ x: Math.min(...yTrue), y: Math.min(...yTrue) }, { x: Math.max(...yTrue), y: Math.max(...yTrue) }],
          type: "line",
          borderColor: COLORS.green,
          borderDash: [6, 4],
          pointRadius: 0,
          backgroundColor: "transparent",
        },
      ],
    },
    options: baseOptions(`${modelType} — Prédictions vs Réel`, "Valeurs réelles", "Valeurs prédites"),
  });

  chartRegistry[canvasId] = chart;
  return chart;
}

// ─── Graphique: patterns advisor ─────────────────────────────────────────────
function renderPatternChart(canvasId, x, y, xLabel, yLabel) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId).getContext("2d");

  const chart = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [{
        label: "Données analysées",
        data: x.map((xi, i) => ({ x: xi, y: y[i] })),
        backgroundColor: COLORS.amber,
        pointRadius: 4,
        pointHoverRadius: 6,
      }],
    },
    options: {
      ...baseOptions("Analyse du pattern", xLabel, yLabel),
      plugins: { ...baseOptions().plugins, legend: { display: false } },
    },
  });

  chartRegistry[canvasId] = chart;
  return chart;
}

// Export global
window.PhysioCharts = {
  renderRawData,
  renderRegressionChart,
  renderPhysicsChart,
  renderAIChart,
  renderPatternChart,
};
