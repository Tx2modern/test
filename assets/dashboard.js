const SERIES_GROUP_LABELS = {
  front_month: "Front-Month Futures",
  curve_proxy: "Curve Proxy ETFs",
  tanker_crude: "Crude Tankers",
  tanker_product: "Product Tankers",
  freight: "Freight",
};

async function loadJson(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

function sparklinePath(values, width, height, pad = 4) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = (width - pad * 2) / (values.length - 1 || 1);
  const points = values.map((v, i) => {
    const x = pad + i * step;
    const y = height - pad - ((v - min) / range) * (height - pad * 2);
    return [x, y];
  });
  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const fillPath = `${linePath} L${points[points.length - 1][0].toFixed(1)},${height - pad} L${points[0][0].toFixed(1)},${height - pad} Z`;
  return { linePath, fillPath };
}

function renderSparkline(values) {
  const width = 260;
  const height = 80;
  const { linePath, fillPath } = sparklinePath(values, width, height);
  return `<svg class="chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
    <path class="fill" d="${fillPath}"></path>
    <path class="line" d="${linePath}"></path>
  </svg>`;
}

function pctChange(current, prior) {
  if (prior === null || prior === undefined || prior === 0) return null;
  return ((current - prior) / prior) * 100;
}

function fmtPct(pct) {
  if (pct === null) return "—";
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function renderDailyClose(rows) {
  const grid = document.getElementById("daily-close-grid");
  grid.innerHTML = "";

  const byTicker = {};
  for (const row of rows) {
    (byTicker[row.ticker] ??= []).push(row);
  }

  const order = Object.entries(byTicker).sort((a, b) => {
    const groupA = a[1][0].series_group;
    const groupB = b[1][0].series_group;
    return groupA.localeCompare(groupB);
  });

  for (const [ticker, series] of order) {
    series.sort((a, b) => a.price_date.localeCompare(b.price_date));
    const closes = series.map((r) => r.close);
    const latest = series[series.length - 1];
    const prior = series.length > 1 ? series[series.length - 2].close : null;
    const pct = pctChange(latest.close, prior);
    const dir = pct === null ? "" : pct >= 0 ? "up" : "down";

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="card-title">
        <h3>${ticker}</h3>
        <span class="card-price ${dir}">$${latest.close.toFixed(2)}</span>
      </div>
      <div class="card-sub">${latest.label} · ${SERIES_GROUP_LABELS[latest.series_group] ?? latest.series_group}</div>
      ${renderSparkline(closes)}
      <div class="deltas"><span class="${dir}">${fmtPct(pct)} vs prior close</span></div>
    `;
    grid.appendChild(card);
  }
}

function renderCurves(rows) {
  const grid = document.getElementById("curve-grid");
  grid.innerHTML = "";

  const byCommodity = {};
  for (const row of rows) {
    (byCommodity[row.commodity] ??= []).push(row);
  }

  for (const [commodity, series] of Object.entries(byCommodity)) {
    series.sort((a, b) => a.tenor - b.tenor);
    const prices = series.map((r) => r.price);
    const front = series[0];

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="card-title">
        <h3>${front.name}</h3>
        <span class="card-price">${front.price.toFixed(2)} ${front.units}</span>
      </div>
      <div class="card-sub">As of ${front.as_of_date} · 12-month curve, front contract ${front.contract}</div>
      ${renderSparkline(prices)}
      <div class="deltas">
        <span>1d: ${fmtPct(pctChange(front.price, front.price_1d))}</span>
        <span>1w: ${fmtPct(pctChange(front.price, front.price_1w))}</span>
        <span>1m: ${fmtPct(pctChange(front.price, front.price_1m))}</span>
        <span>1y: ${fmtPct(pctChange(front.price, front.price_1y))}</span>
      </div>
    `;
    grid.appendChild(card);
  }
}

function setStatus(mode, generatedAt) {
  const badge = document.getElementById("status");
  const when = new Date(generatedAt).toLocaleString();
  if (mode === "mock") {
    badge.textContent = `Sample data (Fabric not yet connected) · generated ${when}`;
    badge.className = "status-badge mock";
  } else {
    badge.textContent = `Live · generated ${when}`;
    badge.className = "status-badge live";
  }
}

async function main() {
  try {
    const [dailyClose, futuresCurve] = await Promise.all([
      loadJson("data/yf_daily_close.json"),
      loadJson("data/yf_futures_curve.json"),
    ]);
    setStatus(dailyClose.mode, dailyClose.generated_at);
    renderCurves(futuresCurve.rows);
    renderDailyClose(dailyClose.rows);
  } catch (err) {
    const badge = document.getElementById("status");
    badge.textContent = `Failed to load data: ${err.message}`;
    badge.className = "status-badge error";
  }
}

main();
