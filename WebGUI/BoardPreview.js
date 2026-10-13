/* BoardPreview.js - draws the generated KiCad boards (and the instant sketch) on a canvas.

   parseBoard(text) reads the few things the generator writes: segments, vias, Edge.Cuts circles and
   filled polygons (rotor copper).  BoardView draws them with one colour per copper layer, with zoom,
   pan, a radius / angle readout, a two-click measure tool and a rotor angle for the overlay. */

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
  const board = { segments: {}, vias: [], circles: [], polys: [], bounds: null };
  const num = "(-?[\\d.]+)";
  const segRe = new RegExp(`\\(segment \\(start ${num} ${num}\\) \\(end ${num} ${num}\\) \\(width ${num}\\) \\(layer "([^"]+)"\\)`, "g");
  let m;
  while ((m = segRe.exec(text))) {
    const [_, x1, y1, x2, y2, w, layer] = m;
    const key = layer + "|" + w;
    (board.segments[key] = board.segments[key] || { layer, width: +w, pts: [] }).pts.push(+x1, +y1, +x2, +y2);
  }
  const viaRe = new RegExp(`\\(via \\(at ${num} ${num}\\) \\(size ${num}\\) \\(drill ${num}\\)`, "g");
  while ((m = viaRe.exec(text))) board.vias.push({ x: +m[1], y: +m[2], d: +m[3], drill: +m[4] });
  const circRe = new RegExp(`\\(gr_circle \\(center ${num} ${num}\\) \\(end ${num} ${num}\\)([^\\n]*)`, "g");
  while ((m = circRe.exec(text))) {
    const cx = +m[1], cy = +m[2], rest = m[5];
    const layer = (/\(layer "([^"]+)"\)/.exec(rest) || [])[1];
    const width = +((/\(width (-?[\d.]+)\)/.exec(rest) || [])[1] || 0.05);
    if (layer) board.circles.push({ cx, cy, r: Math.hypot(+m[3] - cx, +m[4] - cy), layer, width });
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
  constructor(canvas, readout) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.readout = readout;
    this.mode = "sketch";            // sketch | stator | rotor | overlay
    this.stator = null; this.rotor = null; this.sketch = null;
    this.center = [100, 100];
    this.hidden = new Set();
    this.rotorAngle = 0;
    this.view = { scale: 4, ox: 0, oy: 0 };
    this.fitted = false;
    this.measure = false; this.mA = null; this.mB = null;
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
  setSketch(sketch) { this.sketch = sketch; if (this.mode === "sketch") this.draw(); }
  setMode(mode) { this.mode = mode; this.draw(); }
  setViaBoost(on) { if (this.viaBoost !== on) { this.viaBoost = on; this.draw(); } }
  toggleLayer(layer) { this.hidden.has(layer) ? this.hidden.delete(layer) : this.hidden.add(layer); this.draw(); }
  setRotorAngle(deg) { this.rotorAngle = deg; this.draw(); }

  /* radius of everything shown, for Fit */
  extent() {
    let r = 0;
    const take = (b) => b && b.circles.forEach((c) => (r = Math.max(r, c.r + Math.hypot(c.cx - this.center[0], c.cy - this.center[1]))));
    if (this.mode === "sketch") r = this.sketch ? this.sketch.outer : 50;
    else { take(this.stator); take(this.rotor); }
    return r || 50;
  }
  fit() {
    const W = this.canvas.width, H = this.canvas.height, r = this.extent() * 1.08;
    this.view.scale = Math.min(W, H) / (2 * r);
    this.view.ox = W / 2 - this.center[0] * this.view.scale;
    this.view.oy = H / 2 - this.center[1] * this.view.scale;
    this.fitted = true;
    this.draw();
  }
  resize() {
    const dpr = window.devicePixelRatio || 1, el = this.canvas;
    const w = Math.max(10, el.clientWidth * dpr), h = Math.max(10, el.clientHeight * dpr);
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
      const dx = x - this.center[0], dy = this.center[1] - y;          // KiCad y points down
      const r = Math.hypot(dx, dy);
      let a = Math.atan2(dy, dx) * 180 / Math.PI; if (a < 0) a += 360;
      let text = `Radius: ${r.toFixed(2)} mm, Angle: ${a.toFixed(1)}°`;
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
    const px = 1 / scale;                                   // one screen pixel in mm
    if (this.mode === "sketch") this._drawSketch(px);
    else {
      if (this.mode === "stator" || this.mode === "overlay") this._drawBoard(this.stator, px, 0);
      if (this.mode === "rotor") this._drawBoard(this.rotor, px, 0, true);
      if (this.mode === "overlay") this._drawRotorOverlay(px);
    }
    this._drawMeasure(px);
  }

  _layerColour(layer) {
    const info = LAYER_INFO[layer];
    return info ? cssVar(info.css) : "#999";
  }

  _drawBoard(b, px, angle, rotorAlone) {
    if (!b) return;
    const ctx = this.ctx;
    // rotor copper as filled polygons
    for (const p of b.polys) {
      if (!LAYER_INFO[p.layer]) continue;
      if (this.hidden.has(p.layer)) continue;
      ctx.fillStyle = rotorAlone ? "rgba(184, 115, 51, 0.75)" : cssVar("--rotor");
      ctx.beginPath(); this._polyPath(p.pts, angle); ctx.fill();
    }
    for (const layer of LAYER_ORDER) {
      if (this.hidden.has(layer)) continue;
      ctx.strokeStyle = this._layerColour(layer);
      for (const g of Object.values(b.segments)) {
        if (g.layer !== layer) continue;
        ctx.lineWidth = g.width;                         // true width from the file (no minimum)
        ctx.beginPath();
        const q = g.pts;
        for (let k = 0; k < q.length; k += 4) { ctx.moveTo(q[k], q[k + 1]); ctx.lineTo(q[k + 2], q[k + 3]); }
        ctx.stroke();
      }
    }
    // vias: bright gold at their true size (pad = size, hole = drill); the darker rim is drawn inside the pad.
    // "Vias" in the layer chips hides them; hovering that chip (viaBoost) shows small ones at least 6 px across.
    const viaFill = cssVar("--via"), viaRim = cssVar("--via-rim");
    for (let v of this.hidden.has("Vias") ? [] : b.vias) {
      const k = this.viaBoost ? Math.max(1, 3 * px / (v.d / 2)) : 1;          // scale up only if smaller than 6 px
      v = { ...v, d: v.d * k, drill: v.drill * k };
      const r = v.d / 2, rim = (v.d - v.drill) / 2 * 0.3;
      ctx.fillStyle = viaFill;
      ctx.beginPath(); ctx.arc(v.x, v.y, r, 0, 2 * Math.PI); ctx.fill();
      ctx.strokeStyle = viaRim; ctx.lineWidth = rim;
      ctx.beginPath(); ctx.arc(v.x, v.y, r - rim / 2, 0, 2 * Math.PI); ctx.stroke();
      ctx.fillStyle = "#f4f1ea";
      ctx.beginPath(); ctx.arc(v.x, v.y, v.drill / 2, 0, 2 * Math.PI); ctx.fill();
    }
    ctx.strokeStyle = cssVar("--edge");
    for (const c of b.circles) {
      if (c.layer !== "Edge.Cuts") continue;
      ctx.lineWidth = c.width;                           // EDGE_LINE_WIDTH_MM, as in the file
      ctx.beginPath(); ctx.arc(c.cx, c.cy, c.r, 0, 2 * Math.PI); ctx.stroke();
    }
  }

  _polyPath(pts, angleDeg) {
    const ctx = this.ctx, [cx, cy] = this.center;
    const a = -angleDeg * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a);
    for (let k = 0; k < pts.length; k += 2) {
      const dx = pts[k] - cx, dy = pts[k + 1] - cy;
      const x = cx + dx * ca - dy * sa, y = cy + dx * sa + dy * ca;
      k ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.closePath();
  }

  _drawRotorOverlay(px) {
    const b = this.rotor; if (!b) return;
    const ctx = this.ctx;
    for (const p of b.polys) {
      if (!LAYER_INFO[p.layer]) continue;
      ctx.fillStyle = cssVar("--rotor");
      ctx.beginPath(); this._polyPath(p.pts, this.rotorAngle); ctx.fill();   // filled only, like the file
    }
  }

  _drawSketch(px) {
    const s = this.sketch; if (!s) return;
    const ctx = this.ctx, [cx, cy] = this.center;
    // rotor sectors
    ctx.fillStyle = cssVar("--rotor");
    const n = s.loops, duty = 0.5;
    for (let k = 0; k < n; k++) {
      const a0 = (k / n) * 2 * Math.PI, a1 = a0 + duty * 2 * Math.PI / n;
      ctx.beginPath(); ctx.arc(cx, cy, s.rotorOuter, -a0, -a1, true); ctx.arc(cx, cy, s.rotorInner, -a1, -a0, false); ctx.closePath(); ctx.fill();
    }
    // TX turns
    ctx.strokeStyle = this._layerColour(s.txLayer); ctx.lineWidth = Math.max(0.2, px);
    for (let t = 0; t < s.txTurns; t++) { ctx.beginPath(); ctx.arc(cx, cy, s.txFirst + t * s.txPitch, 0, 2 * Math.PI); ctx.stroke(); }
    // SIN and COS boundaries (equal-area law), each sub-coil shifted by the split
    const curves = [];
    for (let sub = 0; sub < s.subcoils; sub++) {
      const shift = (sub - (s.subcoils - 1) / 2) * s.splitDeg * Math.PI / 180;
      curves.push({ phase: shift, layer: "F.Cu" }, { phase: shift + Math.PI, layer: "F.Cu" },
                  { phase: shift + Math.PI / 2, layer: "B.Cu" }, { phase: shift + 1.5 * Math.PI, layer: "B.Cu" });
    }
    const r2m = (s.ri * s.ri + s.ro * s.ro) / 2, r2a = (s.ro * s.ro - s.ri * s.ri) / 2;
    ctx.lineWidth = Math.max(0.2, px);
    for (const c of curves) {
      if (this.hidden.has(c.layer)) continue;
      ctx.strokeStyle = this._layerColour(c.layer);
      ctx.beginPath();
      for (let k = 0; k <= 720; k++) {
        const th = (k / 720) * 2 * Math.PI;
        const r = Math.sqrt(r2m + r2a * Math.sin(s.loops * th + c.phase));
        const x = cx + r * Math.cos(th), y = cy - r * Math.sin(th);
        k ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
      ctx.stroke();
    }
    // board edges
    ctx.strokeStyle = cssVar("--edge"); ctx.lineWidth = 1.5 * px;
    for (const r of [s.inner, s.outer]) { ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI); ctx.stroke(); }
  }

  _drawMeasure(px) {
    if (!this.measure || !this.mA) return;
    const ctx = this.ctx;
    ctx.fillStyle = cssVar("--accent"); ctx.strokeStyle = cssVar("--accent"); ctx.lineWidth = 1.5 * px;
    for (const p of [this.mA, this.mB].filter(Boolean)) { ctx.beginPath(); ctx.arc(p[0], p[1], 3 * px, 0, 2 * Math.PI); ctx.fill(); }
    if (this.mB) {
      ctx.beginPath(); ctx.moveTo(...this.mA); ctx.lineTo(...this.mB); ctx.stroke();
      const d = Math.hypot(this.mB[0] - this.mA[0], this.mB[1] - this.mA[1]);
      ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
      const dpr = window.devicePixelRatio || 1;
      const sx = this.mB[0] * this.view.scale + this.view.ox, sy = this.mB[1] * this.view.scale + this.view.oy;
      ctx.font = `${13 * dpr}px ${cssVar("--ui-font")}`;
      const label = `${d.toFixed(3)} mm`;
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.fillRect(sx + 8 * dpr, sy - 18 * dpr, ctx.measureText(label).width + 12 * dpr, 20 * dpr);
      ctx.fillStyle = cssVar("--accent"); ctx.fillText(label, sx + 14 * dpr, sy - 3 * dpr);
      ctx.restore();
    }
  }
}
