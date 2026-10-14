/* BoardPreview.js - draws the generated KiCad boards (and the instant sketch of Sketch.js) on a canvas.

   parseBoard(text) reads the few things the generator writes: nets, segments, vias, gr_circle (the Edge.Cuts
   circles are drawn) and filled polygons (rotor copper).  BoardView draws them with one colour per copper layer,
   with zoom, pan, an X / Y readout from the origin and a rotor angle for the overlay.  The canvas is sized by
   devicePixelRatio so it stays sharp on HiDPI screens.  Hovering a loop set or a layer chip highlights it (the rest
   is faded); layers, loop sets and vias can be hidden; the vias can be boosted and the origin marker coloured.
   The two-click measure tool keeps its finished lines with S (at most 256) and removes them with Z. */

const FADED = 0.18;
const SKETCH_ROLE = { "sketch:sin": "sin", "sketch:cos": "cos", "sketch:tx": "tx" };   // the nets of Sketch.js                                                    // alpha of everything not highlighted
const LAYER_ORDER = ["B.Cu", "In2.Cu", "In1.Cu", "F.Cu"];              // drawn bottom first
const LAYER_INFO = {
  "F.Cu": { name: "Top", css: "--top" },
  "In1.Cu": { name: "Inner-1", css: "--in1" },
  "In2.Cu": { name: "Inner-2", css: "--in2" },
  "B.Cu": { name: "Bottom", css: "--bottom" },
};

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function parseBoard(text) {
  const board = { segments: {}, vias: [], circles: [], polys: [] };
  const num = "(-?[\\d.]+)";
  // net names: (net 3 "SIN_Signal"); segments and vias carry the number, (net 3)
  const nets = {};
  let m;
  const netRe = /^\s*\(net (\d+) "([^"]*)"\)/gm;
  while ((m = netRe.exec(text))) nets[m[1]] = m[2];
  const segRe = new RegExp(`\\(segment \\(start ${num} ${num}\\) \\(end ${num} ${num}\\) \\(width ${num}\\) \\(layer "([^"]+)"\\)(?: \\(net (\\d+)\\))?`, "g");
  while ((m = segRe.exec(text))) {
    const [_, x1, y1, x2, y2, w, layer, n] = m;
    const net = nets[n] ?? "";
    const key = layer + "|" + w + "|" + net;
    (board.segments[key] = board.segments[key] || { layer, width: +w, net, pts: [] }).pts.push(+x1, +y1, +x2, +y2);
  }
  const viaRe = new RegExp(`\\(via \\(at ${num} ${num}\\) \\(size ${num}\\) \\(drill ${num}\\)[^\\n]*?(?:\\(net (\\d+)\\))?\\)\\s*$`, "gm");
  while ((m = viaRe.exec(text))) board.vias.push({ x: +m[1], y: +m[2], d: +m[3], drill: +m[4], net: nets[m[5]] ?? "" });
  const circRe = new RegExp(`\\(gr_circle \\(center ${num} ${num}\\) \\(end ${num} ${num}\\)([^\\n]*)`, "g");
  while ((m = circRe.exec(text))) {
    const cx = +m[1], cy = +m[2], rest = m[5];
    const layer = (/\(layer "([^"]+)"\)/.exec(rest) || [])[1];
    if (layer) board.circles.push({ cx, cy, r: Math.hypot(+m[3] - cx, +m[4] - cy), layer });
  }
  // filled polygons: (gr_poly (pts (xy ..) ...) ... (layer "F.Cu") ...)
  let i = 0;
  while ((i = text.indexOf("(gr_poly", i)) >= 0) {
    let depth = 0, j = i;
    for (; j < text.length; j++) {
      if (text[j] === "(") depth++;
      else if (text[j] === ")" && --depth === 0) break;
    }
    const body = text.slice(i, j + 1);
    const lm = /\(layer "([^"]+)"\)/.exec(body);
    const pts = [];
    const xyRe = new RegExp(`\\(xy ${num} ${num}\\)`, "g");
    let p;
    while ((p = xyRe.exec(body))) pts.push(+p[1], +p[2]);
    if (lm && pts.length) board.polys.push({ layer: lm[1], pts });
    i = j + 1;
  }
  return board;
}

/* ------------------------------------------------------------------------------------------------ */
class BoardView {
  static MAX_LOCKED = 256;          // measured lines the S key can keep
  constructor(canvas, readout) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.readout = readout;
    this.mode = "overlay";           // sketch | stator | rotor | overlay
    this.stator = null; this.rotor = null;
    this.sketch = null;              // { stator, rotor } from Sketch.js: follows the controls at once
    this.center = [100, 100];
    this.hidden = new Set();
    this.netRole = {};               // net name -> "sin" | "cos" | "tx" (from the parameters of the run)
    this.hiddenNets = new Set();     // roles switched off with the Sin / Cos / TX Loops buttons
    this.highlight = null;           // the role under the mouse: drawn thicker, the rest faded
    this.highlightLayer = null;      // the copper layer under the mouse (Top / Inner-1 / Inner-2 / Bottom chips), the same way
    this.showOrigin = true;          // the board centre marker (Origin button); originBoost = hovered, drawn in the accent colour
    this.rotorAngle = 0;
    this.view = { scale: 4, ox: 0, oy: 0 };
    this.measure = false; this.mA = null; this.mB = null;
    this.mLocked = [];               // measured lines kept with the S key: [[A, B], ...], at most MAX_LOCKED
    this.hasBoard = false;           // true once setBoards has run (WebGUI.js tests it to tell a failed run from no run)
    this.originBoost = false;        // the Origin button is hovered
    this.viaBoost = false;           // the Vias chip is hovered
    this._wire();
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement);
  }

  setBoards(statorText, rotorText, center) {
    this.hasBoard = true;
    this.stator = statorText ? parseBoard(statorText) : null;
    this.rotor = rotorText ? parseBoard(rotorText) : null;
    if (center) this.center = center;
    this.draw();
  }
  setMode(mode) { this.mode = mode; this.draw(); }
  setSketch(sketch) { this.sketch = sketch; if (this.mode === "sketch") this.draw(); }
  /* the stator and rotor the view draws: the sketch's in the Sketch view, else the generated ones */
  _boards() { return this.mode === "sketch" ? (this.sketch || {}) : { stator: this.stator, rotor: this.rotor }; }
  setNetRoles(roles) { this.netRole = roles; this.draw(); }
  toggleNet(role) { this.hiddenNets.has(role) ? this.hiddenNets.delete(role) : this.hiddenNets.add(role); this.draw(); }
  setHighlight(role) { if (this.highlight !== role) { this.highlight = role; this.draw(); } }
  /* the layers with traces or fills in the board(s) the view shows (the layer chips of the others are locked; the
     rotor's mask openings are polygons too, so mask layers can appear, but the chips only ask about copper);
     null before the first board.  Overlay: the stator's, since the rotor drawn over it does not follow the chips. */
  layersPresent() {
    const b = this.mode === "rotor" ? this.rotor : this._boards().stator;
    if (!b) return null;
    const s = new Set();
    for (const g of Object.values(b.segments)) s.add(g.layer);
    for (const p of b.polys) s.add(p.layer);
    return s;
  }
  setLayerHighlight(cu) { if (this.highlightLayer !== cu) { this.highlightLayer = cu; this.draw(); } }
  toggleOrigin() { this.showOrigin = !this.showOrigin; this.draw(); }
  setOriginBoost(on) { if (this.originBoost !== on) { this.originBoost = on; this.draw(); } }
  setViaBoost(on) { if (this.viaBoost !== on) { this.viaBoost = on; this.draw(); } }
  toggleLayer(layer) { this.hidden.has(layer) ? this.hidden.delete(layer) : this.hidden.add(layer); this.draw(); }
  setRotorAngle(deg) { this.rotorAngle = deg; this.draw(); }

  /* radius of everything shown, for Fit */
  extent() {
    let r = 0;
    const take = (b) => b && b.circles.forEach((c) => (r = Math.max(r, c.r + Math.hypot(c.cx - this.center[0], c.cy - this.center[1]))));
    const { stator, rotor } = this._boards();
    take(stator); take(rotor);
    return r || 50;
  }
  fit() {
    const W = this.canvas.width, H = this.canvas.height, r = this.extent() * 1.08;
    this.view.scale = Math.min(W, H) / (2 * r);
    this.view.ox = W / 2 - this.center[0] * this.view.scale;
    this.view.oy = H / 2 - this.center[1] * this.view.scale;
    this.draw();
  }
  resize() {
    const dpr = window.devicePixelRatio || 1, el = this.canvas;
    const w = Math.max(10, Math.floor(el.clientWidth * dpr)), h = Math.max(10, Math.floor(el.clientHeight * dpr));   // whole pixels, as the canvas stores them
    if (el.width !== w || el.height !== h) { el.width = w; el.height = h; }
    this.fit();
  }

  toBoard(px, py) {
    const dpr = window.devicePixelRatio || 1;
    return [(px * dpr - this.view.ox) / this.view.scale, (py * dpr - this.view.oy) / this.view.scale];
  }

  _wire() {
    const c = this.canvas;
    let drag = null;
    c.addEventListener("wheel", (e) => {
      e.preventDefault();
      const dpr = window.devicePixelRatio || 1, x = e.offsetX * dpr, y = e.offsetY * dpr;
      const k = Math.exp(-e.deltaY * 0.0015);
      this.view.ox = x - (x - this.view.ox) * k;
      this.view.oy = y - (y - this.view.oy) * k;
      this.view.scale *= k;
      this.draw();
    }, { passive: false });
    c.addEventListener("mousedown", (e) => {
      if (this.measure) {
        const p = this.toBoard(e.offsetX, e.offsetY);
        if (!this.mA || this.mB) { this.mA = p; this.mB = null; } else this.mB = p;
        this.draw();
        return;
      }
      drag = { x: e.clientX, y: e.clientY, ox: this.view.ox, oy: this.view.oy };
      c.classList.add("dragging");
    });
    window.addEventListener("mousemove", (e) => {
      if (drag) {
        const dpr = window.devicePixelRatio || 1;
        this.view.ox = drag.ox + (e.clientX - drag.x) * dpr;
        this.view.oy = drag.oy + (e.clientY - drag.y) * dpr;
        this.draw();
      }
    });
    window.addEventListener("mouseup", () => { drag = null; c.classList.remove("dragging"); });
    c.addEventListener("mousemove", (e) => {
      const [x, y] = this.toBoard(e.offsetX, e.offsetY);
      // X right and Y up, from the origin (the board centre); KiCad's y points down
      const dx = x - this.center[0], dy = this.center[1] - y;
      const f = (v) => (Math.abs(v) < 0.005 ? 0 : v).toFixed(2);       // no "-0.00"
      let text = `X: ${f(dx)} mm, Y: ${f(dy)} mm`;
      if (this.measure && this.mA && !this.mB) text += `, Distance: ${Math.hypot(x - this.mA[0], y - this.mA[1]).toFixed(3)} mm`;
      this.readout.textContent = text;
    });
    c.addEventListener("mouseleave", () => (this.readout.textContent = ""));
    c.addEventListener("dblclick", () => this.fit());
  }

  /* ---- drawing ------------------------------------------------------------------------------- */
  draw() {
    const ctx = this.ctx, { scale, ox, oy } = this.view;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.setTransform(scale, 0, 0, scale, ox, oy);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    // one canvas (device) pixel in mm; these marks are not multiplied by devicePixelRatio, unlike the measure label
    const px = 1 / scale;
    if (this.mode === "stator" || this.mode === "overlay") this._drawBoard(this.stator, px);
    if (this.mode === "rotor") this._drawBoard(this.rotor, px, true);
    if (this.mode === "overlay") this._drawRotorOverlay(this.rotor);
    if (this.mode === "sketch" && this.sketch) { this._drawBoard(this.sketch.stator, px); this._drawRotorOverlay(this.sketch.rotor); }
    if (this.showOrigin) this._drawOrigin(px);
    this._drawMeasure(px);
  }

  _layerColour(layer) {
    const info = LAYER_INFO[layer];
    return info ? cssVar(info.css) : "#999";
  }

  _drawBoard(b, px, rotorAlone) {
    if (!b) return;
    const ctx = this.ctx;
    const hlCu = this.highlightLayer && !this.hidden.has(this.highlightLayer) ? this.highlightLayer : null;
    // rotor copper as filled polygons
    for (const p of b.polys) {
      if (!LAYER_INFO[p.layer]) continue;
      if (this.hidden.has(p.layer)) continue;
      ctx.globalAlpha = hlCu && p.layer !== hlCu ? FADED : 1;
      ctx.fillStyle = rotorAlone ? "rgba(184, 115, 51, 0.75)" : cssVar("--rotor");
      ctx.beginPath(); this._polyPath(p.pts, 0); ctx.fill();
    }
    ctx.globalAlpha = 1;
    // traces: true width from the file (no minimum).  A loop set or a layer under the mouse (highlight,
    // highlightLayer) is drawn last, thicker, over the others faded; a set switched off (hiddenNets) is not
    // drawn, nor are its vias.
    const role = (net) => this.netRole[net] ?? SKETCH_ROLE[net];
    const off = (net) => this.hiddenNets.has(role(net));
    const hlRole = this.highlight && !this.hiddenNets.has(this.highlight) ? this.highlight : null;
    const hl = hlRole || hlCu;
    const lit = (g) => hlRole ? role(g.net) === hlRole : g.layer === hlCu;
    const segs = Object.values(b.segments);
    for (const pass of hl ? ["rest", "hl"] : ["all"]) {
      ctx.globalAlpha = pass === "rest" ? FADED : 1;
      for (const layer of LAYER_ORDER) {
        if (this.hidden.has(layer)) continue;
        ctx.strokeStyle = this._layerColour(layer);
        for (const g of segs) {
          if (g.layer !== layer || off(g.net)) continue;
          if (pass !== "all" && lit(g) !== (pass === "hl")) continue;
          ctx.lineWidth = pass === "hl" ? Math.max(2.5 * g.width, g.width + 2.5 * px) : g.width;
          ctx.beginPath();
          const q = g.pts;
          for (let k = 0; k < q.length; k += 4) { ctx.moveTo(q[k], q[k + 1]); ctx.lineTo(q[k + 2], q[k + 3]); }
          ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;
    // vias: bright gold at their true size (pad = size, hole = drill); the darker rim is drawn inside the pad.
    // "Vias" in the layer chips hides them; hovering that chip (viaBoost) shows small ones at least 6 px across.
    const viaFill = cssVar("--via"), viaRim = cssVar("--via-rim");
    for (const v of this.hidden.has("Vias") ? [] : b.vias) {
      if (off(v.net)) continue;
      ctx.globalAlpha = hlRole ? (role(v.net) === hlRole ? 1 : FADED) : hlCu ? FADED : 1;
      const k = this.viaBoost ? Math.max(1, 3 * px / (v.d / 2)) : 1;          // scale up only if smaller than 6 px
      const d = v.d * k, drill = v.drill * k;
      const r = d / 2, rim = (d - drill) / 2 * 0.3;
      ctx.fillStyle = viaFill;
      ctx.beginPath(); ctx.arc(v.x, v.y, r, 0, 2 * Math.PI); ctx.fill();
      ctx.strokeStyle = viaRim; ctx.lineWidth = rim;
      ctx.beginPath(); ctx.arc(v.x, v.y, r - rim / 2, 0, 2 * Math.PI); ctx.stroke();
      ctx.fillStyle = "#f4f1ea";
      ctx.beginPath(); ctx.arc(v.x, v.y, drill / 2, 0, 2 * Math.PI); ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.strokeStyle = cssVar("--edge");
    for (const c of b.circles) {
      if (c.layer !== "Edge.Cuts") continue;
      ctx.lineWidth = 1.5 * px;                          // the one exception to true scale: always a visible 1.5 px
      ctx.beginPath(); ctx.arc(c.cx, c.cy, c.r, 0, 2 * Math.PI); ctx.stroke();
    }
  }

  _polyPath(pts, angleDeg) {
    const ctx = this.ctx, [cx, cy] = this.center;
    // KiCad y points down: -angle turns the rotor counter-clockwise on screen (like the Y-up readout)
    const a = -angleDeg * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a);
    for (let k = 0; k < pts.length; k += 2) {
      const dx = pts[k] - cx, dy = pts[k + 1] - cy;
      const x = cx + dx * ca - dy * sa, y = cy + dx * sa + dy * ca;
      k ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.closePath();
  }

  _drawRotorOverlay(b) {
    if (!b) return;
    const ctx = this.ctx;
    for (const p of b.polys) {
      if (!LAYER_INFO[p.layer]) continue;
      ctx.fillStyle = cssVar("--rotor");
      ctx.beginPath(); this._polyPath(p.pts, this.rotorAngle); ctx.fill();   // filled only, like the file
    }
  }

  /* the origin, Onshape style: a black dot inside a thin black ring, with a small gap between them.  Like the board
     edge it keeps one size on screen at any zoom; hovering the Origin button colours it (no size change). */
  _drawOrigin(px) {
    const ctx = this.ctx, [cx, cy] = this.center;
    ctx.fillStyle = ctx.strokeStyle = this.originBoost ? cssVar("--accent") : "#000";
    ctx.beginPath(); ctx.arc(cx, cy, 1.7 * px, 0, 2 * Math.PI); ctx.fill();         // dot: 3.4 px across
    ctx.lineWidth = 0.9 * px;
    ctx.beginPath(); ctx.arc(cx, cy, 3.9 * px, 0, 2 * Math.PI); ctx.stroke();        // ring: about 9 px across
  }

  /* S key: keep the finished line on screen and start a new one.  Returns the number kept, or 0 if there was no
     finished line or the limit is reached. */
  lockMeasure() {
    if (!this.measure || !this.mA || !this.mB || this.mLocked.length >= BoardView.MAX_LOCKED) return 0;
    this.mLocked.push([this.mA, this.mB]);
    this.mA = this.mB = null;
    this.draw();
    return this.mLocked.length;
  }
  /* Z key: remove the line being drawn (finished or only started); with none, remove the last kept line */
  undoMeasure() {
    if (!this.measure) return;
    if (this.mA) this.mA = this.mB = null; else this.mLocked.pop();
    this.draw();
  }
  clearMeasure() { this.mA = this.mB = null; this.mLocked = []; }

  _drawMeasure(px) {
    if (!this.measure) return;
    this.mLocked.forEach(([a, b], i) => this._drawLine(px, a, b, i + 1));
    if (this.mA) this._drawLine(px, this.mA, this.mB, this.mLocked.length + 1);   // the line being drawn is the next one
  }
  _drawLine(px, a, b, n) {                                // line n: end dots, the line, "Ln: length"
    const ctx = this.ctx;
    ctx.fillStyle = cssVar("--accent"); ctx.strokeStyle = cssVar("--accent"); ctx.lineWidth = 1.5 * px;
    for (const p of [a, b].filter(Boolean)) { ctx.beginPath(); ctx.arc(p[0], p[1], 3 * px, 0, 2 * Math.PI); ctx.fill(); }
    if (b) {
      ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.stroke();
      const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
      ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
      const dpr = window.devicePixelRatio || 1;
      const sx = b[0] * this.view.scale + this.view.ox, sy = b[1] * this.view.scale + this.view.oy;
      ctx.font = `${13 * dpr}px ${cssVar("--ui-font")}`;
      const label = `L${n}: ${d.toFixed(3)} mm`;
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.fillRect(sx + 8 * dpr, sy - 18 * dpr, ctx.measureText(label).width + 12 * dpr, 20 * dpr);
      ctx.fillStyle = cssVar("--accent"); ctx.fillText(label, sx + 14 * dpr, sy - 3 * dpr);
      ctx.restore();
    }
  }
}
