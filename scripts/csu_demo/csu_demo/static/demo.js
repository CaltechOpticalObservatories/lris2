// Draw the CSU as seen from the webcam, keep it live, and send operator commands
const STATES = ["disabled", "standstill", "homing", "moving", "moving", "stopping", "error stop"];
const messageBox = document.getElementById("message");
const panel = document.getElementById("panel");
let inControl = false;
let layout = { rows: 12, bars: {} };
let axesByName = {};
let chosenBar = null;
let selected = null; // { name, bars } of the save point shown beside the live values

async function api(method, path, body) {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function showMessage(text, kind = "error") {
  messageBox.textContent = text || "";
  messageBox.className = kind;
  messageBox.hidden = !text;
}

const showError = (text) => showMessage(text, "error");
const showNotice = (text) => showMessage(text, "notice");

function barElement(name) {
  const bar = document.createElement("button");
  bar.className = "bar";
  bar.dataset.bar = name;
  bar.innerHTML = `<span class="name">${name}</span><span class="pos"></span>
                   <span class="state"></span><span class="saved"></span>
                   <span class="spark temp"><svg viewBox="0 0 70 18" preserveAspectRatio="none"></svg><span class="value"></span></span>
                   <span class="spark cur"><svg viewBox="0 0 70 18" preserveAspectRatio="none"></svg><span class="value"></span></span>`;
  bar.addEventListener("click", () => chooseBar(name));
  return bar;
}

// The CSU is built from modules of six bars; a spacer row separates upper and lower modules
const MODULE_ROWS = 6;
const gridRow = (row) => row + Math.floor((row - 1) / MODULE_ROWS);

function buildCsu(axes) {
  const csu = document.getElementById("csu");
  const cells = [];
  for (let first = 1; first <= layout.rows; first += MODULE_ROWS) {
    const last = Math.min(first + MODULE_ROWS - 1, layout.rows);
    for (const column of [1, 3]) {
      const frame = document.createElement("div");
      frame.className = "module";
      frame.style.gridColumn = column;
      frame.style.gridRow = `${gridRow(first)} / ${gridRow(last) + 1}`;
      cells.push(frame);
    }
    if (last < layout.rows) {
      const gap = document.createElement("div");
      gap.className = "module-gap";
      gap.style.gridRow = gridRow(last) + 1;
      cells.push(gap);
    }
  }
  for (let row = 1; row <= layout.rows; row += 1) {
    for (const side of ["left", "right"]) {
      const cell = document.createElement("div");
      cell.className = `slot ${side}`;
      cell.style.gridRow = gridRow(row);
      cell.id = `slot-${side}-${row}`;
      cells.push(cell);
    }
    const slit = document.createElement("div");
    slit.className = "slit";
    slit.style.gridRow = gridRow(row);
    slit.textContent = row;
    cells.push(slit);
  }
  csu.replaceChildren(...cells);

  const unplaced = [];
  for (const axis of axes) {
    const slot = layout.bars[axis.name];
    const bar = barElement(axis.name);
    if (slot) {
      document.getElementById(`slot-${slot.side}-${slot.row}`).append(bar);
    } else {
      unplaced.push(bar);
    }
  }
  document.getElementById("unplaced-list").replaceChildren(...unplaced);
  document.getElementById("unplaced").hidden = unplaced.length === 0;
}

function renderBar(axis) {
  const bar = document.querySelector(`.bar[data-bar="${axis.name}"]`);
  if (!bar) return;
  bar.classList.toggle("live", axis.enabled && !axis.error);
  bar.classList.toggle("off", !axis.enabled && !axis.error);
  bar.classList.toggle("faulted", axis.error);
  bar.classList.toggle("moving", axis.moving);
  bar.classList.toggle("chosen", axis.name === chosenBar);
  bar.querySelector(".pos").textContent = axis.position === undefined ? "–" : axis.position.toFixed(2);
  bar.querySelector(".state").textContent = axis.error
    ? `fault 0x${axis.error_id.toString(16)}` : (STATES[axis.state] ?? "–");
  const saved = selected?.bars[axis.name];
  const was = { true: "on", false: "off", null: "?" }[saved?.enabled ?? null];
  bar.querySelector(".saved").textContent = saved ? `saved ${saved.position.toFixed(2)} (${was})` : "";
}

function slotLabel(name) {
  const slot = layout.bars[name];
  return slot ? `${slot.side} side, row ${slot.row} from the top` : "not placed";
}

function renderPanel() {
  const axis = axesByName[chosenBar];
  document.getElementById("panel-body").hidden = !axis;
  if (!axis) {
    document.getElementById("panel-title").textContent = "Click a bar to control it";
    return;
  }
  document.getElementById("panel-title").textContent = `${axis.name}: ${slotLabel(axis.name)}`;
  document.getElementById("panel-status").textContent =
    `${axis.position.toFixed(3)} ${axis.units}, ${STATES[axis.state] ?? "–"}, ` +
    (axis.enabled ? "enabled" : "disabled") + (axis.error ? `, fault 0x${axis.error_id.toString(16)}` : "");
  for (const units of panel.querySelectorAll(".units")) units.textContent = axis.units;
  const velocity = document.getElementById("velocity");
  velocity.max = axis.max_velocity;
  if (!velocity.value) velocity.value = Math.min(5, axis.max_velocity);
  for (const button of panel.querySelectorAll("button")) button.disabled = !inControl;
}

function chooseBar(name) {
  chosenBar = chosenBar === name ? null : name;
  document.getElementById("velocity").value = "";
  poll();
}

// Grafana-style time charts: one line per bar, shared time axis, legend with last and max
const PALETTE = ["#73bf69", "#f2cc0c", "#8ab8ff", "#ff780a", "#f2495c", "#5794f2", "#b877d9",
                 "#705da0", "#37872d", "#fade2a", "#3274d9", "#e0b400", "#c4162a", "#1f78c1",
                 "#ba43a9", "#9ac48a", "#ffb357", "#ff7383", "#a352cc", "#56a64b", "#ca95e5",
                 "#4ab0ff", "#ffee52"];
const hiddenBars = new Set();

function niceTicks(lo, hi, count) {
  const step = 10 ** Math.floor(Math.log10((hi - lo) / count || 1));
  const best = [1, 2, 5, 10].map((m) => m * step).find((s) => (hi - lo) / s <= count) || step * 10;
  const ticks = [];
  for (let v = Math.ceil(lo / best) * best; v <= hi + 1e-9; v += best) ticks.push(v);
  return ticks;
}

// Current is signed by torque direction; the charts show its magnitude, which is what heats
const magnitude = (key, v) => (key === "current" && v != null ? Math.abs(v) : v);

function drawChart(figure, history) {
  const key = figure.dataset.key;
  const unit = figure.dataset.unit;
  const names = Object.keys(history).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const series = names.map((name, index) => ({
    name, color: PALETTE[index % PALETTE.length],
    points: history[name].time.map((t, i) => [t, magnitude(key, (history[name][key] || [])[i])])
      .filter(([, v]) => v != null),
  }));
  const visible = series.filter((s) => !hiddenBars.has(s.name) && s.points.length);
  const svg = figure.querySelector("svg");
  const all = visible.flatMap((s) => s.points);
  if (all.length < 2) {
    svg.innerHTML = '<text x="20" y="100">collecting… one sample every 10 s</text>';
  } else {
    const t0 = Math.min(...all.map(([t]) => t)), t1 = Math.max(...all.map(([t]) => t));
    let lo = Math.min(...all.map(([, v]) => v)), hi = Math.max(...all.map(([, v]) => v));
    if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.05; lo -= pad; hi += pad;
    const x = (t) => 50 + ((t - t0) / Math.max(t1 - t0, 1)) * 545;
    const y = (v) => 185 - ((v - lo) / (hi - lo)) * 175;
    const grid = niceTicks(lo, hi, 5).map((v) =>
      `<line class="grid" x1="50" x2="595" y1="${y(v)}" y2="${y(v)}"></line>` +
      `<text x="2" y="${y(v) + 4}">${+v.toFixed(2)} ${unit}</text>`).join("");
    const times = [0, 0.5, 1].map((f) => t0 + f * (t1 - t0)).map((t) =>
      `<text x="${Math.min(x(t) - 14, 565)}" y="199">${new Date(t * 1000).toTimeString().slice(0, 5)}</text>`).join("");
    const lines = visible.map((s) =>
      `<polyline stroke="${s.color}" points="${s.points.map(([t, v]) => `${x(t).toFixed(1)},${y(v).toFixed(1)}`).join(" ")}"></polyline>`).join("");
    svg.innerHTML = grid + times + lines;
  }
  const rows = series.map((s) => {
    const values = s.points.map(([, v]) => v);
    const last = values.length ? values[values.length - 1] : null;
    const max = values.length ? Math.max(...values) : null;
    const fmt = (v) => (v == null ? "–" : `${+v.toFixed(1)} ${unit}`);
    return `<tr data-bar="${s.name}" class="${hiddenBars.has(s.name) ? "hidden" : ""}">` +
      `<td><span class="swatch" style="background:${s.color}"></span>${s.name}</td>` +
      `<td>${fmt(last)}</td><td>${fmt(max)}</td></tr>`;
  }).join("");
  figure.querySelector(".legend").innerHTML = `<tr><th>Name</th><th>Last</th><th>Max</th></tr>${rows}`;
}

let lastHistory = {};
function redrawCharts() {
  for (const figure of document.querySelectorAll(".chart")) drawChart(figure, lastHistory);
  drawSparklines(lastHistory);
}

// Each sparkline scales to its own range, so it shows the trend; the number shows the value
function sparkline(svg, values) {
  const points = values.filter((v) => v != null);
  if (points.length < 2) { svg.innerHTML = ""; return; }
  let lo = Math.min(...points), hi = Math.max(...points);
  if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
  const step = 70 / (points.length - 1);
  const line = points.map((v, i) => `${(i * step).toFixed(1)},${(17 - ((v - lo) / (hi - lo)) * 16).toFixed(1)}`);
  svg.innerHTML = `<polyline points="${line.join(" ")}"></polyline>`;
}

function drawSparklines(history) {
  for (const bar of document.querySelectorAll(".bar[data-bar]")) {
    const series = history[bar.dataset.bar];
    for (const [cls, key, unit] of [["temp", "boardtemp", "°C"], ["cur", "current", "mA"]]) {
      const spark = bar.querySelector(`.spark.${cls}`);
      const values = (series?.[key] || []).map((v) => magnitude(key, v));
      const last = values.length ? values[values.length - 1] : null;
      sparkline(spark.querySelector("svg"), values);
      spark.querySelector(".value").textContent = last == null ? "" : `${last.toFixed(1)} ${unit}`;
    }
  }
}

async function drawCharts() {
  try {
    lastHistory = await api("GET", "/api/history");
    redrawCharts();
  } catch (error) {
    showError(`history: ${error.message}`);
  }
}

document.getElementById("charts").addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-bar]");
  if (!row) return;
  const name = row.dataset.bar;
  if (hiddenBars.has(name)) hiddenBars.delete(name); else hiddenBars.add(name);
  redrawCharts();
});
setInterval(drawCharts, 10000);
drawCharts();

let drivesOutlet = null;

async function pollPower() {
  const chip = document.getElementById("power-chip");
  if (!chip) return;
  try {
    const status = await api("GET", "/api/power");
    drivesOutlet = status.outlets.find((outlet) => outlet.switchable) || null;
    const others = status.outlets.filter((outlet) => !outlet.switchable);
    chip.title = others.map((o) => `${o.label}: ${o.on ? "on" : "off"}, ${o.power.toFixed(1)} W`).join("\n");
    if (drivesOutlet) {
      document.getElementById("power-text").textContent =
        `Drives ${drivesOutlet.on ? "on" : "off"}, ${drivesOutlet.power.toFixed(1)} W`;
      chip.className = `chip ${drivesOutlet.on ? "ok" : "bad"}`;
      const button = document.getElementById("power-switch");
      button.textContent = drivesOutlet.on ? "Power off" : "Power on";
      button.disabled = !inControl;
    }
    if (status.error) showError(`PDU: ${status.error}`);
  } catch (error) {
    showError(`PDU: ${error.message}`);
  }
}

document.getElementById("power-switch")?.addEventListener("click", () => {
  if (drivesOutlet) switchPower(drivesOutlet);
});

async function switchPower(outlet) {
  const on = !outlet.on;
  if (!on && !confirm(`Switch ${outlet.label} off?`)) return;
  try {
    await api("POST", `/api/power/${outlet.name}`, { on });
    pollPower();
  } catch (error) {
    showError(error.message);
  }
}
setInterval(pollPower, 5000);
pollPower();

// The layout records which way a positive move takes each bar on screen
function signedStep(name, towards) {
  const step = Math.abs(parseFloat(document.getElementById("step").value));
  const plus = layout.bars[name]?.plus ?? "right";
  return towards === plus ? step : -step;
}

panel.querySelector("#panel-actions").addEventListener("click", async (event) => {
  const action = event.target.dataset.action;
  if (!action || !chosenBar) return;
  const velocity = parseFloat(document.getElementById("velocity").value);
  try {
    if (action.startsWith("move-")) {
      const distance = signedStep(chosenBar, action.slice("move-".length));
      await api("POST", `/api/axes/${chosenBar}/move_relative`, { distance, velocity });
    } else {
      await api("POST", `/api/axes/${chosenBar}/${action}`, {});
    }
    showMessage("");
  } catch (error) {
    showError(`${chosenBar} ${action}: ${error.message}`);
  }
});

function render(status) {
  inControl = status.in_control;
  document.getElementById("control-state").textContent = status.controller
    ? (inControl ? "You are in control" : `${status.controller} is in control`)
    : "Nobody is in control";
  document.getElementById("take").hidden = inControl;
  document.getElementById("password").hidden = inControl;
  document.getElementById("release").hidden = !inControl;
  if (status.error) showError(`PLC: ${status.error}`);
  const plc = document.getElementById("plc-state");
  plc.textContent = `PLC: ${status.plc ?? "–"}`;
  plc.className = `chip ${status.plc === "run" ? "ok" : "bad"}`;
  if (!document.querySelector(".bar")) {
    buildCsu(status.axes);
    drawSparklines(lastHistory);
  }
  axesByName = Object.fromEntries(status.axes.map((axis) => [axis.name, axis]));
  for (const axis of status.axes) renderBar(axis);
  renderPanel();
}

let shownPresets = "";

function presetButton(label, title, onClick, className = "") {
  const button = document.createElement("button");
  button.textContent = label;
  button.title = title;
  button.className = className;
  button.addEventListener("click", onClick);
  return button;
}

function renderPresets(names) {
  if (selected && !names.includes(selected.name)) selected = null;
  const key = [...names, selected?.name, inControl].join("\u0000");
  if (key !== shownPresets) {
    shownPresets = key;
    document.getElementById("preset-list").replaceChildren(...names.map((name) => {
      const group = document.createElement("span");
      group.className = "preset";
      group.append(
        presetButton(name, `Show "${name}" on the bars`, () => togglePreset(name),
                     selected?.name === name ? "selected" : "small"),
        presetButton("Go", `Move every enabled bar to "${name}"`, () => recallPreset(name), "control"),
        presetButton("✕", `Delete "${name}"`, () => deletePreset(name), "small control"),
      );
      return group;
    }));
  }
  for (const button of document.querySelectorAll("#presets .control, #preset-save")) {
    button.disabled = !inControl;
  }
}

async function togglePreset(name) {
  if (selected?.name === name) {
    selected = null;
  } else {
    try {
      selected = { name, bars: await api("GET", `/api/presets/${encodeURIComponent(name)}`) };
    } catch (error) {
      showError(error.message);
    }
  }
  poll();
}

async function recallPreset(name) {
  try {
    const result = await api("POST", `/api/presets/${encodeURIComponent(name)}/recall`);
    showNotice(result.skipped.length ? `${name}: left in place (disabled): ${result.skipped.join(", ")}` : "");
  } catch (error) {
    showError(error.message);
  }
}

async function deletePreset(name) {
  if (!confirm(`Delete save point "${name}"?`)) return;
  try {
    await api("DELETE", `/api/presets/${encodeURIComponent(name)}`);
    poll();
  } catch (error) {
    showError(error.message);
  }
}

document.getElementById("preset-save").addEventListener("click", async () => {
  const field = document.getElementById("preset-name");
  try {
    await api("POST", "/api/presets", { name: field.value });
    field.value = "";
    showMessage("");
    poll();
  } catch (error) {
    showError(error.message);
  }
});

async function poll() {
  try {
    const status = await api("GET", "/api/status");
    render(status);
    renderPresets(status.presets);
  } catch (error) {
    showError(`status: ${error.message}`);
  }
}

document.getElementById("take").addEventListener("click", async () => {
  try {
    const password = document.getElementById("password");
    await api("POST", "/api/control", { password: password.value });
    password.value = "";
    poll();
  } catch (error) {
    showError(error.message);
  }
});
document.getElementById("release").addEventListener("click", async () => {
  await api("DELETE", "/api/control");
  poll();
});
document.getElementById("stop-all").addEventListener("click", () =>
  api("POST", "/api/stop").catch((error) => showError(error.message)));

// Renew the lease well inside its lifetime while this page holds control
setInterval(() => {
  if (inControl) api("POST", "/api/control", {}).catch((error) => showError(error.message));
}, (LEASE_S * 1000) / 3);

// Reopen the webcam stream if it breaks, so a network hiccup does not leave a dead image
const cameraImage = document.querySelector("#camera img");
if (cameraImage) {
  const streamUrl = cameraImage.src;
  cameraImage.addEventListener("error", () => {
    setTimeout(() => { cameraImage.src = `${streamUrl}?t=${Date.now()}`; }, 1000);
  });
}

api("GET", "/api/layout").then((loaded) => { layout = loaded; }).catch((error) => showError(error.message))
  .finally(() => { setInterval(poll, 500); poll(); });
