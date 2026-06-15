"use strict";

const COLORS = {
  home: "#38bdf8",
  away: "#f472b6",
  venue: "#fbbf24",
  homeBand: "rgba(56,189,248,0.14)",
};

// Which variables to surface, and their display metadata (filled from API too).
const VARS = ["t2m", "rh", "tp", "ssrd"];

const charts = {};

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `${r.status} ${r.statusText}`);
  }
  return r.json();
}

function setStatus(msg, isError = false) {
  const el = document.getElementById("status");
  el.textContent = msg || "";
  el.classList.toggle("error", isError);
}

async function init() {
  try {
    const data = await getJSON("/api/matches");
    const md = new Date(data.matchday + "T00:00:00");
    document.getElementById("meta").textContent =
      `Match day: ${md.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}`;
    renderMatches(data.matches);
    if (data.matches.length) selectMatch(data.matches[0].idx, data.matches);
  } catch (err) {
    setStatus("Could not load fixtures: " + err.message, true);
  }
}

function renderMatches(matches) {
  const root = document.getElementById("matches");
  root.innerHTML = "";
  if (!matches.length) {
    root.innerHTML = `<p class="status">No fixtures for the active match day.</p>`;
    return;
  }
  for (const m of matches) {
    const chip = document.createElement("div");
    chip.className = "match-chip";
    chip.dataset.idx = m.idx;
    chip.innerHTML =
      `<strong>${m.home_flag} ${m.home}</strong><span class="vs">vs</span><strong>${m.away} ${m.away_flag}</strong>` +
      `<span class="venue">${m.venue.name}, ${m.venue.city}</span>`;
    chip.onclick = () => selectMatch(m.idx, matches);
    root.appendChild(chip);
  }
}

async function selectMatch(idx, matches) {
  document.querySelectorAll(".match-chip").forEach((c) =>
    c.classList.toggle("active", Number(c.dataset.idx) === idx)
  );
  setStatus("Loading climate data…");
  document.getElementById("report").classList.add("hidden");
  try {
    const rep = await getJSON(`/api/report/${idx}`);
    renderReport(rep);
    setStatus("");
    document.getElementById("report").classList.remove("hidden");
  } catch (err) {
    setStatus("Could not load report: " + err.message, true);
  }
}

function renderReport(rep) {
  const m = rep.match;
  const home = rep.capitals.home;
  const away = rep.capitals.away;
  const venue = rep.venue;

  document.getElementById("matchHead").innerHTML =
    `<h2>${m.home} vs ${m.away}</h2>` +
    `<div class="sub">${m.stage}${m.group ? " · Group " + m.group : ""} · ` +
    `${venue.name}, ${m.venue.city} (${m.venue.country}) · ${rep.matchday}</div>`;

  renderCards(rep, home, away, venue);
  renderCharts(rep, home, away, venue);

  document.getElementById("footnote").innerHTML =
    `Window: ${rep.window.start} → ${rep.window.end} (${rep.window.days} days). ` +
    `Reanalysis (ERA5) through ${rep.era5_cutoff}; more recent days from the ECMWF IFS forecast. ` +
    `Capitals show a ${10}-year climatology (mean + p10–p90 band). All values are UTC daily aggregates. ` +
    `Nearest grid cell to each location.`;
}

function fmt(x, digits = 1) {
  return x === null || x === undefined ? "–" : Number(x).toFixed(digits);
}

function renderCards(rep, home, away, venue) {
  const root = document.getElementById("cards");
  root.innerHTML = "";
  for (const v of VARS) {
    const meta = rep.variables[v];
    const hs = home.summary[v] || {};
    const as = away.summary[v] || {};
    const venueNow = lastValue(venue.current.values[v]);
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML =
      `<h3>${meta.label} <span class="unit">${meta.display_unit}</span></h3>` +
      `<div class="big"><span class="dot venue"></span>${fmt(venueNow)} <span class="unit">venue</span></div>` +
      cardRow("home", home.name, hs) +
      cardRow("away", away.name, as);
    root.appendChild(card);
  }
}

function cardRow(klass, name, s) {
  const anom =
    s.anomaly === undefined || s.anomaly === null
      ? ""
      : `<span class="${s.anomaly >= 0 ? "anom-pos" : "anom-neg"}">` +
        `${s.anomaly >= 0 ? "+" : ""}${fmt(s.anomaly)} vs clim</span>`;
  return (
    `<div class="row"><span><span class="dot ${klass}"></span>${name}: ${fmt(s.now)}</span>${anom}</div>`
  );
}

function lastValue(arr) {
  if (!arr) return null;
  for (let i = arr.length - 1; i >= 0; i--) if (arr[i] !== null) return arr[i];
  return null;
}

function renderCharts(rep, home, away, venue) {
  const root = document.getElementById("charts");
  root.innerHTML = "";
  const labels = home.current.dates;

  for (const v of VARS) {
    const meta = rep.variables[v];
    const box = document.createElement("div");
    box.className = "chart-box";
    box.innerHTML =
      `<h3>${meta.label} <span class="unit">(${meta.display_unit})</span></h3>` +
      `<div class="legend">Solid: current · dashed: capital climatology mean · shaded: ${home.name} p10–p90</div>` +
      `<canvas id="c_${v}"></canvas>`;
    root.appendChild(box);

    const hc = home.climatology.values[v] || {};
    const ds = [
      // home climatology p10–p90 band (drawn first, behind)
      band(`${home.name} p90`, hc.p90, COLORS.homeBand, "+1"),
      band(`${home.name} p10`, hc.p10, COLORS.homeBand, false),
      // climatology means (dashed)
      dashed(`${home.name} clim`, (home.climatology.values[v] || {}).mean, COLORS.home),
      dashed(`${away.name} clim`, (away.climatology.values[v] || {}).mean, COLORS.away),
      // current series (solid)
      solid(`${home.name} now`, home.current.values[v], COLORS.home),
      solid(`${away.name} now`, away.current.values[v], COLORS.away),
      solid(`${venue.name} now`, venue.current.values[v], COLORS.venue),
    ];

    if (charts[v]) charts[v].destroy();
    charts[v] = new Chart(document.getElementById(`c_${v}`), {
      type: "line",
      data: { labels, datasets: ds },
      options: chartOptions(),
    });
  }
}

function solid(label, data, color) {
  return { label, data, borderColor: color, backgroundColor: color, borderWidth: 2,
           pointRadius: 0, tension: 0.25, spanGaps: true };
}
function dashed(label, data, color) {
  return { label, data, borderColor: color, borderDash: [5, 4], borderWidth: 1.3,
           pointRadius: 0, tension: 0.25, spanGaps: true };
}
function band(label, data, color, fill) {
  return { label, data, borderColor: "transparent", backgroundColor: color,
           fill, pointRadius: 0, borderWidth: 0, tension: 0.25 };
}

function chartOptions() {
  const grid = { color: "rgba(255,255,255,0.06)" };
  const ticks = { color: "#9fb0c8", maxTicksLimit: 8 };
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: "#9fb0c8", boxWidth: 12, filter: (i) => !i.text.includes("p10") && !i.text.includes("p90") } },
    },
    scales: { x: { grid, ticks }, y: { grid, ticks } },
  };
}

init();
