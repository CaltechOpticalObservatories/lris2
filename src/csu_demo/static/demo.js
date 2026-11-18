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
                   <span class="state"></span><span class="saved"></span>`;
  bar.addEventListener("click", () => chooseBar(name));
  return bar;
}

function buildCsu(axes) {
  const csu = document.getElementById("csu");
  const cells = [];
  for (let row = 1; row <= layout.rows; row += 1) {
    for (const side of ["left", "right"]) {
      const cell = document.createElement("div");
      cell.className = `slot ${side}`;
      cell.style.gridRow = row;
      cell.id = `slot-${side}-${row}`;
      cells.push(cell);
    }
    const slit = document.createElement("div");
    slit.className = "slit";
    slit.style.gridRow = row;
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
  panel.hidden = !axis;
  if (!axis) return;
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
  drawCharts();
}

// Draw one reading as a line scaled to its own range, with the range and age as labels
function drawChart(svg, times, values) {
  const points = times.map((t, i) => [t, values[i]]).filter(([, v]) => v !== null);
  if (points.length < 2) {
    svg.innerHTML = '<text x="6" y="44">collecting… one sample every 10 s</text>';
    return;
  }
  const [t0, t1] = [points[0][0], points[points.length - 1][0]];
  let lo = Math.min(...points.map(([, v]) => v));
  let hi = Math.max(...points.map(([, v]) => v));
  if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
  const x = (t) => 2 + ((t - t0) / Math.max(t1 - t0, 1)) * 296;
  const y = (v) => 74 - ((v - lo) / (hi - lo)) * 66;
  const line = points.map(([t, v]) => `${x(t).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const minutes = Math.round((t1 - t0) / 60);
  svg.innerHTML = `<polyline points="${line}"></polyline>` +
    `<text x="4" y="10">${hi.toFixed(1)}</text><text x="4" y="78">${lo.toFixed(1)}</text>` +
    `<text x="240" y="78">last ${minutes} min</text>`;
}

async function drawCharts() {
  if (!chosenBar) return;
  try {
    const series = await api("GET", `/api/axes/${encodeURIComponent(chosenBar)}/history`);
    for (const key of ["boardtemp", "current"]) {
      drawChart(document.getElementById(`chart-${key}`), series.time, series[key] || []);
    }
  } catch (error) {
    showError(`history: ${error.message}`);
  }
}
setInterval(drawCharts, 10000);

async function pollPower() {
  const list = document.getElementById("power-list");
  if (!list) return;
  try {
    const status = await api("GET", "/api/power");
    list.replaceChildren(...status.outlets.map((outlet) => {
      const item = document.createElement("span");
      item.className = `outlet ${outlet.on ? "on" : "off"}`;
      item.textContent = `${outlet.label}: ${outlet.on ? "on" : "off"}, ${outlet.power.toFixed(1)} W, ${outlet.current.toFixed(2)} A `;
      if (outlet.switchable) {
        const button = document.createElement("button");
        button.textContent = outlet.on ? "Power off" : "Power on";
        button.disabled = !inControl;
        button.addEventListener("click", () => switchPower(outlet));
        item.append(button);
      }
      return item;
    }));
    if (status.error) showError(`PDU: ${status.error}`);
  } catch (error) {
    showError(`PDU: ${error.message}`);
  }
}

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
  if (!document.querySelector(".bar")) buildCsu(status.axes);
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
