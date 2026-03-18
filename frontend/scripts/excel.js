/**
 * excel.js — Interactions Excel via Office.js pour PhysioAI Lab
 * Lecture, écriture et export des résultats.
 */
"use strict";

const ExcelIO = {

  // ── Lecture de la sélection ───────────────────────────────────────────────
  async readSelection(hasHeader = true) {
    return Excel.run(async (ctx) => {
      const range = ctx.workbook.getSelectedRange();
      range.load(["values", "address"]);
      await ctx.sync();

      const raw = range.values;
      if (!raw || raw.length < 2) throw new Error("Sélection trop petite (min. 2 lignes).");

      let headers, dataRows, sampleNames;

      if (hasHeader) {
        headers  = raw[0].map((h, i) => (h !== null && h !== "") ? String(h) : `V${i+1}`);
        dataRows = raw.slice(1);
      } else {
        headers  = raw[0].map((_, i) => `V${i+1}`);
        dataRows = raw;
      }

      // Détecter colonne texte (identifiants)
      const firstColText = dataRows.every(r => typeof r[0] === "string" && isNaN(parseFloat(r[0])));
      if (firstColText) {
        sampleNames = dataRows.map(r => String(r[0]));
        headers     = headers.slice(1);
        dataRows    = dataRows.map(r => r.slice(1));
        if (hasHeader) headers = raw[0].slice(1).map((h, i) => h || `V${i+1}`);
      } else {
        sampleNames = dataRows.map((_, i) => `S${i+1}`);
      }

      // Convertir en float
      const data = dataRows.map(row =>
        row.map(v => { const n = parseFloat(v); return isNaN(n) ? NaN : n; })
      );

      // Construire dict pour l'API
      const dataDict = {};
      headers.forEach((h, j) => {
        dataDict[h] = data.map(r => r[j] || 0);
      });

      return {
        headers, data, sampleNames, dataDict,
        address: range.address,
        nRows: data.length, nCols: headers.length,
      };
    });
  },

  // ── Parse CSV ─────────────────────────────────────────────────────────────
  parseCSV(text, sep = ",", hasHeader = true) {
    const lines = text.trim().split(/\r?\n/);
    const rows  = lines.map(l => l.split(sep).map(v => v.trim().replace(/^"|"$/g, "")));

    let headers, dataRows, sampleNames;
    if (hasHeader) {
      headers  = rows[0].map((h, i) => h || `V${i+1}`);
      dataRows = rows.slice(1);
    } else {
      headers  = rows[0].map((_, i) => `V${i+1}`);
      dataRows = rows;
    }

    const firstColText = dataRows.every(r => typeof r[0] === "string" && isNaN(parseFloat(r[0])));
    if (firstColText) {
      sampleNames = dataRows.map(r => r[0]);
      headers     = headers.slice(1);
      dataRows    = dataRows.map(r => r.slice(1));
    } else {
      sampleNames = dataRows.map((_, i) => `S${i+1}`);
    }

    const data = dataRows.map(row =>
      row.map(v => { const n = parseFloat(v); return isNaN(n) ? NaN : n; })
    );

    const dataDict = {};
    headers.forEach((h, j) => { dataDict[h] = data.map(r => r[j] || 0); });

    return { headers, data, sampleNames, dataDict, nRows: data.length, nCols: headers.length };
  },

  // ── Export vers Excel ─────────────────────────────────────────────────────

  /** Utilitaires internes */
  _n(v, d = 4) {
    if (v === null || v === undefined || !isFinite(v)) return 0;
    return parseFloat(Number(v).toFixed(d));
  },

  async _sheet(ctx, name) {
    const ws = ctx.workbook.worksheets.getItemOrNullObject(name);
    ws.load("isNullObject");
    await ctx.sync();
    if (ws.isNullObject) {
      const s = ctx.workbook.worksheets.add(name);
      s.activate();
      await ctx.sync();
      return s;
    }
    const used = ws.getUsedRangeOrNullObject();
    used.load("isNullObject");
    await ctx.sync();
    if (!used.isNullObject) { used.clear("All"); await ctx.sync(); }
    ws.activate();
    return ws;
  },

  _write(sheet, row, col, data2D) {
    if (!data2D || data2D.length === 0) return row;
    const nCols = Math.max(...data2D.map(r => Array.from(r).length), 1);
    const safe  = data2D.map(r => {
      const a = Array.from(r);
      const out = new Array(nCols).fill("");
      for (let j = 0; j < nCols; j++) {
        const v = a[j];
        out[j] = (v === null || v === undefined) ? "" : (typeof v === "number" && !isFinite(v)) ? 0 : v;
      }
      return out;
    });
    sheet.getRangeByIndexes(row, col, safe.length, nCols).values = safe;
    return row + safe.length;
  },

  _header(sheet, row, cols) {
    if (!cols.length) return row;
    const r = sheet.getRangeByIndexes(row, 0, 1, cols.length);
    r.values = [cols.map(c => String(c ?? ""))];
    r.format.font.bold  = true;
    r.format.font.color = "#003300";
    r.format.fill.color = "#C6EFCE";
    return row + 1;
  },

  _title(sheet, row, text, w) {
    const range = sheet.getRangeByIndexes(row, 0, 1, Math.max(w, 1));
    range.values = [[text]];
    range.getCell(0, 0).format.font.bold  = true;
    range.getCell(0, 0).format.font.color = "#FFFFFF";
    range.getCell(0, 0).format.font.size  = 11;
    range.format.fill.color = "#1E4080";
    return row + 1;
  },

  // ── Export résultats régression ───────────────────────────────────────────
  async exportRegression(result, sampleNames) {
    return Excel.run(async (ctx) => {
      const sheet = await this._sheet(ctx, "PhysioAI_Régression");
      let row = 0;

      row = this._title(sheet, row, `Régression ${result.type?.toUpperCase() || ""}`, 4);
      row = this._header(sheet, row, ["Métrique", "Valeur"]);
      const metrics = [
        ["R²",    this._n(result.r2, 4)],
        ["RMSE",  this._n(result.rmse, 4)],
        ["MAE",   this._n(result.mae, 4)],
      ];
      if (result.slope !== undefined) {
        metrics.push(["Pente", this._n(result.slope, 6)]);
        metrics.push(["Intercept", this._n(result.intercept, 6)]);
        metrics.push(["p-valeur", this._n(result.p_value, 6)]);
      }
      row = this._write(sheet, row, 0, metrics);
      row += 2;

      row = this._title(sheet, row, "Données et prédictions", 3);
      row = this._header(sheet, row, ["Échantillon", "y réel", "y prédit", "Résidu"]);
      const predData = (result.y_true || []).map((y, i) => [
        sampleNames?.[i] || `S${i+1}`,
        this._n(y, 4),
        this._n((result.y_pred || [])[i], 4),
        this._n((result.residuals || [])[i], 4),
      ]);
      this._write(sheet, row, 0, predData);

      await ctx.sync();
    });
  },

  // ── Export modèle physique ────────────────────────────────────────────────
  async exportPhysics(result, sampleNames) {
    return Excel.run(async (ctx) => {
      const sheet = await this._sheet(ctx, "PhysioAI_Physique");
      let row = 0;

      row = this._title(sheet, row, `Modèle : ${result.model || "physique"}`, 4);
      row = this._header(sheet, row, ["Paramètre", "Valeur"]);
      const params = Object.entries(result.params || {}).map(([k, v]) => [k, this._n(v, 6)]);
      if (result.r2 !== null && result.r2 !== undefined) params.push(["R²", this._n(result.r2, 4)]);
      if (result.half_life) params.push(["Demi-vie", this._n(result.half_life, 4)]);
      row = this._write(sheet, row, 0, params);
      row += 2;

      row = this._title(sheet, row, "Simulation", 2);
      row = this._header(sheet, row, ["t", "C simulé"]);
      const simData = (result.t_sim || []).map((t, i) => [
        this._n(t, 4), this._n((result.C_sim || [])[i], 6),
      ]);
      this._write(sheet, row, 0, simData);

      await ctx.sync();
    });
  },

  // ── Export simulation ─────────────────────────────────────────────────────
  async exportSimulation(result) {
    return Excel.run(async (ctx) => {
      const sheet = await this._sheet(ctx, "PhysioAI_Simulation");
      let row = 0;

      row = this._title(sheet, row, "Résultats de simulation", 3);
      row = this._header(sheet, row, ["t", "C(t)", "Conversion"]);
      const data = (result.t || result.t_sim || []).map((t, i) => [
        this._n(t, 4),
        this._n((result.C || result.C_sim || [])[i], 6),
        this._n((result.conversion || [])[i], 4),
      ]);
      this._write(sheet, row, 0, data);

      await ctx.sync();
    });
  },

  // ── Export ML ─────────────────────────────────────────────────────────────
  async exportML(result, varNames, sampleNames) {
    return Excel.run(async (ctx) => {
      const sheet = await this._sheet(ctx, "PhysioAI_ML");
      let row = 0;

      row = this._title(sheet, row, `Résultats ${result.model?.toUpperCase() || "ML"}`, 3);
      row = this._header(sheet, row, ["Métrique", "Valeur"]);
      const metrics = [
        ["R²", this._n(result.r2, 4)],
        ["RMSE", this._n(result.rmse, 4)],
        ["CV R²", this._n(result.cv_r2, 4)],
      ].filter(([, v]) => v !== 0 || true);
      row = this._write(sheet, row, 0, metrics);
      row += 2;

      if (result.feature_importance) {
        row = this._title(sheet, row, "Importance des variables", 2);
        row = this._header(sheet, row, ["Variable", "Importance"]);
        const vn = varNames || result.feature_importance.map((_, i) => `V${i+1}`);
        const impData = result.feature_importance
          .map((v, i) => ({ name: vn[i], v }))
          .sort((a, b) => b.v - a.v)
          .map(d => [d.name, this._n(d.v, 4)]);
        row = this._write(sheet, row, 0, impData);
        row += 2;
      }

      if (result.y_pred) {
        row = this._title(sheet, row, "Prédictions", 3);
        row = this._header(sheet, row, ["Échantillon", "y réel", "y prédit"]);
        const predData = (result.y_true || []).map((y, i) => [
          sampleNames?.[i] || `S${i+1}`,
          this._n(y, 4),
          this._n((result.y_pred || [])[i], 4),
        ]);
        this._write(sheet, row, 0, predData);
      }

      await ctx.sync();
    });
  },
};

window.ExcelIO = ExcelIO;
