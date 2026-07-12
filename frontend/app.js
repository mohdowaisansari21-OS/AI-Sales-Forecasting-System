console.log("%c[app.js] build v3 loaded - 2026-07-09 (upload-filename-fix + date-bounds-fix + status-badge-fix)", "color:#0f9f8f;font-weight:bold;");

const sampleRows = [
  { Date: "2023-01-01", Product: "Laptop", Region: "North", Sales: 1200 },
  { Date: "2023-01-02", Product: "Laptop", Region: "North", Sales: 1350 },
  { Date: "2023-01-03", Product: "Mobile", Region: "South", Sales: 800 },
  { Date: "2023-01-04", Product: "Mobile", Region: "South", Sales: 900 },
  { Date: "2023-01-05", Product: "Laptop", Region: "East", Sales: 1100 },
  { Date: "2023-01-06", Product: "Headphones", Region: "West", Sales: 620 },
  { Date: "2023-01-07", Product: "Laptop", Region: "East", Sales: 1420 },
  { Date: "2023-01-08", Product: "Mobile", Region: "North", Sales: 980 },
  { Date: "2023-01-09", Product: "Tablet", Region: "South", Sales: 760 },
  { Date: "2023-01-10", Product: "Laptop", Region: "West", Sales: 1520 },
  { Date: "2023-01-11", Product: "Mobile", Region: "East", Sales: 1040 },
  { Date: "2023-01-12", Product: "Tablet", Region: "North", Sales: 870 },
  { Date: "2023-01-13", Product: "Headphones", Region: "South", Sales: 680 },
  { Date: "2023-01-14", Product: "Laptop", Region: "North", Sales: 1610 },
];

let allRows = normalizeRows(sampleRows);
let dataSource = "sample"; // "sample" | "backend" | "upload" - what allRows actually contains right now
let lastForecast = [];
let forecastRequestId = 0;

const els = {
  csvFile: document.getElementById("csvFile"),
  navItems: document.querySelectorAll(".nav-item"),
  segmentSelect: document.getElementById("segmentSelect"),
  startDate: document.getElementById("startDate"),
  endDate: document.getElementById("endDate"),
  exportBtn: document.getElementById("exportBtn"),
  totalRevenue: document.getElementById("totalRevenue"),
  averageSales: document.getElementById("averageSales"),
  highestSale: document.getElementById("highestSale"),
  highestSaleNote: document.getElementById("highestSaleNote"),
  recordCount: document.getElementById("recordCount"),
  revenueNote: document.getElementById("revenueNote"),
  backendStatus: document.getElementById("backendStatus"),
  growthSignal: document.getElementById("growthSignal"),
  confidenceSignal: document.getElementById("confidenceSignal"),
  dateWindow: document.getElementById("dateWindow"),
  segmentTitle: document.getElementById("segmentTitle"),
  trendChart: document.getElementById("trendChart"),
  forecastChart: document.getElementById("forecastChart"),
  segmentChart: document.getElementById("segmentChart"),
  regionPieChart: document.getElementById("regionPieChart"),
  recordsTable: document.getElementById("recordsTable"),
};

const FORECAST_DAYS = 14;
const API_URL = "https://ai-sales-forecasting-system-nf6z.onrender.com/api/forecast"
const DATA_URL = "https://ai-sales-forecasting-system-nf6z.onrender.com/api/data";
const chartColors = ["#0f9f8f", "#2f6fed", "#f97066", "#f6a609", "#22a06b", "#7c5cff"];

const backendState = { dataLoaded: false, forecastLoaded: false };

function setBackendStatus(kind, isOnline) {
  // kind: "data" (GET /api/data) or "forecast" (POST /api/forecast).
  backendState[kind === "data" ? "dataLoaded" : "forecastLoaded"] = isOnline;

  const { forecastLoaded } = backendState;
  let label;
  let online;

  if (dataSource === "upload") {
    label = forecastLoaded
      ? " Using uploaded file - Forecast API connected"
      : " Using uploaded file - Forecast API unavailable";
    online = forecastLoaded;
  } else if (dataSource === "backend") {
    label = forecastLoaded ? " Python API connected" : " Data loaded, forecast unavailable";
    online = forecastLoaded;
  } else {
    // Still on the built-in fallback sample - nothing real has loaded yet.
    label = forecastLoaded
      ? " Forecast API only (showing built-in sample data)"
      : " Python API offline (showing built-in sample data)";
    online = false;
  }

  els.backendStatus.classList.toggle("online", online);
  els.backendStatus.classList.toggle("offline", !online);
  els.backendStatus.lastChild.textContent = label;
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number.isFinite(value) ? value : 0);
}

function parseDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(value) {
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(value);
}

function getField(row, candidates) {
  // Build a case-insensitive / space-insensitive lookup once per row so
  // headers like "Order Date", "order_date", "ORDER DATE" all match.
  const lookup = {};
  for (const key of Object.keys(row)) {
    lookup[key.trim().toLowerCase().replace(/[\s_-]/g, "")] = row[key];
  }
  for (const candidate of candidates) {
    const value = lookup[candidate];
    if (value !== undefined && value !== "") return value;
  }
  return undefined;
}

function normalizeRows(rows) {
  return rows
    .map((row) => {
      const date = parseDate(
        getField(row, ["date", "orderdate", "salesdate", "transactiondate", "invoicedate"])
      );
      const sales = Number(
        getField(row, ["sales", "revenue", "amount", "totalsales", "saleamount"])
      );
      return {
        Date: date,
        Product: getField(row, ["product", "productname", "category", "subcategory", "item"]) || "General",
        Region: getField(row, ["region", "state", "city", "market"]) || "All",
        Sales: sales,
      };
    })
    .filter((row) => row.Date && Number.isFinite(row.Sales))
    .sort((a, b) => a.Date - b.Date);
}

function setDateBounds() {
  if (!allRows.length) return;
  const first = allRows[0].Date.toISOString().slice(0, 10);
  const last = allRows[allRows.length - 1].Date.toISOString().slice(0, 10);

  els.startDate.min = first;
  els.startDate.max = last;
  els.endDate.min = first;
  els.endDate.max = last;
  els.startDate.value = first;
  els.endDate.value = last;
}

function updateSegments() {
  const active = els.segmentSelect.value;
  const segments = [...new Set(allRows.map((row) => row.Product))].sort();
  els.segmentSelect.innerHTML = "<option value=\"all\">All segments</option>";

  segments.forEach((segment) => {
    const option = document.createElement("option");
    option.value = segment;
    option.textContent = segment;
    els.segmentSelect.appendChild(option);
  });

  if (segments.includes(active)) {
    els.segmentSelect.value = active;
  }
}

function getFilteredRows() {
  const start = parseDate(els.startDate.value);
  const end = parseDate(els.endDate.value);
  const segment = els.segmentSelect.value;

  return allRows.filter((row) => {
    const inSegment = segment === "all" || row.Product === segment;
    const inStart = !start || row.Date >= start;
    const inEnd = !end || row.Date <= end;
    return inSegment && inStart && inEnd;
  });
}

function linearRegression(values) {
  const n = values.length;
  if (n < 2) return { slope: 0, intercept: values[0] || 0, r2: 0 };

  const xs = values.map((_, index) => index);
  const meanX = xs.reduce((sum, value) => sum + value, 0) / n;
  const meanY = values.reduce((sum, value) => sum + value, 0) / n;
  const numerator = xs.reduce((sum, x, index) => sum + (x - meanX) * (values[index] - meanY), 0);
  const denominator = xs.reduce((sum, x) => sum + (x - meanX) ** 2, 0);
  const slope = denominator === 0 ? 0 : numerator / denominator;
  const intercept = meanY - slope * meanX;
  const total = values.reduce((sum, y) => sum + (y - meanY) ** 2, 0);
  const residual = values.reduce((sum, y, index) => sum + (y - (slope * index + intercept)) ** 2, 0);
  const r2 = total === 0 ? 1 : Math.max(0, 1 - residual / total);

  return { slope, intercept, r2 };
}

function buildForecast(rows, days) {
  if (!rows.length) return { points: [], r2: 0, growth: 0 };

  const values = rows.map((row) => row.Sales);
  const model = linearRegression(values);
  const lastDate = rows[rows.length - 1].Date;
  const points = Array.from({ length: days }, (_, index) => {
    const date = new Date(lastDate);
    date.setDate(lastDate.getDate() + index + 1);
    return {
      Date: date,
      Sales: Math.max(0, model.slope * (values.length + index) + model.intercept),
    };
  });

  const firstForecast = points[0]?.Sales || values[values.length - 1];
  const lastForecastValue = points[points.length - 1]?.Sales || firstForecast;
  const growth = firstForecast === 0 ? 0 : ((lastForecastValue - firstForecast) / firstForecast) * 100;
  return { points, r2: model.r2, growth };
}

function rowsForBackend(rows) {
  return rows.map((row) => ({
    date: row.Date.toISOString().slice(0, 10),
    product: row.Product,
    region: row.Region,
    sales: row.Sales,
  }));
}

function backendForecastToRows(forecastRows) {
  return forecastRows.map((row) => ({
    Date: parseDate(row.date),
    Sales: Number(row.sales),
    Product: "Forecast",
    Region: "Forecast",
  }));
}

async function updateBackendForecast(rows, requestId) {
  if (rows.length < 2) {
    els.growthSignal.textContent = "Need data";
    els.confidenceSignal.textContent = "Need data";
    lastForecast = [];
    drawLineChart(els.forecastChart, rows.slice(-12), []);
    return;
  }

  els.growthSignal.textContent = "...";
  els.confidenceSignal.textContent = "...";

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: Auth.authHeaders(),
      body: JSON.stringify({ rows: rowsForBackend(rows) }),
    });

    if (response.status === 401) {
      Auth.logout();
      return;
    }
    if (!response.ok) {
      throw new Error(`Forecast API returned ${response.status}`);
    }

    const result = await response.json();
    if (requestId !== forecastRequestId) return;

    const forecastRows = backendForecastToRows(result.forecast || []);
    lastForecast = forecastRows;
    setBackendStatus("forecast", true);
    els.growthSignal.textContent = `${result.forecast_change >= 0 ? "+" : ""}${Number(result.forecast_change).toFixed(1)}%`;
    els.confidenceSignal.textContent = `${Math.round(Number(result.trend_fit))}%`;
    drawLineChart(els.forecastChart, rows.slice(-12), forecastRows);
  } catch (error) {
    if (requestId !== forecastRequestId) return;

    setBackendStatus("forecast", false);
    els.growthSignal.textContent = "API off";
    els.confidenceSignal.textContent = "API off";
    lastForecast = [];
    drawLineChart(els.forecastChart, rows.slice(-12), []);
  }
}

function drawLineChart(container, actualRows, forecastRows = []) {
  const width = Math.max(container.clientWidth, 320);
  const height = container.classList.contains("compact") ? 245 : 315;
  const padding = { top: 20, right: 18, bottom: 36, left: 54 };
  const rows = [...actualRows, ...forecastRows];

  if (!rows.length) {
    container.innerHTML = "";
    return;
  }

  const minY = Math.min(...rows.map((row) => row.Sales)) * 0.9;
  const maxY = Math.max(...rows.map((row) => row.Sales)) * 1.1;
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const yRange = maxY - minY || 1;
  const maxIndex = Math.max(rows.length - 1, 1);
  const point = (row, index) => {
    const x = padding.left + (index / maxIndex) * innerWidth;
    const y = padding.top + innerHeight - ((row.Sales - minY) / yRange) * innerHeight;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  };
  const actualPath = actualRows.map(point).join(" ");
  const forecastPath = forecastRows.map((row, index) => point(row, actualRows.length + index)).join(" ");
  const areaPath = `${padding.left},${height - padding.bottom} ${actualPath} ${padding.left + ((actualRows.length - 1) / maxIndex) * innerWidth},${height - padding.bottom}`;
  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map((step) => {
      const y = padding.top + innerHeight * step;
      return `<line class="grid-line" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" />`;
    })
    .join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Sales chart">
      ${grid}
      <line class="axis" x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" />
      <line class="axis" x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}" />
      <polygon class="area-fill" points="${areaPath}" />
      <polyline class="trend-line" points="${actualPath}" />
      ${forecastRows.length ? `<polyline class="forecast-line" points="${forecastPath}" />` : ""}
      <text x="${padding.left}" y="${height - 10}" fill="#667085" font-size="12">${formatDate(rows[0].Date)}</text>
      <text x="${width - padding.right}" y="${height - 10}" fill="#667085" font-size="12" text-anchor="end">${formatDate(rows[rows.length - 1].Date)}</text>
      <text x="12" y="${padding.top + 8}" fill="#667085" font-size="12">${formatCurrency(maxY)}</text>
      <text x="12" y="${height - padding.bottom}" fill="#667085" font-size="12">${formatCurrency(minY)}</text>
    </svg>
  `;
}

function drawSegments(rows) {
  const totals = rows.reduce((map, row) => {
    map.set(row.Product, (map.get(row.Product) || 0) + row.Sales);
    return map;
  }, new Map());
  const entries = [...totals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  const max = Math.max(...entries.map((entry) => entry[1]), 1);

  els.segmentTitle.textContent = "Sales by Product";
  els.segmentChart.innerHTML = entries
    .map(([name, value], index) => {
      return `
        <div class="bar-row">
          <div class="bar-label"><span>${name}</span><span>${formatCurrency(value)}</span></div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${(value / max) * 100}%; background:${chartColors[index % chartColors.length]}"></div>
          </div>
        </div>
      `;
    })
    .join("");
}

function polarToCartesian(cx, cy, radius, angle) {
  const radians = ((angle - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(radians),
    y: cy + radius * Math.sin(radians),
  };
}

function pieSlicePath(cx, cy, radius, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? 0 : 1;
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
}

function drawRegionPie(rows) {
  const totals = rows.reduce((map, row) => {
    map.set(row.Region, (map.get(row.Region) || 0) + row.Sales);
    return map;
  }, new Map());
  const entries = [...totals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  const total = entries.reduce((sum, entry) => sum + entry[1], 0);

  if (!entries.length || total === 0) {
    els.regionPieChart.innerHTML = "";
    return;
  }

  let angle = 0;
  const slices = entries
    .map(([name, value], index) => {
      const sweep = (value / total) * 360;
      const path = pieSlicePath(100, 100, 88, angle, angle + sweep);
      angle += sweep;
      return `<path d="${path}" fill="${chartColors[index % chartColors.length]}"><title>${name}: ${formatCurrency(value)}</title></path>`;
    })
    .join("");
  const legend = entries
    .map(([name, value], index) => `
      <div class="pie-legend-row">
        <span class="pie-legend-name"><span class="pie-dot" style="background:${chartColors[index % chartColors.length]}"></span>${name}</span>
        <span>${Math.round((value / total) * 100)}%</span>
      </div>
    `)
    .join("");

  els.regionPieChart.innerHTML = `
    <svg viewBox="0 0 200 200" role="img" aria-label="Sales by region pie chart">
      ${slices}
      <circle cx="100" cy="100" r="42" fill="#ffffff"></circle>
      <text x="100" y="96" text-anchor="middle" fill="#14213d" font-size="18" font-weight="800">${entries.length}</text>
      <text x="100" y="116" text-anchor="middle" fill="#667085" font-size="12">Regions</text>
    </svg>
    <div class="pie-legend">${legend}</div>
  `;
}

function updateTable(rows) {
  els.recordsTable.innerHTML = rows
    .slice(-8)
    .reverse()
    .map((row) => `
      <tr>
        <td>${formatDate(row.Date)}</td>
        <td>${row.Product}</td>
        <td>${row.Region}</td>
        <td>${formatCurrency(row.Sales)}</td>
      </tr>
    `)
    .join("");
}

function render() {
  const rows = getFilteredRows();
  const total = rows.reduce((sum, row) => sum + row.Sales, 0);
  const average = rows.length ? total / rows.length : 0;
  const highest = rows.reduce((best, row) => (row.Sales > best.Sales ? row : best), { Sales: 0, Product: "-" });
  const requestId = ++forecastRequestId;

  els.totalRevenue.textContent = formatCurrency(total);
  els.averageSales.textContent = formatCurrency(average);
  els.highestSale.textContent = formatCurrency(highest.Sales);
  els.highestSaleNote.textContent = `${highest.Product} peak`;
  els.recordCount.textContent = rows.length.toString();
  els.revenueNote.textContent = els.segmentSelect.value === "all" ? "Across selected data" : `${els.segmentSelect.value} only`;
  els.dateWindow.textContent = rows.length ? `${formatDate(rows[0].Date)} - ${formatDate(rows[rows.length - 1].Date)}` : "";

  drawLineChart(els.trendChart, rows, []);
  drawLineChart(els.forecastChart, rows.slice(-12), []);
  drawSegments(rows);
  drawRegionPie(rows);
  updateTable(rows);
  updateBackendForecast(rows, requestId);
}

function exportForecast() {
  if (!lastForecast.length) return;
  const lines = ["Date,Forecast Sales", ...lastForecast.map((row) => `${row.Date.toISOString().slice(0, 10)},${row.Sales.toFixed(2)}`)];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "forecast_export.csv";
  link.click();
  URL.revokeObjectURL(url);
}

async function loadInitialData() {
  try {
    const response = await fetch(DATA_URL, { headers: Auth.authHeaders() });

    if (response.status === 401) {
      Auth.logout();
      return;
    }
    if (!response.ok) throw new Error(`Data API returned ${response.status}`);

    const result = await response.json();
    const parsed = normalizeRows(result.rows || []);

    if (parsed.length) {
      if (dataSource !== "upload") {
        allRows = parsed;
        dataSource = "backend";
      }
      setBackendStatus("data", true);
    } else {
      // Endpoint responded but had nothing usable - still a failure to
      // surface, not a silent no-op.
      setBackendStatus("data", false);
    }
  } catch (error) {
    // Backend not running, /api/data missing (older api_server.py), or
    // sales_data.csv not found - keep using the small built-in sample so
    // the dashboard still renders something, but flag it clearly.
    console.warn("[loadInitialData] Falling back to built-in sample data:", error.message);
    setBackendStatus("data", false);
  }
}

els.csvFile.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  const text = await file.text();

  if (typeof CsvLoader === "undefined") {
    alert("CsvLoader is not loaded. Make sure csv-loader.js is included before app.js in index.html.");
    return;
  }

  const result = CsvLoader.load(text);

  if (result.rows.length) {
    allRows = result.rows;
    dataSource = "upload";
    setBackendStatus("data", backendState.dataLoaded); // refresh label text for new source
    updateSegments();
    setDateBounds();
    render();
    console.info(`[CsvLoader] Loaded "${file.name}"\n${result.report()}`);
  } else {
    alert(
      `Could not read any valid rows from "${file.name}".\n\n${result.report()}\n\n` +
      `The file needs at least one column that looks like dates and one that looks like numbers.`
    );
  }
});

["change", "input"].forEach((eventName) => {
  els.segmentSelect.addEventListener(eventName, render);
  els.startDate.addEventListener(eventName, render);
  els.endDate.addEventListener(eventName, render);
});

els.exportBtn.addEventListener("click", exportForecast);
els.navItems.forEach((item) => {
  item.addEventListener("click", (event) => {
    const target = document.getElementById(item.dataset.target);
    if (!target) return;

    event.preventDefault();
    els.navItems.forEach((navItem) => navItem.classList.remove("active"));
    item.classList.add("active");
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    window.history.replaceState(null, "", item.getAttribute("href"));
  });
});
window.addEventListener("resize", render);

(async function init() {
  await loadInitialData();
  updateSegments();
  setDateBounds();
  render();
})();
