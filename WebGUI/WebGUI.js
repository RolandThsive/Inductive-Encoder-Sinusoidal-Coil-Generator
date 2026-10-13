/* WebGUI.js - the page: Basic and Advanced controls, the preview, the checks and the downloads.

   The generator itself runs in PyodideWorker.js.  Every value lives in one object (state.values) that both
   modes edit; the parameter list, defaults, help texts and the "is this used now" rules all come from the
   generator's own files (ParameterChecker.SPEC and the parameter files), so this page never drifts from them. */

"use strict";

/* ---- where things come from ------------------------------------------------------------------- */
const QUERY = new URLSearchParams(location.search);
const CONFIG = {
  pyodideBase: QUERY.get("pyodide") || "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/",
  codeBase: QUERY.get("code") || new URL("../", location.href).href,    // the repository root
  blogHome: "https://ro-h-bots.blogspot.com/",
};

/* ---- the starting design (Roland's default) -------------------------------------------------- */
const START_DESIGN = {
  PCB_LAYERS: 2, INNER_EDGE_RADIUS_MM: 25, OUTER_EDGE_RADIUS_MM: 50,
  LOOPS: 4, RX_SUBCOILS: 1, TX_TURNS: 3, AIR_GAP_MM: 1.0,
  TX_LAYERS: 1, TX_LAYER_A: 4, TX_LAYER_B: 1, TX_SERIES: true,
};

const LAYER_NUM_NAME = { 1: "Top", 2: "Inner-1", 3: "Inner-2", 4: "Bottom" };
const LAYER_NUM_CU = { 1: "F.Cu", 2: "In1.Cu", 3: "In2.Cu", 4: "B.Cu" };
const CU_NAME = { "F.Cu": "Top", "In1.Cu": "Inner-1", "In2.Cu": "Inner-2", "B.Cu": "Bottom" };

/* TX layouts offered in Basic (from the examples in TX_Parameters.py) */
const PRESETS = [
  { id: "2-bottom", layers: 2, name: "Single On Bottom", note: "The original, proven layout",
    set: { PCB_LAYERS: 2, TX_LAYERS: 1, TX_LAYER_A: 4, TX_LAYER_B: 1, TX_SERIES: true } },
  { id: "2-top", layers: 2, name: "Single On Top", note: "Next to the rotor: more signal in the model",
    set: { PCB_LAYERS: 2, TX_LAYERS: 1, TX_LAYER_A: 1, TX_LAYER_B: 4, TX_SERIES: true } },
  { id: "2-series", layers: 2, name: "Series Top + Bottom", note: "Hoxha et al. 2022, go-around fingers",
    set: { PCB_LAYERS: 2, TX_LAYERS: 2, TX_LAYER_A: 1, TX_LAYER_B: 4, TX_SERIES: true } },
  { id: "4-bottom", layers: 4, name: "Single On Bottom", note: "RX on Top + Inner-1",
    set: { PCB_LAYERS: 4, TX_LAYERS: 1, TX_LAYER_A: 4, TX_LAYER_B: 1, TX_SERIES: true, RX_LAYER_A: 1, RX_LAYER_B: 2 } },
  { id: "4-renesas", layers: 4, name: "Series Top + Inner-2", note: "The Renesas IPS2200 reference",
    set: { PCB_LAYERS: 4, TX_LAYERS: 2, TX_LAYER_A: 1, TX_LAYER_B: 3, TX_SERIES: true, RX_LAYER_A: 1, RX_LAYER_B: 2 } },
  { id: "4-inner1", layers: 4, name: "Series Top + Inner-1", note: "As in TX_Parameters.py",
    set: { PCB_LAYERS: 4, TX_LAYERS: 2, TX_LAYER_A: 1, TX_LAYER_B: 2, TX_SERIES: true, RX_LAYER_A: 1, RX_LAYER_B: 2 } },
];
const BASIC_NAMES = new Set(["INNER_EDGE_RADIUS_MM", "OUTER_EDGE_RADIUS_MM", "LOOPS", "RX_SUBCOILS",
  "RX_SUBCOIL_SPLIT_ELEC_DEG", "TX_TURNS", "PCB_LAYERS", "TX_LAYERS", "TX_LAYER_A", "TX_LAYER_B", "TX_SERIES",
  "RX_LAYER_A", "RX_LAYER_B", "AIR_GAP_MM", "TX_START_ANGLE_DEG"]);

/* nicer names for the parameter files' section headings */
const GROUP_TITLES = {
  "Output": "Output (Fixed In The Web Version)",
  "Board outline (Edge.Cuts circles)": "Board Outline",
  "Mechanical / Physical Assumptions": "Mechanical Assumptions",
  "Tx Layers": "TX Layers",
  "SERIES block (TX_SERIES = True, and every TX on one layer)": "Series TX",
  "PARALLEL block (TX_LAYERS = 2 and TX_SERIES = False)": "Parallel TX",
  "According_to_stator": "Automatic Rotor",
  "Outer edge of the copper: over the TX turns (default)": "Automatic Rotor: Edges",
  "Custom": "Custom Rotor",
  "Both modes": "Both Rotor Modes",
};
// The Output block (folder, file names, board centre, page size; read only on the web) is kept but not shown for
// now. Set to true to show it again; see FutureConsiderations.md.
const SHOW_OUTPUT_GROUP = false;
const TAB_TITLES = { "Board_Parameters.py": "Board", "RX_Parameters.py": "RX", "TX_Parameters.py": "TX", "Rotor_Parameters.py": "Rotor" };
const FILE_GROUP_GENERAL = { "TX_Parameters.py": "TX Turns", "Rotor_Parameters.py": "Rotor Mode" };

/* human labels for Advanced fields: the parameter name in capitalised words */
// names the word rule below would make unclear
const LABELS = { RX_NET_PHASE_0_2: "RX Net SIN (Phases 0 / 2)", RX_NET_PHASE_1_3: "RX Net COS (Phases 1 / 3)" };
function labelOf(name) {
  if (LABELS[name]) return { text: LABELS[name], unit: "" };
  const special = { MM: "(mm)", DEG: "(deg)", HZ: "(Hz)", UM: "(µm)" };
  const parts = name.split("_");
  let unit = "";
  if (special[parts[parts.length - 1]]) unit = special[parts.pop()];
  const words = parts.map((w) => (["RX", "TX", "PCB", "IC"].includes(w) ? w : w[0] + w.slice(1).toLowerCase()));
  return { text: words.join(" "), unit };
}

/* ---- state --------------------------------------------------------------------------------------- */
const state = {
  spec: [], byName: {}, values: {}, start: {}, inactive: new Set(),
  mode: "basic", advTab: "Board_Parameters.py", ready: false, busy: false,
  result: null, stale: false, preset: "2-bottom", showInfo: false,
};
const $ = (id) => document.getElementById(id);

/* ---- worker ---------------------------------------------------------------------------------------- */
let worker, nextId = 1;
const pending = new Map();
function ask(cmd, args) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, cmd, args });
  });
}
function startWorker() {
  worker = new Worker("PyodideWorker.js", { type: "module" });
  worker.onmessage = (ev) => {
    const m = ev.data;
    if (m.type === "progress") { setProgressText(m.text); return; }
    const p = pending.get(m.id); if (!p) return;
    pending.delete(m.id);
    m.ok ? p.resolve(m.result) : p.reject(new Error(m.error));
  };
  worker.onerror = (e) => fatal("The Python worker stopped: " + (e.message || e));
}

/* ---- small helpers ------------------------------------------------------------------------------- */
function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v === true) e.setAttribute(k, "");
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k.nodeType ? k : document.createTextNode(k));
  return e;
}
function same(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
function fmt(x) { return typeof x === "number" ? String(Math.round(x * 1000) / 1000) : String(x); }
function toast(text) {
  const t = $("toast"); t.textContent = text; t.hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => (t.hidden = true), 2600);
}
function setProgressText(text) {
  if (!state.ready) $("btn-generate").textContent = text.replace("…", "") + "…";
  $("checks-list").innerHTML = "";
  $("checks-list").append(el("p", { class: "hint" }, text));
}
function busy(on) { state.busy = on; $("progress").classList.toggle("busy", on); }
function fatal(text) {
  busy(false);
  $("btn-generate").textContent = "Python Did Not Start";
  $("checks-list").innerHTML = "";
  $("checks-list").append(el("div", { class: "check error" }, el("span", { class: "lvl" }, "ERROR"), el("span", { class: "stage" }, "Start"), el("span", { class: "msg" }, text)));
}
function download(bytes, name, type = "application/zip") {
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const a = el("a", { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/* help pop-up */
function attachHelp(node, name, extra) {
  // hovering the label or its (i) shows the parameter's help, from the comments in the parameter files
  node.dataset.help = name;
  if (extra) node.dataset.helpExtra = extra;
  node.append(el("i", { class: "info-dot", "aria-label": "Help" }, "i"));
  return node;
}

/* ---- tooltips: every parameter (data-help = its name) and every button (data-tip = the text) ---- */
function showValue(v) {
  if (v === null || v === undefined) return "None";
  if (typeof v === "boolean") return v ? "True" : "False";
  if (Array.isArray(v)) return `(${v.map(showValue).join(", ")})`;
  if (typeof v === "string") return v;
  return fmt(v);
}
let tipTimer = null, tipFor = null;
function hideTip() { clearTimeout(tipTimer); tipFor = null; $("popover").hidden = true; }
function showTip(node) {
  const pop = $("popover");
  pop.innerHTML = "";
  if (node.dataset.help) {
    const name = node.dataset.help, p = state.byName[name];
    pop.append(el("span", { class: "mono-name" }, name));
    if (node.dataset.helpExtra) pop.append(node.dataset.helpExtra + "\n\n");
    pop.append((p && p.help) || "No notes in the parameter file.");
    if (name in state.start) pop.append(el("span", { class: "tip-foot" }, `Starting Value: ${showValue(state.start[name])}`));
  } else {
    pop.append(node.dataset.tip);
  }
  pop.hidden = false;
  const r = node.getBoundingClientRect();
  const below = r.bottom + 8, above = r.top - pop.offsetHeight - 8;
  pop.style.top = (below + pop.offsetHeight < window.innerHeight - 6 || above < 6 ? Math.max(6, Math.min(below, window.innerHeight - pop.offsetHeight - 6)) : above) + "px";
  pop.style.left = Math.max(6, Math.min(window.innerWidth - pop.offsetWidth - 6, r.left)) + "px";
}
document.addEventListener("mouseover", (e) => {
  const node = e.target.closest("[data-tip], [data-help]");
  if (node === tipFor) return;
  hideTip();
  if (!node || (node.dataset.tip !== undefined && !node.dataset.tip)) return;
  tipFor = node;
  tipTimer = setTimeout(() => showTip(node), e.target.closest(".info-dot") ? 0 : 450);
});
document.addEventListener("mousedown", hideTip);
document.addEventListener("scroll", hideTip, true);
function tip(node, text) { node.dataset.tip = text; return node; }

/* ---- value changes ----------------------------------------------------------------------------- */
function setValues(changes, from) {
  let any = false;
  for (const [k, v] of Object.entries(changes)) {
    if (!same(state.values[k], v)) { state.values[k] = v; any = true; }
  }
  if (!any) return;
  if (state.result) { state.stale = true; }
  refreshAfterChange(from);
}
let inactiveTimer;
function refreshAfterChange(from) {
  updateStale();
  if (from !== "basic") renderBasic();
  if (from !== "advanced" && state.mode === "advanced") renderAdvanced();
  else if (state.mode === "advanced") markAdvanced();
  updateAdvNote();
  clearTimeout(inactiveTimer);
  inactiveTimer = setTimeout(async () => {
    if (!state.ready) return;
    try {
      state.inactive = new Set(await ask("inactive", { values: state.values }));
      if (state.mode === "advanced") markAdvanced();
    } catch (e) { /* the next change tries again */ }
  }, 150);
}
function updateStale() {
  const r = state.result, badge = $("stale-badge");
  const failed = r && !r.ok && view.hasBoard;
  badge.hidden = !((state.stale && r) || failed);
  placeBadge();
  for (const part of ["stator", "rotor"]) {
    const b = $(`btn-dl-${part}`), name = part === "stator" ? "stator" : "rotor";
    b.disabled = !(state.result && state.result.ok && state.result.files[part]) || state.stale;
    b.dataset.tip = state.stale ? "The settings changed: press Generate first"
      : `Download only the ${name} board of this run (${state.result && state.result.name ? state.result.name + "_" : ""}${part === "stator" ? "Stator" : "Rotor"}.kicad_pcb), ready to open in KiCad`;
  }
  const dl = $("btn-download");
  dl.disabled = !(state.result && state.result.ok) || state.stale;
  dl.dataset.tip = state.stale ? "The settings changed: press Generate first"
    : "Download this run as one zip: Stator.kicad_pcb, Rotor.kicad_pcb, Parameters.txt and the four parameter files";
}

/* The notice sits in the header, centred between Basic / Advanced and the buttons.  When that gap is too narrow
   (below about 1900 px) the title steps aside while the notice shows, and the notice is centred in the title's place. */
function placeBadge() {
  const badge = $("stale-badge"), bar = $("topbar"), h1 = bar.querySelector("h1");
  badge.classList.remove("in-title"); badge.style.left = ""; h1.classList.remove("yield");
  if (badge.hidden) return;
  badge.textContent = state.stale ? "Settings changed: press Generate to update the board"
    : "Not generated: this is the last board that worked";
  const b = badge.getBoundingClientRect(), ms = $("mode-switch").getBoundingClientRect();
  const ta = bar.querySelector(".top-actions").getBoundingClientRect();
  const x0 = bar.getBoundingClientRect().left;
  if (b.width <= ta.left - ms.right - 24) { badge.style.left = `${(ms.right + ta.left) / 2 - x0}px`; return; }
  const t = h1.getBoundingClientRect();
  h1.classList.add("yield"); badge.classList.add("in-title");
  const right = Math.min(t.right, ms.left - 12);
  badge.style.left = `${(t.left + right) / 2 - x0}px`;
  if (badge.getBoundingClientRect().width > right - t.left)
    badge.textContent = state.stale ? "Settings changed: press Generate" : "Not generated: last good board shown";
}
window.addEventListener("resize", placeBadge);

/* ---- Basic mode ------------------------------------------------------------------------------- */
function presetOf(v) {
  for (const p of PRESETS) {
    if (Object.entries(p.set).every(([k, x]) => {
      if (k === "TX_LAYER_B" && v.TX_LAYERS === 1) return true;            // not used by a one-layer TX
      if ((k === "RX_LAYER_A" || k === "RX_LAYER_B") && v.PCB_LAYERS === 2) return true;
      return same(v[k], x);
    })) return p.id;
  }
  return null;
}

function numberField({ name, label, unit, min, max, step, slider, ticks, note }) {
  const v = state.values[name];
  const input = el("input", { type: "text", inputmode: "decimal", value: fmt(v), "aria-label": label });
  const range = slider ? el("input", { type: "range", min: slider[0], max: slider[1], step, value: v, "aria-label": label }) : null;
  const clamp = (x) => Math.min(max, Math.max(min, x));
  const commit = (x, src) => {
    if (!Number.isFinite(x)) { input.value = fmt(state.values[name]); return; }
    x = clamp(Math.round(x / step) * step);
    x = Math.round(x * 1000) / 1000;
    if (src !== "input") input.value = fmt(x);
    if (range && src !== "range") range.value = x;
    basicChange(name, x);
  };
  input.addEventListener("change", () => commit(parseFloat(input.value), "change"));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); commit((parseFloat(input.value) || 0) + (e.key === "ArrowUp" ? step : -step)); }
  });
  if (range) range.addEventListener("input", () => commit(parseFloat(range.value), "range"));
  const stepper = el("span", { class: "stepper" },
    el("button", { type: "button", "aria-label": "Less", onclick: () => commit(state.values[name] - step) }, "−"),
    input,
    el("button", { type: "button", "aria-label": "More", onclick: () => commit(state.values[name] + step) }, "+"));
  const head = el("div", { class: "field-head" }, el("span", { class: "field-label" }, label, unit ? el("span", { class: "unit" }, ` (${unit})`) : null));
  attachHelp(head, name);
  if (note !== undefined) head.append(el("span", { class: "field-note", "data-note": name }, note));
  // tick labels sit under the track itself, each at its value (the thumb is 20 px, so the track runs 10 px in)
  const track = range && ticks ? el("div", { class: "range-wrap" }, range, el("div", { class: "ticks" }, ticks.map((t) =>
    el("span", { style: `left: calc(10px + (100% - 20px) * ${(parseFloat(t) - slider[0]) / (slider[1] - slider[0])})` }, t)))) : range;
  return el("div", { class: "field" + (track !== range ? " has-ticks" : "") }, head, el("div", { class: "num-row" }, stepper, track));
}

function segmentedField({ name, label, options, note, onPick }) {
  const head = el("div", { class: "field-head" }, el("span", { class: "field-label" }, label));
  attachHelp(head, name);
  if (note !== undefined) head.append(el("span", { class: "field-note", "data-note": name }, note));
  const seg = el("div", { class: "segmented" });
  for (const [val, text] of options) {
    seg.append(el("button", { type: "button", class: same(state.values[name], val) ? "on" : "",
      onclick: (e) => {
        if (onPick) { onPick(val); return; }
        seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === e.currentTarget));
        basicChange(name, val);
      } }, text));
  }
  return el("div", { class: "field" }, head, seg);
}

function presetCard(p, selected) {
  const v = Object.assign({}, state.values, p.set);
  const layers = p.layers === 2 ? [1, 4] : [1, 2, 3, 4];
  const rx = p.layers === 2 ? [1, 4] : [v.RX_LAYER_A, v.RX_LAYER_B];
  const tx = v.TX_LAYERS === 2 ? [v.TX_LAYER_A, v.TX_LAYER_B] : [v.TX_LAYER_A];
  const W = 100, H = 54, gap = H / (layers.length + 1);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  let s = `<rect x="2" y="${gap / 2}" width="${W - 4}" height="${H - gap}" rx="3" fill="#e8dcc4" opacity="0.55"/>`;
  layers.forEach((n, i) => {
    const y = gap * (i + 1), cu = LAYER_NUM_CU[n], col = `var(${LAYER_INFO[cu].css})`;
    if (rx.includes(n)) s += `<path d="M8 ${y} q8 -5 16 0 t16 0 t16 0" stroke="${col}" stroke-width="1.6" fill="none"/>`;
    if (tx.includes(n)) for (let k = 0; k < 3; k++) s += `<rect x="${64 + k * 10}" y="${y - 2.2}" width="7" height="4.4" rx="1" fill="${col}"/>`;
  });
  svg.innerHTML = s;
  return el("div", { class: "slide" + (selected ? " selected" : ""), "data-tip": `${p.name}: ${p.note}`, role: "button", tabindex: 0,
    onclick: () => pickPreset(p.id),
    onkeydown: (e) => (e.key === "Enter" || e.key === " ") && pickPreset(p.id) },
    svg, el("div", { class: "slide-name" }, p.name));
}

function pickPreset(id) {
  const p = PRESETS.find((x) => x.id === id);
  state.preset = id;
  setValues(Object.assign({}, p.set), "basic-preset");
}

function basicChange(name, value) {
  const ch = { [name]: value };
  if (name === "RX_SUBCOILS") ch.RX_SUBCOIL_SPLIT_ELEC_DEG = value === 3 ? 30 : 45;   // as the parameter file advises
  const loops = name === "LOOPS" ? value : state.values.LOOPS;
  const subs = name === "RX_SUBCOILS" ? value : state.values.RX_SUBCOILS;
  if (name === "LOOPS" || name === "RX_SUBCOILS") {
    // many fingers: put the TX tail in the widest gap between them (TX_START_ANGLE_DEG = "auto")
    ch.TX_START_ANGLE_DEG = loops >= 8 || subs >= 2 ? "auto" : state.start.TX_START_ANGLE_DEG;
  }
  setValues(ch, "basic");
  updateBasicNotes();
  renderResults();
}

function noteFor(name) {
  const v = state.values;
  if (name === "LOOPS") return `Range: ${fmt(v.LOOPS ? 360 / v.LOOPS : 360)}°`;
  if (name === "RX_SUBCOILS") return v.RX_SUBCOILS > 1 ? `Split: ${fmt(v.RX_SUBCOIL_SPLIT_ELEC_DEG)}° el` : "";
  if (name === "TX_TURNS") return `Total: ${v.TX_LAYERS === 2 ? v.TX_TURNS * 2 : v.TX_TURNS}`;
  return "";
}
function updateBasicNotes() {
  document.querySelectorAll("#basic-controls [data-note]").forEach((n) => (n.textContent = noteFor(n.dataset.note)));
}

function renderBasic() {
  const box = $("basic-controls");
  const scroll = $("basic-panel").scrollTop;
  box.innerHTML = "";
  const v = state.values;
  box.append(
    numberField({ name: "INNER_EDGE_RADIUS_MM", label: "Board Inner Radius", unit: "mm", min: 1, max: 200, step: 0.5, slider: [5, 120] }),
    numberField({ name: "OUTER_EDGE_RADIUS_MM", label: "Board Outer Radius", unit: "mm", min: 5, max: 250, step: 0.5, slider: [10, 150] }),
    numberField({ name: "LOOPS", label: "Loops", min: 1, max: 16, step: 1, slider: [1, 16],
      note: noteFor("LOOPS"), ticks: ["1", "4", "8", "12", "16"] }),
    segmentedField({ name: "RX_SUBCOILS", label: "RX Sub-Coils", options: [[1, "1 (None)"], [2, "2"], [3, "3"]],
      note: noteFor("RX_SUBCOILS") }),
    numberField({ name: "TX_TURNS", label: "TX Turns Per Layer", min: 1, max: 12, step: 1,
      note: noteFor("TX_TURNS") }),
    segmentedField({ name: "PCB_LAYERS", label: "Board Layers", options: [[2, "2 Layers"], [4, "4 Layers"]],
      onPick: (n) => { if (n !== v.PCB_LAYERS) pickPreset(n === 2 ? "2-bottom" : "4-inner1"); } }),
  );
  // TX layout cards
  const current = presetOf(v);
  const head = el("div", { class: "field-head" }, el("span", { class: "field-label" }, "TX Layout"));
  attachHelp(head, "TX_LAYERS");
  head.append(el("span", { class: "field-note" }, current ? PRESETS.find((p) => p.id === current).note : "Custom (set in Advanced)"));
  const slider = el("div", { class: "slider" });
  for (const p of PRESETS.filter((p) => p.layers === v.PCB_LAYERS)) slider.append(presetCard(p, p.id === current));
  box.append(el("div", { class: "field" }, head, slider));
  box.append(numberField({ name: "AIR_GAP_MM", label: "Air Gap", unit: "mm", min: 0.1, max: 10, step: 0.1, slider: [0.2, 5] }));
  $("basic-panel").scrollTop = scroll;
  updateAdvNote();
}

function updateAdvNote() {
  const n = state.spec.filter((p) => !p.readOnly && !BASIC_NAMES.has(p.name) && !same(state.values[p.name], state.start[p.name])).length;
  let note = $("basic-adv-note");
  if (!note) { note = el("p", { id: "basic-adv-note", class: "hint" }); $("basic-panel").append(note); }
  note.textContent = n ? `Advanced: ${n} more setting${n > 1 ? "s" : ""} changed.` : "";
}

/* ---- Advanced mode -------------------------------------------------------------------------- */
function choiceText(name, val) {
  if (val === "auto") return "Auto";
  // layer numbers (TX_LAYER_A, RX_TAB_LAYER, ...) read as layer names; layer counts (PCB_LAYERS, TX_LAYERS) as counts
  if (typeof val === "number" && /LAYERS$/.test(name)) return `${val} Layer${val === 1 ? "" : "s"}`;
  if (typeof val === "number" && /LAYER(_[AB])?$/.test(name) && LAYER_NUM_NAME[val]) return LAYER_NUM_NAME[val];
  if (CU_NAME[val]) return CU_NAME[val];
  if (typeof val === "boolean") return val ? "True" : "False";
  if (typeof val === "string") return val.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ");
  return String(val);
}

function dropdown(name, options, value, onPick) {
  const dd = el("div", { class: "dropdown" });
  const btn = el("button", { type: "button", class: "dropdown-btn" },
    el("span", {}, choiceText(name, value)), el("span", { class: "arrow" }, "▾"));
  const menu = el("div", { class: "dropdown-content" });
  for (const o of options) {
    menu.append(el("a", { class: same(o, value) ? "on" : "", onclick: () => { dd.classList.remove("open"); onPick(o); } }, choiceText(name, o)));
  }
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    document.querySelectorAll(".dropdown.open").forEach((d) => d !== dd && d.classList.remove("open"));
    dd.classList.toggle("open");
  });
  dd.append(btn, menu);
  return dd;
}
document.addEventListener("click", () => document.querySelectorAll(".dropdown.open").forEach((d) => d.classList.remove("open")));

function advStepper(value, onCommit, { step = 0.1, integer = false, disabled = false } = {}) {
  const input = el("input", { type: "text", inputmode: "decimal", value: value == null ? "" : fmt(value), disabled });
  const len = (value == null ? "" : fmt(value)).length;
  if (len > 5) input.style.width = `${len + 2}ch`;                      // 3500000 Hz fits
  const commit = (x) => {
    if (!Number.isFinite(x)) { input.value = value == null ? "" : fmt(value); return; }
    if (integer) x = Math.round(x);
    onCommit(Math.round(x * 1e6) / 1e6);
  };
  input.addEventListener("change", () => commit(parseFloat(input.value)));
  return el("span", { class: "stepper" },
    el("button", { type: "button", disabled, onclick: () => commit((value ?? 0) - step) }, "−"), input,
    el("button", { type: "button", disabled, onclick: () => commit((value ?? 0) + step) }, "+"));
}

function stepOf(p) {
  const d = p.default;
  if (p.kind === "int") return 1;
  if (p.kind === "steps") return 8;
  if (/HZ$/.test(p.name)) return 100000;
  if (/DEG$/.test(p.name)) return 1;
  if (typeof d === "number" && Math.abs(d) >= 100) return 1;
  if (typeof d === "number" && String(d).includes(".") && String(d).split(".")[1].length >= 2) return 0.05;
  return 0.1;
}

function advancedWidget(p) {
  const name = p.name, v = state.values[name], ro = p.readOnly;
  const set = (x) => setValues({ [name]: x }, "advanced-field");
  const k = p.kind, o = p.options || {};
  if (ro) return el("input", { class: "text-input", value: Array.isArray(v) ? v.join(", ") : String(v), disabled: true });
  if (k === "bool") {
    const cb = el("input", { type: "checkbox" }); cb.checked = !!v;
    cb.addEventListener("change", () => set(cb.checked));
    return el("label", { class: "switch-row" }, el("span", { class: "switch" }, cb, el("span", { class: "knob" })), v ? "On" : "Off");
  }
  if (k === "choice" || k === "ic") {
    let values = o.values || [];
    const current = typeof v === "string" && o.ci ? v.toLowerCase() : v;
    if (values.length <= 3 && values.every((x) => choiceText(name, x).length <= 12)) {
      const seg = el("div", { class: "segmented" });
      for (const x of values) seg.append(el("button", { type: "button", class: same(current, x) ? "on" : "", onclick: () => set(x) }, choiceText(name, x)));
      return seg;
    }
    return dropdown(name, values, current, set);
  }
  if (k === "num" || k === "int" || k === "mask_expansion") {
    return advStepper(v, set, { step: stepOf(p), integer: k === "int" });
  }
  if (k === "num_or_none" || k === "auto_or_num" || k === "steps") {
    const isAuto = k === "num_or_none" ? v === null : (typeof v === "string" && v.toLowerCase() === "auto");
    const autoWord = k === "num_or_none" ? "None" : "Auto";
    const cb = el("input", { type: "checkbox" }); cb.checked = isAuto;
    const fallback = typeof p.default === "number" ? p.default : (k === "steps" ? 200 : (o.lo ?? 1));
    const lastNumber = isAuto ? (state.lastNumbers[name] ?? fallback) : v;
    cb.addEventListener("change", () => {
      if (cb.checked) { state.lastNumbers[name] = typeof v === "number" ? v : lastNumber; set(k === "num_or_none" ? null : "auto"); }
      else set(lastNumber);
    });
    return el("div", { class: "auto-row" },
      el("label", { class: "switch-row" }, el("span", { class: "switch" }, cb, el("span", { class: "knob" })), autoWord),
      advStepper(isAuto ? null : v, set, { step: stepOf(p), integer: k === "steps", disabled: isAuto }));
  }
  if (k === "rotor_layers") {
    const box = el("div", { class: "auto-row" });
    for (const cu of ["F.Cu", "B.Cu"]) {
      const cb = el("input", { type: "checkbox" }); cb.checked = (v || []).includes(cu);
      cb.addEventListener("change", () => {
        const now = new Set(v || []); cb.checked ? now.add(cu) : now.delete(cu);
        set(["F.Cu", "B.Cu"].filter((x) => now.has(x)));
      });
      box.append(el("label", { class: "switch-row" }, el("span", { class: "switch" }, cb, el("span", { class: "knob" })), CU_NAME[cu]));
    }
    return box;
  }
  if (k === "pair") return el("input", { class: "text-input", value: (v || []).join(", "), disabled: true });
  // str, net, file
  const t = el("input", { class: "text-input", value: v ?? "" });
  t.addEventListener("change", () => set(t.value));
  return t;
}

function renderAdvanced() {
  const tabs = $("adv-tabs");
  tabs.innerHTML = "";
  for (const [file, title] of Object.entries(TAB_TITLES)) {
    tabs.append(el("button", { type: "button", class: file === state.advTab ? "on" : "", "data-tip": `The parameters in ${file}`,
      onclick: () => { state.advTab = file; renderAdvanced(); } }, title));
  }
  const box = $("advanced-controls");
  const scroll = $("advanced-panel").scrollTop;
  box.innerHTML = "";
  // a new rotor mode opens its own blocks and folds the other mode's, after the page is drawn (so it animates)
  const mode = String(state.values.ROTOR_MODE || "").toLowerCase(), modeChanged = mode !== state.rotorModeSeen;
  if (state.rotorModeSeen === undefined) foldRotorBlocks(mode);
  state.rotorModeSeen = mode;
  let group = null, card = null;
  for (const p of state.spec.filter((x) => x.file === state.advTab && (SHOW_OUTPUT_GROUP || x.group !== "Output"))) {
    let g = GROUP_TITLES[p.group] || p.group;
    if (g === "General") g = FILE_GROUP_GENERAL[p.file] || "General";
    if (g !== group) {
      group = g;
      const inner = el("div", { class: "group-inner" });
      const shell = el("div", { class: "group-card" + (state.folded.has(g) ? " collapsed" : ""), "data-group": g }, inner);
      if (ROTOR_MODE_GROUPS[g]) {
        box.append(el("button", { type: "button", class: "group-title foldable" + (state.folded.has(g) ? " collapsed" : ""), "data-group": g,
          "data-tip": `Show or hide the ${g.startsWith("Custom") ? "custom" : "automatic"} rotor settings (used when Rotor Mode is ${ROTOR_MODE_GROUPS[g]})`,
          onclick: () => { state.folded.has(g) ? state.folded.delete(g) : state.folded.add(g); applyFolds(); } },   // this block only
          el("span", { class: "chevron" }), g));
      } else box.append(el("div", { class: "group-title" }, g));
      box.append(shell);
      card = inner;
    }
    const lab = labelOf(p.name);
    const head = el("div", { class: "field-head" }, el("span", { class: "field-label" }, lab.text, lab.unit ? el("span", { class: "unit" }, " " + lab.unit) : null));
    attachHelp(head, p.name);
    head.append(el("span", { class: "field-note" }, el("span", { class: "mono-name" }, p.name)));
    if (!p.readOnly) head.append(el("button", { type: "button", class: "reset-one", "data-tip": "Back to the starting value",
      onclick: () => setValues({ [p.name]: state.start[p.name] }, "advanced-field") }, "↺"));
    card.append(el("div", { class: "field", "data-name": p.name }, head, advancedWidget(p)));
  }
  $("advanced-panel").scrollTop = scroll;
  markAdvanced();
  if (modeChanged) requestAnimationFrame(() => { foldRotorBlocks(mode); applyFolds(); });
}
/* The rotor blocks that belong to one Rotor Mode fold away when the other mode is chosen (the arrow opens them again). */
const ROTOR_MODE_GROUPS = { "Automatic Rotor": "according_to_stator", "Automatic Rotor: Edges": "according_to_stator", "Custom Rotor": "custom" };
state.folded = new Set();
function foldRotorBlocks(mode) {
  for (const [g, m] of Object.entries(ROTOR_MODE_GROUPS)) m === mode ? state.folded.delete(g) : state.folded.add(g);
}
function applyFolds() {
  document.querySelectorAll("#advanced-controls [data-group]").forEach((n) => n.classList.toggle("collapsed", state.folded.has(n.dataset.group)));
}
function markAdvanced() {
  document.querySelectorAll("#advanced-controls .field").forEach((f) => {
    const n = f.dataset.name;
    f.classList.toggle("inactive", state.inactive.has(n));
    f.classList.toggle("changed", !same(state.values[n], state.start[n]));
  });
}
// a field edited in Advanced redraws Advanced (widgets show the new value)

/* ---- mode switch -------------------------------------------------------------------------------- */
let modeTimer = null;
function setMode(mode) {
  if (mode === state.mode) return;
  state.mode = mode;
  document.querySelectorAll("#mode-switch button").forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
  // the panel widens (Advanced) or narrows (Basic) while the old controls fade out and the new ones fade in
  const ctr = $("controls");
  ctr.classList.remove("enter");
  ctr.classList.add("leave");
  $("app").classList.toggle("advanced", mode === "advanced");
  clearTimeout(modeTimer);
  modeTimer = setTimeout(() => {
    $("basic-panel").hidden = state.mode !== "basic";
    $("advanced-panel").hidden = state.mode !== "advanced";
    if (state.mode === "advanced") renderAdvanced(); else renderBasic();
    ctr.classList.remove("leave");
    void ctr.offsetWidth;                                  // restart the fade-in
    ctr.classList.add("enter");
  }, 180);
  setTimeout(() => view.resize(), 560);
}

/* ---- generate ---------------------------------------------------------------------------------- */
async function generate() {
  if (!state.ready || state.busy) return;
  busy(true);
  const btn = $("btn-generate");
  btn.disabled = true; btn.textContent = "Generating…";
  try {
    const sent = state.values;
    const r = await ask("generate", { values: sent, strict: $("strict").checked });
    state.result = r;
    state.stale = false;
    renderChecks();
    if (r.ok) {
      view.setBoards(r.files.stator, r.files.rotor, r.center);
      view.setNetRoles({ [sent.RX_NET_PHASE_0_2]: "sin", [sent.RX_NET_PHASE_1_3]: "cos", [sent.TX_NET]: "tx" });
      view.fit();
      $("btn-summary").disabled = false;
    }
    renderResults();
    updateCaption();
  } catch (e) {
    state.result = { ok: false, items: [{ stage: "Python", level: "error", msg: String(e.message || e) }], failed: "the generator stopped" };
    renderChecks();
  } finally {
    busy(false);
    btn.disabled = false; btn.textContent = "Generate";
    updateStale();
  }
}

function renderChecks() {
  const r = state.result, list = $("checks-list");
  list.innerHTML = "";
  if (!r) return;
  const items = r.items || [];
  const n = (l) => items.filter((i) => i.level === l).length;
  const ne = n("error"), nw = n("warning"), ni = n("info");
  const counts = $("counts");
  counts.innerHTML = "";
  if (r.ok) counts.append(el("span", { class: nw ? "w" : "ok" }, nw ? `${nw} Warning${nw > 1 ? "s" : ""}` : "No Warnings"),
    ` · ${ni} Info · ${r.name} · ${r.seconds ? r.seconds.toFixed(1) + " s" : ""}`);
  else counts.append(el("span", { class: "e" }, `Not Generated: ${r.failed}`), ne ? ` · ${ne} Error${ne > 1 ? "s" : ""}` : "", nw ? ` · ${nw} Warning${nw > 1 ? "s" : ""}` : "");
  const order = { error: 0, warning: 1, info: 2 };
  const shown = items.filter((i) => state.showInfo || i.level !== "info").sort((a, b) => order[a.level] - order[b.level]);
  for (const i of shown) {
    list.append(el("div", { class: "check " + i.level },
      el("span", { class: "lvl" }, i.level.toUpperCase()), el("span", { class: "stage" }, i.stage), el("span", { class: "msg" }, i.msg)));
  }
  if (!shown.length) list.append(el("p", { class: "hint" }, r.ok ? "Nothing to report. Turn on Info to see the generator's notes." : ""));
}

function renderResults() {
  const r = state.result, v = state.values, box = $("results");
  const parts = [`<b>Range:</b> ${fmt(360 / v.LOOPS)}° per period`];
  if (r && r.ok && !state.stale) {
    parts.push(`<b>RX Band:</b> ${fmt(r.rx.ri)} to ${fmt(r.rx.ro)} mm`);
    const m = /TX ring r = ([\d.]+) \.\.\. ([\d.]+) mm/.exec(r.summaries.stator);
    if (m) parts.push(`<b>TX Ring:</b> ${m[1]} to ${m[2]} mm`);
    parts.push(`<b>Board:</b> ${fmt(r.edges.inner)} to ${fmt(r.edges.outer)} mm`);
  }
  box.innerHTML = parts.join("<br>");
}

/* ---- preview tabs, layers ---------------------------------------------------------------------- */
let view;
function pickView(mode) {
  view.setMode(mode);
  document.querySelectorAll("#view-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.view === mode));
  $("rotor-angle-box").hidden = mode !== "overlay";
  renderNetToggles();
  view.fit();
  updateCaption();
}
function updateCaption() {
  const r = state.result, v = state.values, mode = view.mode;
  if (!r || !r.ok) {
    $("preview-caption").textContent = r ? "Not generated: see the checks below" : "Press Generate to make the boards";
    return;
  }
  const what = { stator: "Stator", rotor: "Rotor", overlay: "Stator With Rotor" }[mode];
  $("preview-caption").textContent = `${what}: ${r.name}`;
}
function renderLayerToggles() {
  const box = $("layer-toggles");
  box.innerHTML = "";
  for (const cu of ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]) {
    const chip = el("span", { class: "layer-chip" + (view.hidden.has(cu) ? " off" : ""), role: "switch",
      "data-tip": `Show or hide the ${CU_NAME[cu]} copper (${cu})`,
      onclick: () => { view.toggleLayer(cu); renderLayerToggles(); } },
      el("span", { class: "sw", style: `background: var(${LAYER_INFO[cu].css})` }), CU_NAME[cu]);
    box.append(chip);
  }
  // vias: hide / show like a layer; hovering makes tiny vias big enough to see (preview only)
  const off = view.hidden.has("Vias");
  const icon = el("span", { class: "via-icon" });
  const chip = el("span", { class: "layer-chip" + (off ? " off" : ""), role: "switch",
    "data-tip": off ? "Show the vias" : "Show or hide the vias. Hover to enlarge small vias to at least 6 px (the preview only, the boards are unchanged)",
    onclick: () => { view.setViaBoost(false); view.toggleLayer("Vias"); renderLayerToggles(); },
    onmouseenter: () => { if (!view.hidden.has("Vias")) view.setViaBoost(true); },
    onmouseleave: () => view.setViaBoost(false) }, icon, "Vias");
  box.append(chip);
}
// Sin / Cos / TX Loops and Origin (top right of the preview): hover highlights, click hides
const NET_BUTTONS = [
  { role: "sin", text: "Sin Loops", what: "the SIN coil (RX phases 0 / 2)", icon: "M1 7 C4 -1 6 -1 9 7 S14 15 17 7" },
  { role: "cos", text: "Cos Loops", what: "the COS coil (RX phases 1 / 3)", icon: "M1 3 C3 3 4 11 9 11 S15 3 17 3" },
  { role: "tx", text: "TX Loops", what: "the TX coil (the outer ring)", icon: "M9 1.5 A5.5 5.5 0 1 1 8.99 1.5 M9 4 A3 3 0 1 1 8.99 4" },
];
function renderNetToggles() {
  const box = $("net-toggles");
  box.innerHTML = "";
  for (const n of view.mode === "rotor" ? [] : NET_BUTTONS) {             // the rotor has no coils
    const off = view.hiddenNets.has(n.role);
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 18 14");
    icon.innerHTML = `<path d="${n.icon}"/>`;
    box.append(el("button", { type: "button", class: "net-btn" + (off ? " off" : ""), role: "switch", "aria-checked": String(!off),
      "data-tip": off ? `Show ${n.what}` : `Hover to highlight ${n.what}, click to hide it (the preview only)`,
      onclick: () => { view.toggleNet(n.role); view.setHighlight(null); renderNetToggles(); },
      onmouseenter: () => { if (!view.hiddenNets.has(n.role)) view.setHighlight(n.role); },
      onmouseleave: () => view.setHighlight(null) }, icon, n.text));
  }
  // the board centre: hover makes the marker bigger, click hides it
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 18 14");
  icon.innerHTML = `<circle cx="9" cy="7" r="1.8" fill="currentColor" stroke="none"/><circle cx="9" cy="7" r="4.6" stroke-width="1.1"/>`;
  box.append(el("button", { type: "button", class: "net-btn" + (view.showOrigin ? "" : " off"), role: "switch", "aria-checked": String(view.showOrigin),
    "data-tip": view.showOrigin ? "The board centre (origin). Hover to enlarge it, click to hide it" : "Show the board centre (origin)",
    onclick: () => { view.toggleOrigin(); view.setOriginBoost(false); renderNetToggles(); },
    onmouseenter: () => { if (view.showOrigin) view.setOriginBoost(true); },
    onmouseleave: () => view.setOriginBoost(false) }, icon, "Origin"));
}

/* ---- share, import, export ------------------------------------------------------------------- */
function encodeDesign() {
  const diff = {};
  for (const [k, v] of Object.entries(state.values)) if (!same(v, state.start[k])) diff[k] = v;
  const b = btoa(unescape(encodeURIComponent(JSON.stringify(diff))));
  return b.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function decodeDesign(hash) {
  const m = /[#&]d=([A-Za-z0-9_-]+)/.exec(hash || "");
  if (!m) return null;
  try {
    const b = m[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(decodeURIComponent(escape(atob(b))));
  } catch (e) { return null; }
}
async function share() {
  // embedded: the blog page tells us its address (a cross-origin referrer carries only the site)
  const base = window.self !== window.top ? (state.hostPage || document.referrer.split("#")[0] || CONFIG.blogHome)
    : location.href.split("#")[0];
  const d = encodeDesign();
  const link = d === "e30" ? base : `${base}#d=${d}`;              // "e30" is {}: the starting design
  try { await navigator.clipboard.writeText(link); toast("Link copied"); }
  catch (e) { window.prompt("Copy this link:", link); }
}
async function exportFiles() {
  if (!state.ready) return;
  try {
    const r = await ask("exportZip", { values: state.values });
    download(r.zipBytes, "Parameter_Files.zip");
  } catch (e) { toast("Export failed: " + e.message); }
}
async function importFiles(files) {
  let found = {};
  for (const f of files) {
    const text = await f.text();
    Object.assign(found, await ask("readValues", { text }));
  }
  const n = Object.keys(found).length;
  if (!n) { toast("No parameter values found in that file"); return; }
  setValues(found, "import");
  renderBasic();
  if (state.mode === "advanced") renderAdvanced();
  toast(`Loaded ${n} value${n > 1 ? "s" : ""}`);
}

/* ---- start -------------------------------------------------------------------------------------- */
async function main() {
  if (window.COILGEN_PHONE) return;                       // computers only: nothing loads on a phone
  state.lastNumbers = {};
  view = new BoardView($("board-canvas"), $("readout"));     // opens on Overlay
  renderLayerToggles();
  renderNetToggles();

  // wiring
  document.querySelectorAll("#mode-switch button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  document.querySelectorAll("#view-tabs button").forEach((b) => b.addEventListener("click", () => pickView(b.dataset.view)));
  $("btn-generate").addEventListener("click", generate);
  $("btn-download").addEventListener("click", () => state.result && state.result.ok && download(state.result.zipBytes, state.result.name + ".zip"));
  for (const part of ["stator", "rotor"]) {
    $(`btn-dl-${part}`).addEventListener("click", () => {
      const r = state.result;
      if (!r || !r.ok || state.stale || !r.files[part]) return;
      const file = part === "stator" ? "Stator" : "Rotor";
      download(r.files[part], `${r.name}_${file}.kicad_pcb`, "application/octet-stream");
    });
  }
  $("btn-fit").addEventListener("click", () => view.fit());
  $("btn-measure").addEventListener("click", (e) => {
    view.measure = !view.measure; view.mA = view.mB = null;
    e.currentTarget.classList.toggle("on", view.measure);
    $("board-canvas").classList.toggle("measuring", view.measure);
    view.draw();
  });
  $("btn-fullscreen").addEventListener("click", () => {
    const w = $("canvas-wrap");
    document.fullscreenElement ? document.exitFullscreen() : (w.requestFullscreen || w.webkitRequestFullscreen).call(w);
  });
  document.addEventListener("fullscreenchange", () => {
    $("btn-fullscreen").textContent = document.fullscreenElement ? "Exit Fullscreen" : "Fullscreen";
    setTimeout(() => view.resize(), 100);
  });
  $("rotor-angle").addEventListener("input", (e) => { view.setRotorAngle(+e.target.value); $("rotor-angle-out").textContent = `${e.target.value}°`; });
  $("show-info").addEventListener("change", (e) => { state.showInfo = e.target.checked; renderChecks(); });
  $("btn-summary").addEventListener("click", () => {
    const r = state.result; if (!r || !r.ok) return;
    $("summary-text").textContent = r.summaries.stator + "\n\n" + r.summaries.rotor;
    $("summary-dialog").showModal();
  });
  $("btn-share").addEventListener("click", share);
  $("btn-export").addEventListener("click", exportFiles);
  $("btn-import").addEventListener("click", () => $("import-file").click());
  $("import-file").addEventListener("change", (e) => { importFiles([...e.target.files]); e.target.value = ""; });
  $("btn-reset").addEventListener("click", () => { setValues(Object.assign({}, state.start), "reset"); renderBasic(); toast("Back to the starting design"); });
  $("strict").addEventListener("change", () => { if (state.result) { state.stale = true; updateStale(); } });
  $("nav-back").addEventListener("click", (e) => { e.preventDefault(); history.length > 1 ? history.back() : (location.href = CONFIG.blogHome); });
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") generate();
  });

  // Python
  startWorker();
  busy(true);
  let init;
  try {
    init = await ask("init", { pyodideBase: CONFIG.pyodideBase, codeBase: CONFIG.codeBase });
  } catch (e) {
    fatal(`Python could not be loaded: ${e.message}. Check the internet connection and reload the page.`);
    return;
  }
  state.spec = init.description.parameters;
  for (const p of state.spec) state.byName[p.name] = p;
  for (const p of state.spec) state.start[p.name] = p.default;
  Object.assign(state.start, START_DESIGN);
  state.values = JSON.parse(JSON.stringify(state.start));
  const shared = decodeDesign(location.hash);
  if (shared) Object.assign(state.values, shared);
  state.ready = true;
  busy(false);
  $("btn-generate").disabled = false;
  $("btn-generate").textContent = "Generate";
  renderBasic();
  renderResults();
  try { state.inactive = new Set(await ask("inactive", { values: state.values })); } catch (e) { /* ignore */ }
  await generate();
}

window.addEventListener("message", (e) => {
  // the blog page passes its address and its #d=... share link on to the tool
  if (e.source !== window.parent || !e.data || typeof e.data !== "object") return;
  if (typeof e.data.coilgenPage === "string") state.hostPage = e.data.coilgenPage;
  if (typeof e.data.coilgenHash === "string" && e.data.coilgenHash.startsWith("#d=") && !state.ready) location.hash = e.data.coilgenHash;
});

main();
