/**
 * PhysioAI Lab — Module Excel (Office.js)
 * Lecture / écriture de données depuis/vers Excel
 */

const ExcelHelper = {

  /**
   * Lit une plage Excel et retourne un tableau de nombres.
   * @param {string} rangeAddress - Adresse de la plage (ex: "A2:A20")
   * @returns {Promise<number[]>} Tableau de valeurs numériques
   */
  async readRange(rangeAddress) {
    return new Promise((resolve, reject) => {
      Excel.run(async (context) => {
        try {
          const sheet = context.workbook.worksheets.getActiveWorksheet();
          const range = sheet.getRange(rangeAddress);
          range.load("values");
          await context.sync();

          const values = range.values.flat().map(v => {
            const num = parseFloat(v);
            if (isNaN(num)) throw new Error(`Valeur non numérique: "${v}"`);
            return num;
          });

          resolve(values);
        } catch (e) {
          reject(e);
        }
      });
    });
  },

  /**
   * Écrit un tableau de données dans Excel à partir d'une cellule.
   * @param {string} startCell - Cellule de départ (ex: "D1")
   * @param {Array<Array>} headers - En-têtes du tableau
   * @param {Array<Array>} data - Données à écrire
   * @param {string} sheetName - Nom de la feuille (optionnel)
   */
  async writeResults(startCell, headers, data, sheetName = null) {
    return new Promise((resolve, reject) => {
      Excel.run(async (context) => {
        try {
          let sheet;
          if (sheetName) {
            try {
              sheet = context.workbook.worksheets.getItem(sheetName);
            } catch {
              sheet = context.workbook.worksheets.add(sheetName);
            }
          } else {
            sheet = context.workbook.worksheets.getActiveWorksheet();
          }

          const allData = [headers, ...data];
          const endCol = String.fromCharCode(startCell.charCodeAt(0) + headers.length - 1);
          const startRow = parseInt(startCell.slice(1));
          const endRow = startRow + allData.length - 1;
          const rangeAddr = `${startCell}:${endCol}${endRow}`;

          const range = sheet.getRange(rangeAddr);
          range.values = allData;

          // Style des en-têtes
          const headerRange = sheet.getRange(`${startCell}:${endCol}${startRow}`);
          headerRange.format.fill.color = "#161b22";
          headerRange.format.font.bold = true;
          headerRange.format.font.color = "#39d0d8";

          // Ajustement automatique des colonnes
          range.format.autofitColumns();

          await context.sync();
          resolve();
        } catch (e) {
          reject(e);
        }
      });
    });
  },

  /**
   * Exporte les résultats de régression dans une nouvelle feuille.
   */
  async exportRegressionResults(data) {
    const { curveX, curveY, equation, r2, model_type } = data;
    const rows = curveX.map((x, i) => [x, curveY[i]]);
    const sheetName = `Régression_${model_type}`;
    await this.writeResults("A1", ["x", "y_modèle"], rows, sheetName);
    return sheetName;
  },

  /**
   * Exporte les résultats de simulation physique.
   */
  async exportPhysicsResults(data) {
    const { t, y, model_type } = data;
    const rows = t.map((ti, i) => [ti, y[i]]);
    const sheetName = `Simulation_${model_type}`;
    await this.writeResults("A1", ["temps", "valeur"], rows, sheetName);
    return sheetName;
  },

  /**
   * Vérifie si on est dans un environnement Office.
   */
  isOfficeEnvironment() {
    return typeof Office !== "undefined" && typeof Excel !== "undefined";
  },

  /**
   * Mode démo: données exemples si pas dans Office.
   */
  getDemoData(type = "kinetics_1") {
    const demos = {
      kinetics_1: {
        x: [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80],
        y: [1.00, 0.78, 0.61, 0.47, 0.37, 0.29, 0.22, 0.14, 0.08, 0.05, 0.03, 0.02],
      },
      linear: {
        x: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        y: [0.5, 1.8, 3.2, 4.1, 5.6, 6.9, 8.1, 9.3, 10.8, 12.2, 13.5],
      },
      noisy: {
        x: [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
        y: [2.1, 3.8, 7.2, 12.5, 19.8, 29.1, 42.3, 58.7, 79.4, 103.1, 132.5],
      },
    };
    return demos[type] || demos.kinetics_1;
  },
};

window.ExcelHelper = ExcelHelper;
