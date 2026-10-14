/* Sketch.js - an instant drawing of the stator and rotor from the current settings, without running the generator.

   sketchBoards(values) follows the generator's own rules (BandLayout.py, StatorGenerator.py, TXLayout.py) closely
   enough to show what a change does at once: the RX band and the board edges (with the None rules and the room
   for the TX turns, the tail and the fingers), the RX curves (profile, loops, sub-coils, zero offset) with each
   edge on its layer (rising / falling), the tip vias, the bridging fingers, the TX turns on their layers (stepped
   or spiral) with the tail and the terminal via, and the rotor sectors (automatic or custom).
   It is an estimate: the junction vias, the go-around windows, the TX steps and the generator's checks are left out,
   and Field Compensated is drawn as Equal Area.  Generate draws the real boards.

   The result has the shape parseBoard (BoardPreview.js) gives, so the preview draws it like a real board:
   { stator, rotor, center } or { error }. */

const SKETCH_CU = { 1: "F.Cu", 2: "In1.Cu", 3: "In2.Cu", 4: "B.Cu" };
const SKETCH_NETS = { sin: "sketch:sin", cos: "sketch:cos", tx: "sketch:tx" };   // the Sin / Cos / TX Loops buttons
const SKETCH_STEPS = 256;                                                          // polyline points per loop

function sketchBoards(v) {
  try {
    return _sketch(v);
  } catch (e) {
    return { error: e.message };
  }
}

function _sketch(v) {
  const num = (x) => typeof x === "number" && Number.isFinite(x);
  const low = (x) => String(x).toLowerCase();
  const cx = num(v.CENTER_X_MM) ? v.CENTER_X_MM : 100, cy = num(v.CENTER_Y_MM) ? v.CENTER_Y_MM : 100;
  const N = Math.max(1, Math.round(v.LOOPS)), L = 2 * Math.PI / N, S = SKETCH_STEPS;
  const rw = v.RX_TRACE_WIDTH_MM, tw = v.TX_TRACE_WIDTH_MM, clr = v.MIN_CLEARANCE_MM, vr = v.VIA_DIAMETER_MM / 2;
  const T = Math.max(1, Math.round(v.TX_TURNS)), pitch = v.TX_PITCH_MM;
  const spiral = low(v.TX_TURN_SHAPE) === "spiral";

  // ---- layers
  const four = v.PCB_LAYERS === 4;
  const rxNums = four ? [v.RX_LAYER_A, v.RX_LAYER_B] : (v.RX_RISING_EDGE_LAYER === "B.Cu" ? [4, 1] : [1, 4]);   // [rising, falling]
  const txNums = v.TX_LAYERS === 2 ? [v.TX_LAYER_A, v.TX_LAYER_B] : [v.TX_LAYER_A];
  const tabsOn = ["all", "single"].includes(low(v.RX_TABS));
  let tabNum;
  if (low(v.RX_TAB_LAYER) === "auto") {
    const byTop = [...rxNums].sort((a, b) => a - b);
    tabNum = byTop.find((n) => !txNums.includes(n)) ?? byTop[0];
  } else tabNum = v.RX_TAB_LAYER;
  const parallelStitched = v.TX_LAYERS === 2 && !v.TX_SERIES && low(v.TX_PARALLEL_BREAK_STYLE) === "stitched";
  const goaround = tabsOn && txNums.includes(tabNum) && !parallelStitched;

  // ---- room outside the RX band (TXLayout.outer_edge_room)
  const margin = v.OUTER_EDGE_TAIL_MARGIN_MM;
  const rOutOff = v.TX_OFFSET_MM + (spiral ? T : T - 1) * pitch;               // outermost TX copper (centre line)
  let tipOff = 0;
  if (goaround) {
    const viaOff = rOutOff + tw / 2 + clr + vr + 0.02, first = vr + tw / 2 + clr + 0.02, s = Math.max(pitch, tw + clr + 0.02);
    const lastBracket = T > 1 ? viaOff + first + (T - 2) * s : viaOff;
    tipOff = lastBracket + tw / 2 + rw / 2 + clr + 0.2;
  }
  let tab = Math.max(v.RX_TAB_LENGTH_MM, v.TX_OFFSET_MM + (T - 1) * pitch + tw / 2 + rw / 2 + clr + 0.2);
  if (goaround) tab = Math.max(tab, tipOff);
  let room = Math.max(v.OUTER_EDGE_OFFSET_MM, v.TX_OFFSET_MM + T * pitch + v.TX_TAIL_EXTRA_MM + margin);
  if (tabsOn) room = Math.max(room, tab + rw / 2 + margin);

  // ---- the RX band and the board edges (BandLayout.resolve)
  const has = (n) => v[n] !== null && v[n] !== undefined;
  const inset = v.INNER_EDGE_INSET_MM;
  let ri, ro, hole, edge;
  if (has("INSIDE_RADIUS_MM") && has("OUTSIDE_RADIUS_MM")) { ri = v.INSIDE_RADIUS_MM; ro = v.OUTSIDE_RADIUS_MM; }
  else if (has("RX_R_BASE_MM") && has("RX_A_MM")) { ri = v.RX_R_BASE_MM - v.RX_A_MM; ro = v.RX_R_BASE_MM + v.RX_A_MM; }
  else {
    if (!has("INNER_EDGE_RADIUS_MM") || !has("OUTER_EDGE_RADIUS_MM"))
      throw new Error("The RX band is None, so both board edges need a radius.");
    ri = v.INNER_EDGE_RADIUS_MM + inset; ro = v.OUTER_EDGE_RADIUS_MM - room;
  }
  if (has("INSIDE_RADIUS_MM") && has("OUTSIDE_RADIUS_MM")) {
    if (!(ro > ri)) throw new Error("RX Inside Radius must be smaller than RX Outside Radius.");
  } else if (has("RX_R_BASE_MM") && has("RX_A_MM")) {
    if (!(ri > 0)) throw new Error("Swing A must be smaller than R Base.");
  } else if (!(ro > ri)) throw new Error("The board is too small for an RX band: enlarge the board or use fewer TX turns.");
  hole = has("INNER_EDGE_RADIUS_MM") ? v.INNER_EDGE_RADIUS_MM : ri - inset;
  edge = has("OUTER_EDGE_RADIUS_MM") ? v.OUTER_EDGE_RADIUS_MM : ro + room;
  if (!(hole > 0)) throw new Error("The centre hole would have no radius: lower the Inner Edge Inset.");

  const stator = { segments: {}, vias: [], circles: [], polys: [] };
  const rotor = { segments: {}, vias: [], circles: [], polys: [] };
  const P = (r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const seg = (layer, width, net, a, b) => {
    const key = layer + "|" + width + "|" + net;
    (stator.segments[key] = stator.segments[key] || { layer, width, net, pts: [] }).pts.push(a[0], a[1], b[0], b[1]);
  };
  const via = (pt, net) => stator.vias.push({ x: pt[0], y: pt[1], d: v.VIA_DIAMETER_MM, drill: v.VIA_DRILL_MM, net });

  // ---- RX curves: r(xi) from the profile, xi = the electrical angle of the node
  const a2 = 0.5 * (ro * ro - ri * ri), b2 = 0.5 * (ro * ro + ri * ri), rm = 0.5 * (ro + ri), ra = 0.5 * (ro - ri);
  const radius = low(v.RX_PROFILE) === "cosine_r" ? (s) => rm + ra * s : (s) => Math.sqrt(b2 + a2 * s);
  const zero = L * v.RX_ZERO_OFFSET_LOOP_FRACTION + v.RX_ZERO_OFFSET_DEG * Math.PI / 180;
  const nSub = Math.max(1, Math.round(v.RX_SUBCOILS));
  const splitNodes = nSub > 1 ? 2 * Math.max(1, Math.round(v.RX_SUBCOIL_SPLIT_ELEC_DEG / (2 * 360 / S))) : 0;
  let tip = Math.round(v.RX_VIA_ELECTRICAL_DEG / 360 * S);
  tip = Math.min(Math.max(tip, S / 8 + 2), 3 * S / 8 - 2);
  const lowTip = (tip + S / 2) % S;
  const layerOf = (i) => SKETCH_CU[((i - lowTip + S) % S) < S / 2 ? rxNums[0] : rxNums[1]];   // rising, else falling
  const tips = [];                                     // outer tips: [angle, curve k, sub]
  for (let sub = 0; sub < nSub; sub++) {
    const shift = L * Math.round((sub - (nSub - 1) / 2) * splitNodes) / S;
    for (let k = 0; k < 4; k++) {
      const net = k % 2 ? SKETCH_NETS.cos : SKETCH_NETS.sin;
      const node = (j) => {
        const r = radius(Math.sin(2 * Math.PI * (j % S) / S));
        return P(r, L * j / S + k * L / 4 + shift + zero);
      };
      for (let j = 0; j < N * S; j++) {
        seg(layerOf(j % S), rw, net, node(j), node(j + 1));
        if (j % S === tip) { via(node(j), net); tips.push({ a: L * j / S + k * L / 4 + shift + zero, k, sub }); }
        if (j % S === lowTip) via(node(j), net);
      }
    }
  }

  // ---- TX start angle: a number, or "auto" = the middle of the widest gap between the fingers
  let start;
  if (low(v.TX_START_ANGLE_DEG) === "auto") {
    const angs = tips.map((t) => ((t.a % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)).sort((a, b) => a - b);
    start = 0;
    if (tabsOn && angs.length) {
      let best = -1;
      angs.forEach((a, i) => {
        const b = i + 1 < angs.length ? angs[i + 1] : angs[0] + 2 * Math.PI;
        if (b - a > best) { best = b - a; start = (a + b) / 2; }
      });
    }
  } else start = v.TX_START_ANGLE_DEG * Math.PI / 180;

  // ---- bridging fingers: two legs from the outer tip out to ro + tab, on the finger layer
  if (tabsOn) {
    let chosen = tips;
    if (low(v.RX_TABS) === "single") {
      const near = (t) => Math.abs(((t.a - start) % (2 * Math.PI) + 3 * Math.PI) % (2 * Math.PI) - Math.PI);
      chosen = [0, 1].map((k) => tips.filter((t) => t.k === k).sort((a, b) => near(a) - near(b))[0]).filter(Boolean);
    }
    const cu = SKETCH_CU[tabNum], half = v.RX_TAB_WIDTH_MM / 2;
    for (const t of chosen) {
      const net = t.k % 2 ? SKETCH_NETS.cos : SKETCH_NETS.sin, rEnd = ro + tab;
      const da = half / ro;
      seg(cu, rw, net, P(ro, t.a - da), P(rEnd, t.a - half / rEnd));
      seg(cu, rw, net, P(ro, t.a + da), P(rEnd, t.a + half / rEnd));
      seg(cu, rw, net, P(rEnd, t.a - half / rEnd), P(rEnd, t.a + half / rEnd));
    }
  }

  // ---- TX turns on each TX layer, the tail and the terminal via
  const r0 = ro + v.TX_OFFSET_MM;
  for (const n of txNums) {
    const cu = SKETCH_CU[n];
    if (spiral) {
      const steps = 360 * T;
      for (let k = 0; k < steps; k++) {
        const a = start + 2 * Math.PI * k / 360, b = start + 2 * Math.PI * (k + 1) / 360;
        seg(cu, tw, SKETCH_NETS.tx, P(r0 + pitch * k / 360, a), P(r0 + pitch * (k + 1) / 360, b));
      }
    } else {
      for (let t = 0; t < T; t++) {
        const r = r0 + t * pitch;
        for (let k = 0; k < 360; k++) seg(cu, tw, SKETCH_NETS.tx, P(r, k * Math.PI / 180), P(r, (k + 1) * Math.PI / 180));
      }
    }
  }
  // tails (TXLayout.tx_layout): series on two layers = an outer tail on each; otherwise an outer tail on the turn
  // layer and an inner tail from the terminal via on the underpass layer (parallel: the layer of the stitched arcs)
  const tailIn = r0 - v.TX_INSIDE_VIA_DISTANCE_MM, tailOut = r0 + T * pitch + v.TX_TAIL_EXTRA_MM;
  const rLast = r0 + (spiral ? T : T - 1) * pitch, series = v.TX_SERIES !== false || txNums.length === 1;
  let innerTail = null;
  if (txNums.length === 1) {
    const base = txNums[0], under = Number(v.TX_SERIES_UNDERPASS_LAYER);
    innerTail = [1, 2, 3, 4].includes(under) && under !== base ? under
      : base === 4 ? 1 : base === 1 ? (four ? 2 : 4) : base === 2 ? 1 : 4;
  } else if (!series) innerTail = txNums.includes(tabNum) ? tabNum : txNums[0];
  for (const n of series && txNums.length === 2 ? txNums : [txNums[0]])
    seg(SKETCH_CU[n], tw, SKETCH_NETS.tx, P(rLast, start), P(tailOut, start));
  if (innerTail !== null) seg(SKETCH_CU[innerTail], tw, SKETCH_NETS.tx, P(tailIn, start), P(tailOut, start));
  via(P(tailIn, start), SKETCH_NETS.tx);

  // ---- board edges
  stator.circles.push({ cx, cy, r: hole, layer: "Edge.Cuts" }, { cx, cy, r: edge, layer: "Edge.Cuts" });

  // ---- rotor sectors
  let n, duty, a0, rIn, rOut, layers;
  if (low(v.ROTOR_MODE) === "custom") {
    n = Math.max(1, Math.round(v.ROTOR_CUSTOM_SECTORS)); duty = v.ROTOR_CUSTOM_DUTY;
    a0 = v.ROTOR_CUSTOM_START_ANGLE_DEG * Math.PI / 180;
    rIn = v.ROTOR_CUSTOM_INNER_RADIUS_MM; rOut = v.ROTOR_CUSTOM_OUTER_RADIUS_MM;
    layers = v.ROTOR_CUSTOM_COPPER_LAYERS;
    if (has("ROTOR_CUSTOM_BORE_RADIUS_MM")) rotor.circles.push({ cx, cy, r: v.ROTOR_CUSTOM_BORE_RADIUS_MM, layer: "Edge.Cuts" });
    if (has("ROTOR_CUSTOM_OUTLINE_RADIUS_MM")) rotor.circles.push({ cx, cy, r: v.ROTOR_CUSTOM_OUTLINE_RADIUS_MM, layer: "Edge.Cuts" });
  } else {
    n = N; duty = v.ROTOR_AUTO_DUTY; a0 = v.ROTOR_AUTO_START_ANGLE_DEG * Math.PI / 180;
    const ext = has("ROTOR_AUTO_EXTENSION_MM") ? v.ROTOR_AUTO_EXTENSION_MM : v.AIR_GAP_MM;
    const extIn = has("ROTOR_AUTO_EXTENSION_INNER_MM") ? v.ROTOR_AUTO_EXTENSION_INNER_MM : ext;
    const extOut = has("ROTOR_AUTO_EXTENSION_OUTER_MM") ? v.ROTOR_AUTO_EXTENSION_OUTER_MM : ext;
    const keep = v.ROTOR_AUTO_EDGE_CLEARANCE_MM;
    rIn = Math.max(ri - extIn, hole + keep);
    rOut = v.ROTOR_AUTO_COVER_TX
      ? Math.min(r0 + (spiral ? T : T - 1) * pitch + tw / 2 + v.ROTOR_AUTO_TX_OVERHANG_MM, edge - keep)
      : Math.min(ro + extOut, r0 - tw / 2 - v.ROTOR_AUTO_TX_CLEARANCE_MM);
    layers = v.ROTOR_AUTO_COPPER_LAYERS;
    rotor.circles.push({ cx, cy, r: hole, layer: "Edge.Cuts" }, { cx, cy, r: edge, layer: "Edge.Cuts" });
  }
  if (rOut > rIn && duty > 0) {
    const steps = Math.max(8, Math.round(v.ROTOR_ARC_STEPS_PER_SECTOR) || 48);
    for (const cu of (layers && layers.length ? layers : ["F.Cu"])) {
      for (let k = 0; k < n; k++) {
        const s0 = a0 + k * 2 * Math.PI / n, s1 = s0 + duty * 2 * Math.PI / n, pts = [];
        for (let i = 0; i <= steps; i++) pts.push(...P(rOut, s0 + (s1 - s0) * i / steps));
        for (let i = steps; i >= 0; i--) pts.push(...P(rIn, s0 + (s1 - s0) * i / steps));
        rotor.polys.push({ layer: cu, pts });
      }
    }
  }
  return { stator, rotor, center: [cx, cy], band: [ri, ro], edges: [hole, edge] };
}
