#!/usr/bin/env python3
"""
StatorGenerator.py
==================
Generates the STATOR of an inductive angle sensor (Renesas IPS2550 / IPS2200,
Microchip LX34070 ... class): four sinusoidal receiver "phases" that form the
SIN and COS coils (1 ... 16 electrical periods per turn) plus a TX coil.
Every setting is read from Parameters.py.   Output: one KiCad 7+ .kicad_pcb.

How the receiver coils are built
--------------------------------
Phase k (k = 0..3) is one closed polyline going once around the axis:

        r(phi)^2 = mean(r^2) + amp * sin( LOOPS * phi - k*90deg ),

i.e. LOOPS sine periods per turn, phase k rotated by a quarter period.
Phases 0 and 2 are in antiphase and together make one coil (net A);
phases 1 and 3 make the other coil, 90 deg later (net B).
Per coil, the two strands cross each other 2*LOOPS times; the crossings of
different phases all fall exactly on polyline nodes.

  * Net weight: strand "+" is traversed forward, strand "-" backward, so the
    coil is the chain of 2*LOOPS lobes of alternating orientation.  The net
    area is zero (no pick-up of the uniform TX field) and the flux weight is a
    pure sine of the target angle (equal-area radius law).
  * Layers: every crossing needs the two traces on different layers.  Each
    phase carries its RISING edges on one layer and its FALLING edges on the
    other, with the layer swap (via) at the outer and inner tip of every lobe.
    That is the layout with the fewest vias that also satisfies  "the two
    strands of a coil are always on opposite layers"  (equal air-gap exposure
    of SIN and COS).  It needs 8 vias per period.
  * Series junction: one crossing per coil is turned into a connection (both
    traces swap layers there without a via) so the two strands become ONE
    closed series loop.  Break that loop wherever you want your terminals.

  * Sub-coils (RX_SUBCOILS > 1): every coil is built from several antiphase
    pairs ("sub-coils") spread RX_SUBCOIL_SPLIT_ELEC_DEG apart and wired in
    series by extra junctions, like the distributed winding of the Renesas
    IPS2200 reference design: more signal (2*cos(split/2) for two) and the low
    odd harmonics attenuated.  Each coil is still ONE closed series loop.

  * Bridging fingers: at the outer tip of every lobe of every phase the trace
    leaves the RX band radially on an RX layer, runs across (over) the TX ring
    and returns, so the RX coils can be broken out outside the TX turns without
    touching the TX copper (the finger layer carries no TX turn).  No terminals
    are made.  RX_TAB_LAYER chooses the finger layer.

  * TX layers (TX_SERIES, TXLayout.py): a series TX on one layer (Bottom = the original
    layout) or on two layers (two mirrored spirals joined at the inner end), or a
    parallel TX (the same turns on two layers).  Where a finger runs on a layer that
    carries TX turns, the TX makes way.  "staggered" (go-around, as in Hoxha et al.,
    Sensors 2022, Fig. 2): every turn runs out, parallel to the finger, to a via just
    outside the TX ring - a staircase, the outer turns farther from the finger - and a
    bracket on another layer carries it around the finger; the finger runs out past the
    outermost bracket.  "stitched" (parallel TX only): the turns on the finger's layer
    stop at a via on each side and the turns of the other layer carry the current.  The
    TX copper is checked against itself (all turns are one net, so KiCad's DRC would not
    see a via touching another turn).

No silkscreen, no terminals, no checks beyond parameter sanity are generated.
"""

import math
import os
import sys

import numpy as np

# The project folders sit next to each other: Parameters and Generator (and Output).
# Put both on the import path, so every program runs from any folder.  (All files in one folder works too.)
_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ("Generator", "Parameters"):
    _p = os.path.join(_PROJECT, _sub)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Parameters as P_DEFAULT
import BandLayout
import TXLayout

RISING, FALLING = 0, 1          # edge classes (radius grows / shrinks with angle)


# =============================================================================
#  small numeric helpers
# =============================================================================
def _ellipk_ellipe(m):
    """Complete elliptic integrals K(m), E(m) (parameter m = k^2) by AGM."""
    if m <= 0.0:
        return math.pi / 2.0, math.pi / 2.0
    a, b, c = 1.0, math.sqrt(1.0 - m), math.sqrt(m)
    total, pw = 0.5 * c * c, 0.5
    while abs(c) > 1e-16:
        a, b, c = 0.5 * (a + b), math.sqrt(a * b), 0.5 * (a - b)
        pw *= 2.0
        total += pw * c * c
    k = math.pi / (2.0 * a)
    return k, k * (1.0 - total)


def loop_bz(radius, r, z):
    """Axial field (arbitrary units, per ampere) of a circular current loop."""
    m = 4.0 * radius * r / ((radius + r) ** 2 + z * z)
    k, e = _ellipk_ellipe(min(m, 1.0 - 1e-12))
    den = (radius - r) ** 2 + z * z
    return (k + (radius * radius - r * r - z * z) / den * e) / math.sqrt((radius + r) ** 2 + z * z)


def point_segments_distance(p, a, b):
    """Distance from point p to each segment a[i]-b[i]  (arrays Nx2)."""
    ab = b - a
    ap = p - a
    den = np.einsum("ij,ij->i", ab, ab)
    t = np.where(den > 0, np.einsum("ij,ij->i", ap, ab) / np.where(den > 0, den, 1.0), 0.0)
    t = np.clip(t, 0.0, 1.0)
    proj = a + ab * t[:, None]
    return np.hypot(*(p - proj).T)


def points_segments_min_distance(pts, a, b, chunk=2048):
    """For every point of pts (n, 2): the distance to the nearest of the segments a[i] -> b[i] (m, 2)."""
    pts = np.asarray(pts, dtype=float).reshape(-1, 2)
    if len(a) == 0 or len(pts) == 0:
        return np.full(len(pts), np.inf)
    d = b - a
    dd = np.maximum(np.einsum("ij,ij->i", d, d), 1e-30)
    out = np.empty(len(pts))
    for s0 in range(0, len(pts), max(1, chunk * 64 // max(len(a), 1))):
        p = pts[s0:s0 + max(1, chunk * 64 // max(len(a), 1))]
        w = p[:, None, :] - a[None, :, :]
        t = np.clip(np.einsum("ijk,jk->ij", w, d) / dd[None, :], 0.0, 1.0)
        c = a[None, :, :] + t[:, :, None] * d[None, :, :]
        out[s0:s0 + len(p)] = np.sqrt(((p[:, None, :] - c) ** 2).sum(axis=2)).min(axis=1)
    return out


def near_points_segments_min_distance(pts, a, b, cutoff, chunk=200000):
    """Smallest distance from the points to the segments a[i]-b[i], exact when it is below `cutoff` (otherwise
    some value >= cutoff).  Only nearby pairs are measured (a grid of cells), so it stays fast for long, finely
    divided polylines."""
    pts, a, b = (np.asarray(x, dtype=float).reshape(-1, 2) for x in (pts, a, b))
    if not len(pts) or not len(a):
        return float("inf")
    h = float(cutoff) + float(np.hypot(*(b - a).T).max()) / 2.0 + 1e-9
    mid = 0.5 * (a + b)
    lo = np.minimum(mid.min(axis=0), pts.min(axis=0))
    cs = np.floor((mid - lo) / h).astype(np.int64)
    cp = np.floor((pts - lo) / h).astype(np.int64)
    K = int(max(cs.max(), cp.max())) + 3
    key = (cs[:, 0] + 1) * K + (cs[:, 1] + 1)
    order = np.argsort(key, kind="stable")
    ks = key[order]
    best = float("inf")
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            k = (cp[:, 0] + 1 + dx) * K + (cp[:, 1] + 1 + dy)
            l0 = np.searchsorted(ks, k, "left")
            cnt = np.searchsorted(ks, k, "right") - l0
            idx = np.nonzero(cnt)[0]
            if not len(idx):
                continue
            # pairs, in slices of about `chunk`
            csum = np.cumsum(cnt[idx])
            start = 0
            while start < len(idx):
                stop = int(np.searchsorted(csum, (csum[start - 1] if start else 0) + chunk, "right"))
                stop = max(stop, start + 1)
                sel = idx[start:stop]
                c = cnt[sel]
                tot = int(c.sum())
                pi = np.repeat(sel, c)
                off = np.arange(tot) - np.repeat(np.cumsum(c) - c, c)
                si = order[np.repeat(l0[sel], c) + off]
                A, B, Pp = a[si], b[si], pts[pi]
                ab = B - A
                den = np.einsum("ij,ij->i", ab, ab)
                t = np.where(den > 0, np.einsum("ij,ij->i", Pp - A, ab) / np.where(den > 0, den, 1.0), 0.0)
                t = np.clip(t, 0.0, 1.0)
                d = np.hypot(*(Pp - (A + ab * t[:, None])).T)
                best = min(best, float(d.min()))
                start = stop
    return best


def segment_distance(p1, p2, q1, q2):
    """Shortest distance between the segments p1-p2 and q1-q2: 0 when they cross or touch."""
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if side(q1, q2, p1) * side(q1, q2, p2) < 0 and side(p1, p2, q1) * side(p1, p2, q2) < 0:
        return 0.0                                         # they cross
    p1, p2, q1, q2 = (np.asarray(v, dtype=float) for v in (p1, p2, q1, q2))
    return float(min(point_segments_distance(p1, q1[None], q2[None])[0],
                     point_segments_distance(p2, q1[None], q2[None])[0],
                     point_segments_distance(q1, p1[None], p2[None])[0],
                     point_segments_distance(q2, p1[None], p2[None])[0]))


# =============================================================================
#  KiCad file writer (KiCad 7 file format, readable by KiCad 7, 8, 9, 10)
# =============================================================================
class KiCadBoard:
    _COPPER2 = """\
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)"""
    _COPPER4 = """\
    (0 "F.Cu" signal)
    (1 "In1.Cu" signal)
    (2 "In2.Cu" signal)
    (31 "B.Cu" signal)"""
    _LAYERS = """\
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user "B.Mask")
    (39 "F.Mask" user "F.Mask")
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)"""

    def __init__(self, title="Inductive sensor", comment="", page=(200, 200), thickness=1.6,
                 copper_layers=2, comments=None):
        """comments: up to 9 lines for the comment fields of the title block (KiCad: Comment1 ... Comment9;
        its default drawing sheet shows Comment1 ... Comment4, Comment1 at the bottom); without it, `comment`
        alone fills Comment1."""
        self.copper_layers = int(copper_layers)
        self.title, self.comment, self.page, self.thickness = title, comment, page, thickness
        self.comments = list(comments) if comments else ([comment] if comment else [])
        self.nets = {"": 0}
        self.body = []

    def net(self, name):
        if name not in self.nets:
            self.nets[name] = len(self.nets)
        return self.nets[name]

    @staticmethod
    def _q(s):
        """Text for the file: no double quotes, backslashes or line breaks."""
        return str(s).replace("\\", "/").replace('"', "'").replace("\n", " ")

    @staticmethod
    def _f(v):
        s = f"{v:.6f}".rstrip("0").rstrip(".")
        return "0" if s in ("", "-0") else s

    def segment(self, p, q, width, layer, net):
        f = self._f
        self.body.append(
            f'  (segment (start {f(p[0])} {f(p[1])}) (end {f(q[0])} {f(q[1])}) '
            f'(width {f(width)}) (layer "{layer}") (net {self.net(net)}))')

    def via(self, p, size, drill, net):
        f = self._f
        self.body.append(
            f'  (via (at {f(p[0])} {f(p[1])}) (size {f(size)}) (drill {f(drill)}) '
            f'(layers "F.Cu" "B.Cu") (net {self.net(net)}))')

    def circle(self, c, radius, layer, width):
        f = self._f
        self.body.append(
            f'  (gr_circle (center {f(c[0])} {f(c[1])}) (end {f(c[0])} {f(c[1] + radius)}) '
            f'(layer "{layer}") (width {f(width)}) (fill none))')

    def polygon(self, points, layer):
        f = self._f
        pts = " ".join(f"(xy {f(x)} {f(y)})" for x, y in points)
        self.body.append(f'  (gr_poly (pts {pts}) (layer "{layer}") (width 0) (fill solid))')

    def text(self):
        out = ["(kicad_pcb (version 20221018) (generator pcbnew)", "",
               f"  (general (thickness {self._f(self.thickness)}))", "",
               f'  (paper "User" {self.page[0]} {self.page[1]})',
               "  (title_block (title \"" + self._q(self.title) + "\")"
               + "".join(f' (comment {i} "{self._q(c)}")' for i, c in enumerate(self.comments[:9], 1)) + ")", "",
               "  (layers", self._COPPER4 if self.copper_layers == 4 else self._COPPER2,
               self._LAYERS, "  )", "",
               "  (setup (pad_to_mask_clearance 0))", ""]
        for name, idx in sorted(self.nets.items(), key=lambda kv: kv[1]):
            out.append(f'  (net {idx} "{name}")')
        out.append("")
        out.extend(self.body)
        out.append(")")
        return "\n".join(out) + "\n"

    def save(self, path):
        with open(path, "w", newline="\n") as fh:
            fh.write(self.text())


# KiCad's default drawing sheet (KiCad 7 ... 9): a frame 10 mm and 12 mm inside the page edge, and the title block
# 108 x 32 mm in the bottom right corner of the inner frame
SHEET_FRAME_MM = 12.0
TITLE_BLOCK_MM = (108.0, 32.0)
PAGE_GAP_MM = 3.0                   # free space between the board and the frame / the title block


def page_size(P, cx, cy, radius):
    """KiCad page size (width, height, mm) for a round board of `radius` (its outer edge) centred at (cx, cy) on the
    page: at least PAGE_SIZE_MM, grown (right and down, so the board keeps its position) until the board stays
    PAGE_GAP_MM clear of the drawing frame and of the title block.  Of the sizes that do that, the one with the
    smallest area."""
    w0, h0 = (float(v) for v in P.PAGE_SIZE_MM)
    R = float(radius) + float(P.EDGE_LINE_WIDTH_MM) / 2.0 + PAGE_GAP_MM
    fr = SHEET_FRAME_MM
    tw, th = TITLE_BLOCK_MM
    w_min = max(w0, math.ceil(cx + R + fr))
    h_min = max(h0, math.ceil(cy + R + fr))

    def clear(w, h):
        # distance from the board centre to the title block rectangle
        x0, x1, y0, y1 = w - fr - tw, w - fr, h - fr - th, h - fr
        dx = max(x0 - cx, 0.0, cx - x1)
        dy = max(y0 - cy, 0.0, cy - y1)
        return math.hypot(dx, dy) >= R

    best = None
    w = w_min
    while True:
        h = h_min
        while not clear(w, h):
            h += 1.0
        if best is None or w * h < best[0] * best[1] - 1e-9:
            best = (w, h)
        if h == h_min:                     # (wider pages cannot make it any smaller)
            break
        w += 1.0
    return best


def outer_edge_room(P):
    """Distance from the RX outside radius to the outer board edge that the automatic edge rule gives (mm); see
    TXLayout.outer_edge_room (it does not depend on the radius)."""
    return TXLayout.outer_edge_room(P)


def rx_band(P):
    """The RX band and the board edges from the parameters (BandLayout.resolve): dict(ri, ro, hole, outer_edge,
    mode, inner_from, outer_from).  Raises ValueError for settings that do not fit together."""
    def room():
        try:
            return outer_edge_room(P)
        except (TypeError, ValueError, AttributeError) as e:
            raise ValueError(f"the room for the TX turns and the TX tail outside the RX band cannot be worked out "
                             f"(a TX / RX tab / margin setting is not a number: {e})")
    return BandLayout.resolve(lambda n: getattr(P, n, None), room)


def outside_radius(P):
    """RX outside radius used for the board (rx_band)."""
    return rx_band(P)["ro"]


# =============================================================================
#  stator design
# =============================================================================
def chord_tolerance(P, which):
    """RX_ / TX_ / ROTOR_CHORD_TOLERANCE_MM (mm); the RX one falls back to the older name CHORD_TOLERANCE_MM;
    0.001 (1 micron) when the line is missing."""
    v = getattr(P, f"{which}_CHORD_TOLERANCE_MM", None)
    if v is None and which == "RX":
        v = getattr(P, "CHORD_TOLERANCE_MM", None)
    return 0.001 if v is None else float(v)


class StatorDesign:
    def __init__(self, P=P_DEFAULT):
        self.P = P
        self._validate()
        self._resolve_layers()
        self.N = int(P.LOOPS)
        self.cx, self.cy = float(P.CENTER_X_MM), float(P.CENTER_Y_MM)
        self.band = rx_band(P)
        self.ri, self.ro, self.inner_edge_radius = self.band["ri"], self.band["ro"], self.band["hole"]
        self.L = 2.0 * math.pi / self.N                       # one loop (rad)
        self.zero = self.L * P.RX_ZERO_OFFSET_LOOP_FRACTION + math.radians(P.RX_ZERO_OFFSET_DEG)

        # TX ring radii (full turns); needed by the field model and by the rotor
        self.tx_radii = [self.ro + P.TX_OFFSET_MM + n * P.TX_PITCH_MM for n in range(int(P.TX_TURNS))]
        self.tx_first_radius = self.ro + P.TX_OFFSET_MM
        self.tx_inner_edge = self.tx_first_radius - P.TX_TRACE_WIDTH_MM / 2.0
        self.tx_tail_end_radius = (self.tx_first_radius + P.TX_TURNS * P.TX_PITCH_MM
                                   + P.TX_TAIL_EXTRA_MM)

        # outermost COMPLETE TX turn; the point at tx_first_radius + TURNS*pitch is only the
        # start of the TX tail (one azimuth, kept clear of the fingers by TX_START_ANGLE_DEG)
        self.tx_outer_radius = self.tx_first_radius + (P.TX_TURNS - 1) * P.TX_PITCH_MM
        self.tx_steps = self._pick_tx_steps()
        self.tab_end_radius = None
        if self._tabs_on():
            self.tab_end_radius = max(
                self.ro + P.RX_TAB_LENGTH_MM,
                self.tx_outer_radius + P.TX_TRACE_WIDTH_MM / 2.0 + P.RX_TRACE_WIDTH_MM / 2.0
                + P.MIN_CLEARANCE_MM + 0.2)
            if self.tx_goaround:
                # go-around windows: the fingers run out past the outermost bracket (as in the paper's layout)
                self.tab_end_radius = max(self.tab_end_radius, self.ro + TXLayout.goaround_dims(P)["tip_off"])

        self._make_profile()
        S0 = self._pick_steps()
        tries = [S0]
        if P.STEPS_PER_LOOP == "auto" and int(P.RX_SUBCOILS) > 1:
            # The sub-coil split is a whole number of node pairs, and the junctions need enough nodes
            # to fit their stubs: take the smallest resolution >= the automatic one that reproduces the
            # requested split (within 0.3 deg) and lets every junction fit.
            def split_error(S):
                unit = 720.0 / S
                return abs(max(1, round(P.RX_SUBCOIL_SPLIT_ELEC_DEG / unit)) * unit - P.RX_SUBCOIL_SPLIT_ELEC_DEG)
            tries = [S for S in range(S0, 6 * S0 + 1, 8) if split_error(S) <= 0.3] or [S0]
        for attempt, S in enumerate(tries):
            self.S = S
            try:
                self._setup_subcoils()
                self._phase_nodes()
                self._assign_layers()
                break
            except RuntimeError:
                if attempt == len(tries) - 1:
                    raise
        self._collect_items()

        edge_formula = self.ro + P.OUTER_EDGE_OFFSET_MM
        if self.band["outer_edge"] is not None:
            self.outer_edge_radius = float(self.band["outer_edge"])
        else:
            self.outer_edge_radius = max(edge_formula,
                                         self.tx_tail_end_radius + P.OUTER_EDGE_TAIL_MARGIN_MM)
            if self.tab_end_radius is not None:
                self.outer_edge_radius = max(self.outer_edge_radius,
                                             self.tab_end_radius + P.RX_TRACE_WIDTH_MM / 2.0
                                             + P.OUTER_EDGE_TAIL_MARGIN_MM)

    # ------------------------------------------------------------------ checks
    def _validate(self):
        P = self.P
        # (a whole number written as 8.0 is accepted, as ParameterChecker does)
        if (isinstance(P.LOOPS, bool) or not isinstance(P.LOOPS, (int, float)) or not math.isfinite(P.LOOPS)
                or not float(P.LOOPS).is_integer() or not 1 <= P.LOOPS <= 16):
            raise ValueError("LOOPS must be a whole number from 1 to 16")
        rx_band(P)                                      # the RX band and the board edges fit together
        if P.RX_PROFILE not in ("equal_area", "cosine_r", "field_compensated"):
            raise ValueError('RX_PROFILE must be "equal_area", "cosine_r" or "field_compensated"')
        if isinstance(P.RX_SUBCOILS, bool) or P.RX_SUBCOILS not in (1, 2, 3):
            raise ValueError("RX_SUBCOILS must be 1, 2 or 3")
        if P.RX_SUBCOILS > 1:
            if not (P.RX_SUBCOIL_SPLIT_ELEC_DEG > 0
                    and (P.RX_SUBCOILS - 1) * P.RX_SUBCOIL_SPLIT_ELEC_DEG < 180.0):
                raise ValueError("RX_SUBCOIL_SPLIT_ELEC_DEG must be > 0 and (RX_SUBCOILS-1)*split < 180")
        self.tx_shape = TXLayout.tx_shape(P)            # "diagonal" | "arc" | "spiral" (raises on a bad value)
        if P.PCB_LAYERS not in (2, 4):
            raise ValueError("PCB_LAYERS must be 2 or 4")
        if P.PCB_LAYERS == 2 and P.RX_RISING_EDGE_LAYER not in ("F.Cu", "B.Cu"):
            raise ValueError('RX_RISING_EDGE_LAYER must be "F.Cu" or "B.Cu"')
        if P.PCB_LAYERS == 4:
            for nm in ("RX_LAYER_A", "RX_LAYER_B"):
                v = getattr(P, nm)
                if isinstance(v, bool) or v not in (1, 2, 3, 4):
                    raise ValueError(f"{nm} must be 1 (Top), 2 (Inner 1), 3 (Inner 2) or 4 (Bottom)")
            if P.RX_LAYER_A == P.RX_LAYER_B:
                raise ValueError("RX_LAYER_A and RX_LAYER_B must be different layers")
        if not (50.0 <= P.RX_VIA_ELECTRICAL_DEG <= 130.0):
            raise ValueError("RX_VIA_ELECTRICAL_DEG must be within 50 ... 130")
        if P.STEPS_PER_LOOP != "auto" and (int(P.STEPS_PER_LOOP) % 8 or int(P.STEPS_PER_LOOP) < 48):
            raise ValueError('STEPS_PER_LOOP must be "auto" or a multiple of 8 that is >= 48')
        if str(P.RX_TABS).lower() not in ("all", "single", "none"):
            raise ValueError('RX_TABS must be "all", "single" or "none"')
        if P.TX_TURNS < 1:
            raise ValueError("TX_TURNS must be >= 1")
        self.tx_lay = TXLayout.tx_layout(P)          # TX layers, finger layer, windows (raises on bad settings)

    _LAYER_NAMES = TXLayout.LAYER_NAMES

    def _resolve_layers(self):
        """Copper layers used by the RX coils (rising / falling edges), the bridging fingers and the TX
        (TXLayout.tx_layout: TX_SERIES and its series / parallel block)."""
        P = self.P
        if P.PCB_LAYERS == 2:
            self.rising_layer = P.RX_RISING_EDGE_LAYER
            self.falling_layer = "B.Cu" if self.rising_layer == "F.Cu" else "F.Cu"
        else:
            self.rising_layer = self._LAYER_NAMES[P.RX_LAYER_A]
            self.falling_layer = self._LAYER_NAMES[P.RX_LAYER_B]
        lay = self.tx_lay
        self.tx_mode = lay["mode"]                       # "single" | "series2" | "parallel"
        self.tx_turn_layers = lay["turn_layers"]
        self.tx_field_layers = lay["field_layers"]      # (layer, share of the current)
        self.tx_layer_p = self.tx_layer_q = None
        if self.tx_mode == "series2":
            self.tx_layer_p, self.tx_layer_q = lay["layers"]   # spiral run inwards (from the terminal) / outwards
        self.tab_layer = lay["tab_layer"]
        self.tx_windows_on = lay["windows_on"]          # a finger crosses the TX on a TX layer
        self.tx_break_style = lay["style"]              # finger windows: "staggered" (go-around) / "stitched"
        self.tx_goaround = lay["goaround"]
        self.tx_new_builder = lay["new_builder"]

    def _tabs_on(self):
        """Bridging fingers at all: RX_TABS = "all" (every outer tip) or "single" (one per coil)."""
        return str(self.P.RX_TABS).lower() in ("all", "single")

    def _tabs_single(self):
        return str(self.P.RX_TABS).lower() == "single"

    # ------------------------------------------------------------ radius law
    def _make_profile(self):
        P = self.P
        ri2, ro2 = self.ri ** 2, self.ro ** 2
        self._a, self._b = 0.5 * (ro2 - ri2), 0.5 * (ro2 + ri2)
        if P.RX_PROFILE == "equal_area":
            self.radius = lambda s: np.sqrt(self._b + self._a * np.asarray(s, dtype=float))
            return
        if P.RX_PROFILE == "cosine_r":
            rm, ra = 0.5 * (self.ro + self.ri), 0.5 * (self.ro - self.ri)
            self.radius = lambda s: rm + ra * np.asarray(s, dtype=float)
            return
        # field_compensated: choose r(s) so that  G(r) = int B_tx(r') r' dr'
        # grows linearly with s = sin(electrical angle)  (target = z above TX)
        z = P.PCB_THICKNESS_MM + P.AIR_GAP_MM
        grid = np.linspace(self.ri, self.ro, 4001)
        if getattr(self, "tx_new_builder", False):
            # the TX turns at their real layers (TX_SERIES blocks): depth of a layer below the top copper
            t = float(P.PCB_THICKNESS_MM)
            inner = 0.2 if 0.4 < t else t / 3.0
            depth = {"F.Cu": 0.0, "In1.Cu": inner, "In2.Cu": t - inner, "B.Cu": t}
            zs = [(P.AIR_GAP_MM + depth[l], w) for l, w in self.tx_field_layers]
            bz = np.array([sum(w * loop_bz(R, float(r), zz) for R in self.tx_radii for zz, w in zs) for r in grid])
        else:
            bz = np.array([sum(loop_bz(R, float(r), z) for R in self.tx_radii) for r in grid])
        g = np.concatenate([[0.0], np.cumsum(0.5 * (bz[1:] * grid[1:] + bz[:-1] * grid[:-1]) * np.diff(grid))])
        self.radius = lambda s: np.interp(g[-1] * (1.0 + np.asarray(s, dtype=float)) / 2.0, g, grid)

    def _pick_tx_steps(self):
        """Points per TX turn: TX_STEPS, or (auto) the fewest, a multiple of 8, whose chords of the outermost turn lie
        within TX_CHORD_TOLERANCE_MM of the circle."""
        P = self.P
        s = getattr(P, "TX_STEPS", "auto")
        if not (isinstance(s, str) and s.lower() == "auto"):
            return int(s)
        r, tol = float(self.tx_outer_radius), chord_tolerance(P, "TX")
        n = int(math.ceil(math.pi / math.acos(max(-1.0, 1.0 - tol / r))))
        return max(48, -(-n // 8) * 8)

    def _pick_steps(self):
        P = self.P
        if P.STEPS_PER_LOOP != "auto":
            return int(P.STEPS_PER_LOOP)

        def point(t, S):
            xi = 2.0 * math.pi * t / S
            r = self.radius(np.sin(xi))
            phi = self.L * t / S
            return np.stack([r * np.cos(phi), r * np.sin(phi)], axis=-1)

        err = None
        tol = chord_tolerance(P, "RX")
        for S in range(48, 1025, 8):
            i = np.arange(S, dtype=float)
            p0, p1, pm = point(i, S), point(i + 1, S), point(i + 0.5, S)
            err = float(np.max(np.hypot(*(pm - 0.5 * (p0 + p1)).T)))
            if err <= tol:
                return S
        # the limit of 1024 chords per loop was reached without meeting the tolerance
        print(f"WARNING: RX_CHORD_TOLERANCE_MM = {tol:g} mm needs more than 1024 chords per loop; "
              f"STEPS_PER_LOOP = auto stops at 1024 ({err:.4f} mm chord error). Raise RX_CHORD_TOLERANCE_MM, or set "
              f"STEPS_PER_LOOP to a fixed value (a multiple of 8, up to 4096)", file=sys.stderr)
        return 1024

    # ------------------------------------------------------------ sub-coils
    def _setup_subcoils(self):
        P, S = self.P, self.S
        self.n_sub = int(P.RX_SUBCOILS)
        if self.n_sub > 1:
            unit = 2.0 * 360.0 / S                       # two polyline nodes, in electrical degrees
            m = int(round(P.RX_SUBCOIL_SPLIT_ELEC_DEG / unit))
            if m < 1:
                raise ValueError(f"RX_SUBCOIL_SPLIT_ELEC_DEG is below the polyline resolution "
                                 f"({unit:g} deg); raise it or raise STEPS_PER_LOOP")
            self.split_nodes = 2 * m
        else:
            self.split_nodes = 0
        self.split_deg = self.split_nodes * 360.0 / S
        # shift of every sub-coil in polyline nodes (symmetric about the coil axis)
        self.sub_shift = [int(round((s - (self.n_sub - 1) / 2.0) * self.split_nodes)) for s in range(self.n_sub)]

    # ------------------------------------------------------------ polylines
    def _phase_nodes(self):
        N, S = self.N, self.S
        self.NS = N * S
        j = np.arange(self.NS)
        xi = 2.0 * math.pi * (j % S) / S
        r = self.radius(np.sin(xi))
        self.rnode = r
        self.curves = []                  # one entry per closed curve: sub-coil s, phase k
        self.nodes = []
        for s in range(self.n_sub):
            shift = self.L * self.sub_shift[s] / S
            for k in range(4):
                phi = self.L * (j / S) + k * self.L / 4.0 + shift + self.zero
                self.nodes.append(np.stack([self.cx + r * np.cos(phi), self.cy + r * np.sin(phi)], axis=1))
                self.curves.append(dict(sub=s, k=k, off=k * S // 4 + self.sub_shift[s],
                                        net=[self.P.RX_NET_PHASE_0_2, self.P.RX_NET_PHASE_1_3][k % 2]))
        self.nets_of_phase = [c["net"] for c in self.curves]
        self.ncurves = len(self.curves)

    def _ci(self, sub, k):
        return sub * 4 + k

    # --------------------------------------------------------- layer scheme
    def _assign_layers(self):
        P, N, S, NS = self.P, self.N, self.S, self.NS
        # segment j runs from node j to node j+1; its edge class follows from
        # where it sits between the two tip vias.
        tip = int(round(P.RX_VIA_ELECTRICAL_DEG / 360.0 * S))
        tip = min(max(tip, S // 8 + 2), 3 * S // 8 - 2)        # keep clear of crossings
        low_tip = tip + S // 2
        i = np.arange(NS) % S
        base = np.where(((i - low_tip) % S) < S // 2, RISING, FALLING)
        self.edge_class = [base.copy() for _ in range(self.ncurves)]
        self.tip_nodes = (tip, low_tip % S)
        self._tip, self._low_tip = tip, low_tip % S

        # Series junction: a crossing of a RISING strand ("plus", traversed forward)
        # with a FALLING strand ("minus", traversed backward) is turned into a
        # connection (both traces swap layers there without a via).  Two closed
        # curves joined this way become ONE closed series loop.
        self.junction = []
        self._jvias = []                  # (x, y) of every junction via placed so far
        self._windows = [[] for _ in range(self.ncurves)]   # reserved node ranges per curve
        # 1) inside every sub-coil: the antiphase pair (phase 0/2 or 1/3) at mid radius.
        #    The two coils get their junction on opposite sides of the board so the
        #    junction vias of different nets can never meet.
        for sub in range(self.n_sub):
            for kp, km, loop_pref in ((0, 2, 0), (1, 3, N // 2)):
                plus, minus = self._ci(sub, kp), self._ci(sub, km)
                loops = [loop_pref] if self.n_sub == 1 else [(loop_pref + t) % N for t in range(N)]
                done = False
                for loop in loops:
                    jp = loop * S
                    jm = ((loop - 1) * S + S // 2) % NS
                    d = self._try_junction(plus, jp, minus, jm, legacy=True)
                    if d is not None:
                        self._commit_junction(plus, jp, minus, jm, d)
                        done = True
                        break
                if not done:
                    raise RuntimeError("could not place the junction vias with the required clearance; "
                                       "increase STEPS_PER_LOOP, the sub-coil split, or relax MIN_CLEARANCE_MM")
        # 2) between neighbouring sub-coils of one coil: join "plus" of sub-coil s
        #    with "minus" of sub-coil s+1 (an antiphase partner, so the signals ADD)
        for sub in range(self.n_sub - 1):
            for kp, km in ((0, 2), (1, 3)):
                plus, minus = self._ci(sub, kp), self._ci(sub + 1, km)
                cands = self._crossings(plus, minus)
                placed = False
                for ja, jb in cands:
                    d = self._try_junction(plus, ja, minus, jb, legacy=False)
                    if d is not None:
                        self._commit_junction(plus, ja, minus, jb, d)
                        placed = True
                        break
                if not placed:
                    raise RuntimeError("could not find a clear crossing to join neighbouring sub-coils; "
                                       "increase RX_SUBCOIL_SPLIT_ELEC_DEG or STEPS_PER_LOOP")

    # -- helpers for junctions ------------------------------------------------
    def _min_dist(self, p, curve, node_idx):
        a = self.nodes[curve][node_idx[:-1]]
        b = self.nodes[curve][node_idx[1:]]
        return float(point_segments_distance(np.asarray(p), a, b).min())

    def _angpos(self, ja, curve):
        x, y = self.nodes[curve][ja % self.NS]
        return math.atan2(y - self.cy, x - self.cx)

    def _crossings(self, a, b):
        """(ja, jb) where curve a (on a rising edge) and curve b (on a falling edge) cross at a node,
        best first (farthest from the junctions already placed)."""
        NS, S = self.NS, self.S
        ia = np.arange(NS)
        jb = (ia + self.curves[a]["off"] - self.curves[b]["off"]) % NS
        same = np.abs(self.rnode[ia] - self.rnode[jb]) < 1e-9
        out = []
        for ja in np.where(same)[0]:
            jbb = int(jb[ja])
            u = (ja % S - self._low_tip) % S               # position along the rising half
            w = (jbb % S - self._tip) % S                  # position along the falling half
            if 1 <= u < S // 2 and 1 <= w < S // 2:
                out.append((int(ja), jbb))
        used = [math.atan2(y - self.cy, x - self.cx) for x, y in self._jvias]

        def score(c):
            ang = self._angpos(c[0], a)
            if not used:
                return 4.0
            return min(abs((ang - u0 + math.pi) % (2 * math.pi) - math.pi) for u0 in used)
        out.sort(key=lambda c: (-round(score(c), 3), c[0]))
        return out

    def _overlaps(self, curve, lo, hi):
        """True when the (circular) node range lo..hi of a curve touches a reserved window."""
        NS = self.NS
        for wlo, whi in self._windows[curve]:
            for sh in (-NS, 0, NS):
                if lo + sh <= whi and wlo <= hi + sh:
                    return True
        return False

    def _try_junction(self, plus, jp, minus, jm, legacy):
        """Smallest stub length d (in nodes) for which the junction fits with the required
        clearances, or None."""
        P, S, NS = self.P, self.S, self.NS
        req = P.VIA_DIAMETER_MM / 2.0 + P.RX_TRACE_WIDTH_MM / 2.0 + P.MIN_CLEARANCE_MM
        dmax = S // 8 - 2
        if not legacy:
            u = (jp % S - self._low_tip) % S
            w = (jm % S - self._tip) % S
            dmax = min(dmax, S // 2 - S // 8 - u - 2, w - S // 8 - 2)
        for cand in range(1, dmax + 1):
            if self.n_sub > 1 or not legacy:
                if self._overlaps(plus, jp - 2, jp + cand + 2) or self._overlaps(minus, jm - cand - 2, jm + 2):
                    continue
            via_minus = self.nodes[minus][(jm - cand) % NS]
            via_plus = self.nodes[plus][(jp + cand) % NS]
            near_plus = np.arange(jp - cand - 4, jp + cand + 5) % NS
            near_minus = np.arange(jm - cand - 4, jm + cand + 5) % NS
            d1 = self._min_dist(via_minus, plus, near_plus)
            d2 = self._min_dist(via_plus, minus, near_minus)
            pair_gap = float(np.hypot(*(via_minus - via_plus))) - P.VIA_DIAMETER_MM
            if not (min(d1, d2) >= req and pair_gap >= P.MIN_CLEARANCE_MM):
                continue
            if self.n_sub > 1 or not legacy:
                # clear of every other curve (through-hole vias touch all layers) and of other junction vias
                ok = True
                for c in range(self.ncurves):
                    if c in (plus, minus):
                        continue
                    for v in (via_minus, via_plus):
                        a_, b_ = self.nodes[c], np.roll(self.nodes[c], -1, axis=0)
                        if float(point_segments_distance(np.asarray(v), a_, b_).min()) < req:
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    for (vx, vy) in self._jvias:
                        for v in (via_minus, via_plus):
                            if math.hypot(v[0] - vx, v[1] - vy) - P.VIA_DIAMETER_MM < P.MIN_CLEARANCE_MM:
                                ok = False
                if not ok:
                    continue
            return cand
        return None

    def _commit_junction(self, plus, jp, minus, jm, d):
        S, NS = self.S, self.NS
        for t in range(d):
            self.edge_class[minus][(jm - d + t) % NS] = RISING
            self.edge_class[plus][(jp + t) % NS] = FALLING
        self._windows[plus].append((jp - 2, jp + d + 2))
        self._windows[minus].append((jm - d - 2, jm + 2))
        for c, node in ((minus, (jm - d) % NS), (plus, (jp + d) % NS)):
            self._jvias.append(tuple(self.nodes[c][node]))
        self.junction.append(dict(plus=plus, minus=minus, jp=jp, jm=jm, stub=d))

    def layer_name(self, edge_class):
        return self.rising_layer if edge_class == RISING else self.falling_layer

    # ------------------------------------------------------ items to write
    def _collect_items(self):
        P, N, S, NS = self.P, self.N, self.S, self.NS
        self.rx_segments, self.rx_vias = [], []        # (p, q, layer, net, phase) / (p, net, phase, node)
        self.tab_segments = []                          # subset of rx_segments that are bridging fingers
        junction_nodes = set()
        for jn in self.junction:
            junction_nodes.add((jn["plus"], jn["jp"]))
            junction_nodes.add((jn["minus"], jn["jm"]))

        # bridging fingers: legs sit on two polyline nodes q steps apart, centred on the outer tip
        tab_starts, q = set(), 0
        if self._tabs_on():
            tip0 = S // 4
            ds = float(np.hypot(*(self.nodes[0][tip0 + 1] - self.nodes[0][tip0])))
            q = max(1, int(math.ceil(P.RX_TAB_WIDTH_MM / ds - 1e-9)))
            qmax = 2 * (S // 8 - 2)
            if q > qmax:
                print(f"WARNING: RX_TAB_WIDTH_MM too wide for this loop count; using {qmax * ds:.2f} mm",
                      file=sys.stderr)
                q = qmax
            a0 = tip0 - q // 2
            tab_starts = {m * S + a0 for m in range(N)}
        self.tab_q = q
        rend = self.tab_end_radius

        def outward(p):
            v = np.asarray(p) - (self.cx, self.cy)
            return np.array([self.cx, self.cy]) + v / np.hypot(*v) * rend

        # finger start nodes for every curve: all outer tips, or (RX_TABS = "single") one tip per coil
        starts_of = {k: tab_starts for k in range(self.ncurves)}
        self.single_tabs = []
        if tab_starts and self._tabs_single():
            self._build_tx()                             # the TX tail and via decide where the fingers go
            chosen = self._pick_single_tabs(tab_starts, q, outward)
            starts_of = {k: {j for kk, j in chosen if kk == k} for k in range(self.ncurves)}

        for k in range(self.ncurves):
            cls, net = self.edge_class[k], self.nets_of_phase[k]
            em = []                                      # (p, q, layer, node_start, node_end)
            j = 0
            while j < NS:
                if j in starts_of[k]:
                    c = (j + q) % NS
                    pa, pc = self.nodes[k][j], self.nodes[k][c]
                    pao, pco = outward(pa), outward(pc)
                    em.append((pa, pao, self.tab_layer, j, None))
                    em.append((pao, pco, self.tab_layer, None, None))
                    em.append((pco, pc, self.tab_layer, None, c))
                    j += q
                else:
                    em.append((self.nodes[k][j], self.nodes[k][(j + 1) % NS],
                               self.layer_name(cls[j]), j, (j + 1) % NS))
                    j += 1
            for i, (p, qq, layer, n0, n1) in enumerate(em):
                self.rx_segments.append((p, qq, layer, net, k))
                if layer != em[i - 1][2] and n0 is not None and (k, n0) not in junction_nodes:
                    self.rx_vias.append((p, net, k, n0))
                if n0 is None or n1 is None:
                    self.tab_segments.append((p, qq, layer, net, k))
            self.phase_seg_count = len(em)
        if not self.single_tabs or self.tx_new_builder:
            self._build_tx()                             # (new builder: now with the windows under the fingers)
        self._warn_clearances()

    def _pick_single_tabs(self, tab_starts, q, outward):
        """RX_TABS = "single": one bridging finger per coil (net), at the outer tip nearest the TX tail whose
        finger keeps MIN_CLEARANCE_MM (copper to copper) from the TX tail and the TX via on the finger layer,
        and from the finger already placed for the other coil.  Returns {(curve, start node), ...}."""
        P, NS = self.P, self.NS
        tx = math.radians(self._tx_start())
        need = float(P.MIN_CLEARANCE_MM) + 0.02                 # (+20 um for the polyline chords)
        info = getattr(self, "tx_seg_info", None)
        if self.tx_windows_on and info is not None:
            # the TX makes way for the finger: only its tail and terminal via are obstacles; the finger's window
            # must also stay clear of the tail (staggered vias)
            tail = [(np.array(t[0]), np.array(t[1])) for t, (_n, kind) in zip(self.tx_segments, info)
                    if t[2] == self.tab_layer and kind == "tail"]
            vias = [np.asarray(self.tx_vias[0])]
        else:
            tail = [(np.array(t[0]), np.array(t[1])) for t in self.tx_segments if t[2] == self.tab_layer]
            vias = [np.asarray(v) for v in self.tx_vias]
        placed = []                                              # finger segments already chosen
        chosen = set()
        for net in (P.RX_NET_PHASE_0_2, P.RX_NET_PHASE_1_3):
            cands = []
            for k in range(self.ncurves):
                if self.nets_of_phase[k] != net:
                    continue
                for j in tab_starts:
                    mid = self.nodes[k][(j + q // 2) % NS]
                    ang = math.atan2(mid[1] - self.cy, mid[0] - self.cx)
                    cands.append((abs((ang - tx + math.pi) % (2.0 * math.pi) - math.pi), k, j))
            for d, k, j in sorted(cands):
                pa, pc = self.nodes[k][j], self.nodes[k][(j + q) % NS]
                segs = [(np.asarray(pa), outward(pa)), (outward(pa), outward(pc)), (outward(pc), np.asarray(pc))]
                gap = 1e9
                for a, b in segs:
                    for ta, tb in tail:
                        gap = min(gap, segment_distance(a, b, ta, tb) - (P.RX_TRACE_WIDTH_MM + P.TX_TRACE_WIDTH_MM) / 2.0)
                    for v in vias:
                        gap = min(gap, float(point_segments_distance(v, np.array([a]), np.array([b])).min())
                                  - (P.VIA_DIAMETER_MM + P.RX_TRACE_WIDTH_MM) / 2.0)
                    for oa, ob in placed:
                        gap = min(gap, segment_distance(a, b, oa, ob) - P.RX_TRACE_WIDTH_MM)
                if gap >= need and self.tx_goaround and info is not None and self.tx_mode != "parallel":
                    angs = [math.atan2(pp[1] - self.cy, pp[0] - self.cx) for pp in (pa, pc)]
                    if not self._window_clear_of_tail(angs):
                        gap = -1.0
                if gap >= need:
                    chosen.add((k, j))
                    placed.extend(segs)
                    self.single_tabs.append(dict(net=net, curve=k, angle_deg=math.degrees(
                        math.atan2(self.nodes[k][(j + q // 2) % NS][1] - self.cy,
                                   self.nodes[k][(j + q // 2) % NS][0] - self.cx)), tx_offset_deg=math.degrees(d)))
                    break
            else:
                raise ValueError(f"RX_TABS = \"single\": no outer tip of the RX coil {net} keeps MIN_CLEARANCE_MM "
                                 f"from the TX tail / via (and room for the TX window around the finger); change "
                                 f"TX_START_ANGLE_DEG or use RX_TABS = \"all\"")
        return chosen

    def _tx_start(self):
        """Azimuth (deg) of the TX tail / via.  A number, or "auto" = the widest gap between RX fingers."""
        if hasattr(self, "tx_start_angle_deg"):
            return self.tx_start_angle_deg
        v = self.P.TX_START_ANGLE_DEG
        if not (isinstance(v, str) and v.strip().lower() == "auto"):
            self.tx_start_angle_deg = float(v)
            return self.tx_start_angle_deg
        if not self.tab_segments:                   # (RX_TABS = "single": the fingers follow the tail instead)
            self.tx_start_angle_deg = 0.0
            return 0.0
        centres, halves = [], []
        for i in range(0, len(self.tab_segments) - 2, 3):
            pts = [self.tab_segments[i][0], self.tab_segments[i][1], self.tab_segments[i + 1][1], self.tab_segments[i + 2][1]]
            ang = [math.atan2(p[1] - self.cy, p[0] - self.cx) for p in pts]
            rel = [(a - ang[0] + math.pi) % (2 * math.pi) - math.pi for a in ang]
            lo, hi = min(rel), max(rel)
            centres.append(ang[0] + 0.5 * (lo + hi)); halves.append(0.5 * (hi - lo))
        centres, halves = np.array(centres), np.array(halves)
        cand = np.radians(np.arange(0.0, 360.0, 0.05))
        gap = np.abs((cand[:, None] - centres[None, :] + math.pi) % (2 * math.pi) - math.pi) - halves[None, :]
        self.tx_start_angle_deg = float(np.degrees(cand[int(np.argmax(gap.min(axis=1)))]))
        return self.tx_start_angle_deg

    def _spiral_points(self, sense, pt):
        """Smooth (Archimedean) outward spiral from (r0, angle 0) to the tail start (r0 + turns*pitch, angle 0):
        the gap between neighbouring turns is the pitch everywhere (no radial steps)."""
        P = self.P
        steps, turns = self.tx_steps, int(P.TX_TURNS)
        n = turns * steps
        return [pt(sense * 2.0 * math.pi * i / steps, self.tx_first_radius + P.TX_PITCH_MM * i / steps)
                for i in range(n + 1)]

    def _build_tx(self):
        self._build_tx_copper()
        self._place_terminal_via()

    def _step_plan(self):
        """The steps between the turns of a "stepped_diagonal" TX at TX_STEPPED_ANGLE_DEG, or None ("auto", a
        "stepped_arc" or a spiral: the
        original shapes).  Every step is one straight piece from a turn to the next one at that angle to the turn
        (90 = straight out).  Two neighbouring steps are parallel, one pitch apart along the radius, so the copper
        gap between them is pitch * cos(angle) - trace width: when that is below MIN_CLEARANCE_MM, each step starts
        a little earlier than the one inside it (stagger), which opens the gap to pitch * cos + stagger * sin.
          theta (rad), run (mm along the turn that one step takes), stagger (mm per turn), span (mm: how far the
          steps reach back from the terminal, all turns)."""
        P = self.P
        a = getattr(P, "TX_STEPPED_ANGLE_DEG", "auto")
        if (isinstance(a, str) and a.lower() == "auto") or self.tx_shape != "diagonal":
            return None
        th = math.radians(min(90.0, max(1.0, float(a))))
        p, tw, clr = float(P.TX_PITCH_MM), float(P.TX_TRACE_WIDTH_MM), float(P.MIN_CLEARANCE_MM)
        run = p * math.cos(th) / math.sin(th)
        gap = p * math.cos(th) - tw                                  # copper gap between neighbouring steps
        T = int(P.TX_TURNS)
        # (the turns are polylines: a chord lies up to `sag` inside its circle, plus a hair)
        sag = (self.tx_first_radius + T * p) * (1.0 - math.cos(math.pi / float(self.tx_steps)))
        need = clr + 0.02 + sag
        stagger = max(0.0, (need - gap) / math.sin(th))
        # the first step (turn 0 -> 1) must clear the terminal via: a pad of VIA_DIAMETER_MM at the terminal azimuth,
        # TX_INSIDE_VIA_DISTANCE_MM inside the first turn.  Local coordinates: x along the turn (mm, 0 = terminal),
        # y outwards from the first turn; the step runs from (e - run, 0) to (e, pitch).
        vr = float(P.VIA_DIAMETER_MM) / 2.0
        dv = float(getattr(P, "TX_INSIDE_VIA_DISTANCE_MM", 0.0))
        keep = vr + tw / 2.0 + clr + 0.02 + sag
        vx, vy = 0.0, -dv
        dx, dy = run, p
        ln2 = dx * dx + dy * dy
        first = 0.0
        while first > -20.0:
            ax, ay = first - run, 0.0
            f = max(0.0, min(1.0, ((vx - ax) * dx + (vy - ay) * dy) / ln2))
            if math.hypot(vx - ax - f * dx, vy - ay - f * dy) >= keep:
                break
            first -= 0.005
        return dict(theta=th, run=run, stagger=stagger, first=first, span=run - first + (T - 1) * stagger,
                    gap=p * math.cos(th) + stagger * math.sin(th) - tw)

    def _ramp_angle(self):
        """Slope (rad) of the TX's own radial steps between turns: TX_STEPPED_ANGLE_DEG, or ("auto") 2/3 of a pitch
        over 0.45 of a step of the original shape (45 deg for the spiral, which has no steps)."""
        P = self.P
        if self.tx_shape != "diagonal":
            return math.radians(45.0)
        plan = self._step_plan()
        if plan is not None:
            return plan["theta"]
        step_mm = 2.0 * math.pi * self.tx_first_radius / float(self.tx_steps)
        return math.atan2(2.0 / 3.0 * float(P.TX_PITCH_MM), 0.45 * step_mm)

    def _arc_plan(self):
        """The arcs of a "stepped_arc" TX (None for the other shapes).  All arcs are centred on the terminal via,
        which sits on the first turn at the TX start angle; arc n (radius rho0 + n x pitch) leaves turn n where it
        crosses it on the far side of the terminal and runs round the via to turn n + 1, which it meets on the near
        side; the last arc ends at its outermost point, where the outer tail starts.  Arcs one pitch apart have the
        same copper gap as the turns.  Local coordinates: x towards the terminal, angles from the centre relative
        to the TX start angle (positive = the way the turns run on a counter-clockwise layer).
          rho, xv (the via's distance from the centre), low[n] / up[n] (angle where arc n meets turn n / n + 1),
          b_low[n] / b_up[n] (the same points seen from the via), apex (radius where the outer tail starts),
          ext (smallest, largest angle of the arcs), tol (chord tolerance)."""
        if self.tx_shape != "arc":
            return None
        if getattr(self, "_arc_cache", None) is not None:
            return self._arc_cache
        P = self.P
        T, p = int(P.TX_TURNS), float(P.TX_PITCH_MM)
        r0 = float(self.tx_first_radius)
        sag = (r0 + T * p) * (1.0 - math.cos(math.pi / float(self.tx_steps)))
        rho0 = TXLayout.arc_first_radius(P, sag)
        lim = TXLayout.arc_radius_limits(P)
        if rho0 <= lim["corner"] + 1e-9:
            raise ValueError(f"TX_STEPPED_ARC_RADIUS_MM = {rho0:g} must be larger than TX_PITCH_MM = {p:g}: the arcs are "
                             f"one pitch apart and each must reach the next turn")
        if rho0 >= lim["top"] - 1e-9:
            raise ValueError(f"TX_STEPPED_ARC_RADIUS_MM = {rho0:g} must be smaller than TX_PITCH_MM + TX_TAIL_EXTRA_MM = "
                             f"{lim['top']:g}: the last arc would reach past the end of the TX tail")
        xv = r0
        rho = [rho0 + n * p for n in range(T)]

        def meet(R, rr, sign):
            x = (R * R - rr * rr + xv * xv) / (2.0 * xv)
            y = sign * math.sqrt(max(0.0, R * R - x * x))
            return math.atan2(y, x), math.atan2(y, x - xv)
        low, b_low, up, b_up = [], [], [], []
        for n in range(T):
            a, b = meet(r0 + n * p, rho[n], -1.0)
            low.append(a); b_low.append(b)
            if n < T - 1:
                a, b = meet(r0 + (n + 1) * p, rho[n], +1.0)
                up.append(a); b_up.append(b)
        ext = (min(low), max(up) if up else 0.0)
        self._arc_cache = dict(rho=rho, xv=xv, low=low, up=up, b_low=b_low, b_up=b_up, apex=xv + rho[-1], ext=ext,
                               tol=chord_tolerance(P, "TX"), auto=isinstance(getattr(P, "TX_STEPPED_ARC_RADIUS_MM",
                                                                                      "auto"), str))
        return self._arc_cache

    def _check_arc_region(self, arc_polys, via):
        """"stepped_arc": the smallest copper gap around the terminal via between pieces of TX copper on the same layer
        that are not joined there (all TX turns are one net, so KiCad's DRC cannot see it).  The pieces: every arc,
        the start and the end of every turn (a full turn apart along the copper), the outer tail.  Joined: arc n with
        the end of turn n and the start of turn n + 1, the last arc with the outer tail.  (The via itself is measured
        by _place_terminal_via.)"""
        P = self.P
        T, tw, clr = int(P.TX_TURNS), float(P.TX_TRACE_WIDTH_MM), float(P.MIN_CLEARANCE_MM)
        arc = self._arc_plan()
        V = np.asarray(via, dtype=float)
        reach = arc["rho"][-1] + 1.5
        rot = math.radians(self._tx_start())
        sig = {layer: sg for layer, sg, _n, _p in arc_polys}
        pieces = {}                                       # (layer, name) -> list of (a, b)

        def put(layer, name, a, b):
            a, b = np.asarray(a, float), np.asarray(b, float)
            if min(np.hypot(*(a - V)), np.hypot(*(b - V))) <= reach:
                pieces.setdefault((layer, name), []).append((a, b))
        for layer, _sg, n, pts in arc_polys:
            for a, b in zip(pts[:-1], pts[1:]):
                put(layer, ("arc", n), a, b)
        for (a, b, layer), (tid, kind) in zip(self.tx_segments, self.tx_seg_info):
            if layer not in sig:
                continue
            if kind == "turn" and tid >= 0:
                n = tid % T
                m = 0.5 * (np.asarray(a) + np.asarray(b)) - (self.cx, self.cy)
                ang = sig[layer] * (((math.atan2(m[1], m[0]) - rot) + math.pi) % (2.0 * math.pi) - math.pi)
                put(layer, ("start", n) if ang >= 0.0 else ("end", n), a, b)
            elif kind == "tail" and tid < 0:
                if min(np.hypot(*(np.asarray(a) - V)), np.hypot(*(np.asarray(b) - V))) > 1e-6:
                    put(layer, ("tail",), a, b)            # (the outer tail: the inner one starts at the via)
        joined = set()
        for n in range(T):
            joined.add((("arc", n), ("end", n)))
            if n < T - 1:
                joined.add((("arc", n), ("start", n + 1)))
        joined.add((("arc", T - 1), ("tail",)))
        joined |= {(b, a) for a, b in joined}
        worst, who = math.inf, None
        keys = sorted(pieces)
        for i, ka in enumerate(keys):
            for kb in keys[i + 1:]:
                if ka[0] != kb[0] or (ka[1], kb[1]) in joined:
                    continue
                A = np.array([s[0] for s in pieces[kb]]); B = np.array([s[1] for s in pieces[kb]])
                pts = []
                for a, b in pieces[ka]:
                    k = max(1, int(math.ceil(np.hypot(*(b - a)) / 0.02)))
                    pts.append(a[None, :] + (b - a)[None, :] * np.linspace(0.0, 1.0, k + 1)[:, None])
                g = float(points_segments_min_distance(np.vstack(pts), A, B).min()) - tw
                if g < worst:
                    worst, who = g, (ka, kb)
        self.tx_arc_gap = worst if math.isfinite(worst) else None
        self.tx_arc_gap_pieces = who
        if self.tx_arc_gap is not None and worst < clr - 1e-6:
            name = lambda k: " ".join(str(x) for x in k[1])
            print(f"WARNING: around the TX terminal via the arcs of the stepped_arc TX come within {worst:.3f} mm of "
                  f"other TX copper ({name(who[0])} / {name(who[1])} on {who[0][0]}, wanted {clr} mm): all TX turns are "
                  f"one net, so KiCad's DRC will not flag it, but it shorts turns; raise TX_STEPPED_ARC_RADIUS_MM or "
                  f"TX_PITCH_MM", file=sys.stderr)

    def _place_terminal_via(self, own_mm=2.0):
        """The via at the TX terminal (tx_vias[0]: inner tail -> first turn, or the via joining the two spirals of a
        series TX).  TX_INSIDE_VIA_DISTANCE_MM moves it that far towards the centre (negative: away from it), at the
        terminal's azimuth.  Every turn that starts at the terminal then leaves its circle a little before it and runs
        down to the via at the slope of the TX's own steps, with a short flat piece (one via radius) into the via; a
        radial inner tail simply runs on to the via.  0 = the original layout (the via on the trace ends).
        The via and the new copper are then measured against the other TX turns (all one net: KiCad's DRC cannot) and
        the RX band."""
        P = self.P
        vr, tw, clr = float(P.VIA_DIAMETER_MM) / 2.0, float(P.TX_TRACE_WIDTH_MM), float(P.MIN_CLEARANCE_MM)
        rw = float(P.RX_TRACE_WIDTH_MM)
        # (a "stepped_arc" TX keeps the via on the first turn: its arcs are centred on it)
        D = 0.0 if self.tx_shape == "arc" else float(getattr(P, "TX_INSIDE_VIA_DISTANCE_MM", 0.0))
        self.terminal_via_shift = D
        self.terminal_via_clearance = None
        if not self.tx_vias:
            return
        segs = list(self.tx_segments)
        info = getattr(self, "tx_seg_info", None)
        info = list(info) if info is not None else None
        v0 = np.asarray(self.tx_vias[0], dtype=float)
        c = np.array([self.cx, self.cy])
        key = lambda p, l: (round(float(p[0]), 5), round(float(p[1]), 5), l)

        def adjacency():
            adj = {}
            for i, (a, b, l) in enumerate(segs):
                if a is None:
                    continue
                adj.setdefault(key(a, l), []).append(i)
                adj.setdefault(key(b, l), []).append(i)
            return adj
        adj = adjacency()
        ends = [k for k, e in adj.items() if len(e) == 1 and math.hypot(k[0] - v0[0], k[1] - v0[1]) < vr]
        if not ends:
            return
        e0 = np.array([ends[0][0], ends[0][1]])
        u = (e0 - c) / np.linalg.norm(e0 - c)                       # outwards at the terminal
        t = np.array([-u[1], u[0]])                                 # along the circle (counter-clockwise)
        r_e = float(np.linalg.norm(e0 - c))
        added = []
        if abs(D) > 1e-9:
            V = c + u * (r_e - D)
            th = self._ramp_angle()
            flat = vr                                               # the flat piece into the via
            x_trim = flat + abs(D) / math.tan(th)                   # where the turn leaves its circle (mm along it)

            def along(p):                                           # signed distance along the circle from the terminal
                q = p - c
                return r_e * math.atan2(float(q @ t), float(q @ u))

            def on_circle(x, r):
                a_ = x / r_e
                return c + r * (u * math.cos(a_) + t * math.sin(a_))
            for k in ends:
                l = k[2]
                i = adj[k][0]
                a, b, _l = segs[i]
                a, b = np.asarray(a, float), np.asarray(b, float)
                far = b if np.hypot(*(a - e0)) < 1e-4 else a
                d = far - e0
                if abs(float(d @ u)) > abs(float(d @ t)):
                    # a radial tail: it runs on to the via
                    segs[i] = ((float(V[0]), float(V[1])), (float(far[0]), float(far[1])), l)
                    continue
                s = 1.0 if float(d @ t) > 0 else -1.0               # the way the turn leaves the terminal
                # walk along the turn, removing it up to x_trim, and split the piece that crosses x_trim
                cur, seg_i = e0, i
                while True:
                    a, b, _l = segs[seg_i]
                    a, b = np.asarray(a, float), np.asarray(b, float)
                    nxt = b if np.hypot(*(a - cur)) < 1e-4 else a
                    xa, xb = s * along(cur), s * along(nxt)
                    if xb >= x_trim:
                        f = (x_trim - xa) / (xb - xa) if xb > xa else 1.0
                        p_trim = cur + (nxt - cur) * f
                        segs[seg_i] = ((float(p_trim[0]), float(p_trim[1])), (float(nxt[0]), float(nxt[1])), l)
                        break
                    segs[seg_i] = (None, None, l)                   # removed
                    nk = key(nxt, l)
                    others = [j for j in adj.get(nk, ()) if j != seg_i and segs[j][0] is not None]
                    if len(others) != 1:
                        p_trim = nxt
                        break
                    cur, seg_i = nxt, others[0]
                F = on_circle(s * flat * (r_e - D) / r_e, r_e - D)
                for p, q in ((V, F), (F, p_trim)):
                    added.append(((float(p[0]), float(p[1])), (float(q[0]), float(q[1])), l))
            keep = [j for j, sg in enumerate(segs) if sg[0] is not None]
            self.tx_segments = [segs[j] for j in keep] + added
            if info is not None:
                self.tx_seg_info = [info[j] for j in keep] + [(-1, "terminal")] * len(added)
            self.tx_vias[0] = (float(V[0]), float(V[1]))
        # how close the via and the new copper come to the other turns and to the RX band
        segs = self.tx_segments
        A = np.array([s_[0] for s_ in segs], dtype=float)
        B = np.array([s_[1] for s_ in segs], dtype=float)
        vpos = np.asarray(self.tx_vias[0], dtype=float)
        adj = {}
        for i, (a, b, l) in enumerate(segs):
            adj.setdefault(key(a, l), []).append(i)
            adj.setdefault(key(b, l), []).append(i)
        start = [k for k in adj if math.hypot(k[0] - vpos[0], k[1] - vpos[1]) < vr + 1e-6]
        own, best, front = set(), {k: 0.0 for k in start}, [(k, 0.0) for k in start]
        # copper this close to the via along the TX is the via's own (its run down from the turn is vr + D / sin)
        own_reach = own_mm + abs(D) * 3.0
        if abs(D) > 1e-9:
            own_reach = max(own_reach, own_mm + vr + abs(D) / math.sin(self._ramp_angle()))
        while front:
            k, dd0 = front.pop()
            for i in adj.get(k, ()):
                a, b, l = segs[i]
                own.add(i)
                for p in (a, b):
                    kk = key(p, l)
                    dd = dd0 + math.hypot(b[0] - a[0], b[1] - a[1])
                    if kk != k and dd < own_reach and dd < best.get(kk, 1e9):
                        best[kk] = dd
                        front.append((kk, dd))
        foreign = np.array([i not in own for i in range(len(segs))])
        if not foreign.any():
            return
        Af, Bf = A[foreign], B[foreign]
        g_via = float(point_segments_distance(vpos, Af, Bf).min()) - tw / 2.0 - vr
        g_new = 1e9
        lay_f = np.array([s_[2] for s_ in segs])[foreign]
        for p, q, l in segs[len(segs) - len(added):]:
            same = lay_f == l                                       # (traces: the same layer only)
            if not same.any():
                continue
            p, q = np.asarray(p), np.asarray(q)
            n = max(2, int(math.ceil(np.hypot(*(q - p)) / 0.05)))
            pts = p[None, :] + (q - p)[None, :] * np.linspace(0.0, 1.0, n)[:, None]
            g_new = min(g_new, float(points_segments_min_distance(pts, Af[same], Bf[same]).min()) - tw)
        g_rx = float(np.linalg.norm(vpos - c)) - vr - (self.ro + rw / 2.0)
        self.terminal_via_clearance = min(g_via, g_new)
        if g_via < clr - 1e-6:
            print(f"WARNING: the TX terminal via comes within {g_via:.3f} mm of another TX turn (wanted {clr} mm): all "
                  f"TX turns are one net, so KiCad's DRC will not flag it, but it shorts a turn; change "
                  f"TX_INSIDE_VIA_DISTANCE_MM (now {D:g})", file=sys.stderr)
        if g_new < clr - 1e-6:
            print(f"WARNING: the TX run down to the terminal via comes within {g_new:.3f} mm of another TX turn (wanted "
                  f"{clr} mm); change TX_INSIDE_VIA_DISTANCE_MM (now {D:g})", file=sys.stderr)
        if g_rx < clr - 1e-6:
            print(f"WARNING: the TX terminal via comes within {g_rx:.3f} mm of the RX band (its outer tips) (wanted "
                  f"{clr} mm); lower TX_INSIDE_VIA_DISTANCE_MM (now {D:g}) or raise TX_OFFSET_MM", file=sys.stderr)

    def _build_tx_copper(self):
        if getattr(self, "tx_new_builder", False) or self._step_plan() is not None or self.tx_shape == "arc":
            # (TX_STEPPED_ANGLE_DEG = a number, or a "stepped_arc" TX: the original layouts too, with those steps)
            self._build_tx_placed()
            return
        if self.tx_mode == "series2":
            self._build_tx_two_layers()
            return
        if str(self.P.TX_TURN_SHAPE).lower() == "spiral":
            self._build_tx_one_layer_spiral()
            return
        P = self.P
        cx, cy = self.cx, self.cy
        steps, turns = self.tx_steps, int(P.TX_TURNS)
        r0, pitch = self.tx_first_radius, P.TX_PITCH_MM

        rot = math.radians(self._tx_start())

        def pt(angle, radius):
            angle += rot
            return (cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)

        self.tx_segments, self.tx_vias = [], []
        last = tail_end = None
        for n in range(turns + 1):
            radius = r0 + n * pitch
            for s in range(steps):
                angle = s / steps * 2.0 * math.pi
                cur = pt(angle, radius)
                if s == 0 and n == 0:
                    self.tx_vias.append(pt((s + 0.15) / steps * 2.0 * math.pi, radius))
                    tail_end = pt(angle, self.tx_tail_end_radius)
                    self.tx_segments.append((cur, tail_end, "F.Cu"))
                if s == 0 and last is not None:
                    # radial step from the previous turn to this one
                    a1 = (n * -0.08 - 0.75) / steps * 2.0 * math.pi
                    a2 = (n * -0.08 - 0.30) / steps * 2.0 * math.pi
                    t1 = pt(a1, r0 + (n - 1) * pitch)
                    t2 = pt(a2, radius - pitch / 3.0)
                    self.tx_segments.append((last, t1, "B.Cu"))
                    self.tx_segments.append((t1, t2, "B.Cu"))
                    last = t2
                if last is not None:
                    self.tx_segments.append((last, cur, "B.Cu"))
                last = cur
                if n == turns:
                    self.tx_segments.append((cur, tail_end, "B.Cu"))
                    break

    # ------------------------------------------------- TX windows and the TX layouts of the new builder
    def _tx_geometry(self, check=True):
        """Dimensions of the stitched windows of a parallel TX (mm and rad): the turns on one layer end at vias -
        staggered along the circle, because the turn pitch is smaller than a via - and the turns of the other
        layer carry the current through the window.  Next to every via the neighbouring turns bend away (jog) far
        enough to keep MIN_CLEARANCE_MM from its pad: all TX turns are one net, so KiCad's DRC would not notice a
        via touching the next turn.  Also gives the angular extent of the TX terminal (`tail`)."""
        P = self.P
        T, steps = int(P.TX_TURNS), self.tx_steps
        pitch, tw, rw = float(P.TX_PITCH_MM), float(P.TX_TRACE_WIDTH_MM), float(P.RX_TRACE_WIDTH_MM)
        vr, clr = float(P.VIA_DIAMETER_MM) / 2.0, float(P.MIN_CLEARANCE_MM)
        need = vr + tw / 2.0 + clr                             # via centre to the centre line of another turn
        delta = max(0.0, need + 0.03 - pitch)                  # how far a neighbouring turn bends away
        if check and T > 1 and pitch - tw - delta < clr - 1e-9:
            raise ValueError(f"TX_PITCH_MM = {pitch:g} is too small for the TX vias of the windows: a turn next to a "
                             f"{2 * vr:g} mm via has to bend {delta:.2f} mm away and would then come closer than "
                             f"MIN_CLEARANCE_MM to the turn beyond it. Raise TX_PITCH_MM to at least "
                             f"{(need + 0.03 + tw + clr) / 2.0:.2f} or use smaller vias")
        ramp = max(0.3, 3.0 * delta)
        stag = max(math.sqrt(max(0.0, (2.0 * vr + clr + 0.02) ** 2 - pitch ** 2)), need + ramp + 0.05) if T > 1 else 0.0
        d0 = vr + max(rw, tw) / 2.0 + clr + 0.05               # finger / tail centre line to the nearest via centre
        r0 = self.tx_first_radius
        reach = d0 + (T - 1) * stag + need + ramp              # how far a window reaches past its obstacle (arc)
        step = 2.0 * math.pi / steps
        spiral = str(P.TX_TURN_SHAPE).lower() == "spiral"
        # around the TX terminal: the radial steps between turns (stepped), the two tails and the terminal via
        plan = None if spiral else self._step_plan()
        back = plan["span"] / r0 if plan is not None else (0.0 if spiral else step)   # the steps, behind the terminal
        tail_lo = -back - (tw / 2.0 + clr) / r0
        tail_hi = 0.15 * step + (vr + clr) / r0
        if plan is not None:
            # the terminal via moved inwards (TX_INSIDE_VIA_DISTANCE_MM) and its run down from the first turn
            dv = abs(float(getattr(P, "TX_INSIDE_VIA_DISTANCE_MM", 0.0)))
            tail_hi = max(tail_hi, (vr + dv / math.tan(plan["theta"]) + tw / 2.0 + clr) / r0)
        if self.tx_mode == "series2":
            # two mirrored spirals: radial steps on both sides of the terminal
            span = 0.0 if spiral else (plan["span"] if plan is not None else (0.08 * T + 0.75) * step)
            if plan is not None:
                span /= r0
            tail_lo = min(tail_lo, -span - (tw / 2.0 + clr) / r0)
            tail_hi = max(tail_hi, span + (tw / 2.0 + clr) / r0)
        arc = None if spiral else self._arc_plan()
        if arc is not None:
            # "stepped_arc": the arcs around the terminal via (angles seen from the centre, relative to the terminal)
            lo_a, hi_a = arc["ext"]
            pad = (tw / 2.0 + clr) / r0
            if self.tx_mode == "series2":                     # mirrored arcs on the two layers
                lo_a, hi_a = -max(-lo_a, hi_a), max(-lo_a, hi_a)
            tail_lo = min(tail_lo, lo_a - pad)
            tail_hi = max(tail_hi, hi_a + pad)
        return dict(T=T, steps=steps, pitch=pitch, tw=tw, vr=vr, clr=clr, need=need, delta=delta, ramp=ramp,
                    stag=stag, d0=d0, reach=reach, r0=r0, step=step, spiral=spiral, tail=(tail_lo, tail_hi))

    def _go_geometry(self):
        """Go-around windows (TXLayout.goaround_dims) with absolute radii and the angular reach of a window."""
        P = self.P
        d = dict(TXLayout.goaround_dims(P))
        d["via_r"] = self.ro + d["via_off"]
        d["bracket_r"] = [self.ro + b for b in d["bracket_off"]]
        rmin = self.tx_first_radius - float(P.TX_TRACE_WIDTH_MM) / 2.0
        d["reach_ang"] = math.asin(min(1.0, d["reach"] / rmin))
        return d

    def _window_clear_of_tail(self, leg_angles):
        """True when a go-around window around a finger with these leg azimuths (rad, absolute) stays clear of the
        TX terminal (tail, steps, terminal via)."""
        g = self._tx_geometry(check=False)
        rot = math.radians(self._tx_start())
        rel = [((a - rot + math.pi) % (2.0 * math.pi)) - math.pi for a in leg_angles]
        lo, hi = min(rel), max(rel)
        if hi - lo > math.pi:                                     # (the two legs straddle the +-pi line)
            lo, hi = hi, lo + 2.0 * math.pi
        R = self._go_geometry()["reach_ang"] if self.tx_goaround else g["reach"] / g["r0"]
        t_lo, t_hi = g["tail"]
        for shift in (-2.0 * math.pi, 0.0, 2.0 * math.pi):
            if lo - R + shift < t_hi and hi + R + shift > t_lo:
                return False
        return True

    _NO_ROOM = ("a TX window under an RX finger would reach the TX terminal (tail / terminal via). "
                'Set TX_START_ANGLE_DEG = "auto" (or move it away from the fingers); if it is '
                '"auto" already, the fingers leave no room for the terminal between their windows: '
                'use RX_TABS = "single", put the fingers on a layer without TX turns (RX_TAB_LAYER), '
                "use a parallel TX (TX_SERIES = False), or fewer TX_TURNS")

    def _no_room(self):
        plan = self._step_plan()
        if plan is None:
            return self._NO_ROOM
        return (self._NO_ROOM + f"; or a TX_STEPPED_ANGLE_DEG closer to 45 (now {math.degrees(plan['theta']):g}: its steps "
                f"take {plan['span']:.2f} mm of the turns next to the terminal)")

    def _tx_windows(self, g, ga=None):
        """The windows as obstacle intervals (rad, relative to the TX start, merged where they would overlap):
        [(lo, hi, is_tail_window, kind), ...] sorted.  kind "go" = the turns go around the fingers (go-around),
        "stitch" = the turns of a parallel TX are stitched to the other layer (always around the terminal of a
        parallel TX).  Every window that is not a stitched tail window stays clear of the TX terminal."""
        rot = math.radians(self._tx_start())
        two_pi = 2.0 * math.pi
        parallel = self.tx_mode == "parallel"
        spans = []
        for i in range(0, len(self.tab_segments) - 2, 3):
            legs = [self.tab_segments[i][0], self.tab_segments[i + 2][1]]
            rel = [((math.atan2(p[1] - self.cy, p[0] - self.cx) - rot) % two_pi) for p in legs]
            lo, hi = min(rel), max(rel)
            if hi - lo > math.pi:
                lo, hi = hi, lo + two_pi
            spans.append([lo, hi])
        R_st = g["reach"] / g["r0"]
        R_f = ga["reach_ang"] if self.tx_goaround else R_st
        obst = [[lo, hi, False, R_f] for lo, hi in spans] if self.tx_windows_on else []
        t_lo, t_hi = g["tail"]
        if parallel:
            m = (g["need"] + g["ramp"]) / g["r0"]
            tw_ = [t_lo - m, t_hi + m, True, R_st]
            if not self.tx_windows_on:
                # the stitching vias around the tail go through every layer: a finger (on a layer without TX
                # turns) that they would reach is taken into the window, so the vias land beyond it
                R = R_st
                grown = True
                while grown:
                    grown = False
                    for lo, hi in spans:
                        for sh in (-two_pi, 0.0, two_pi):
                            a, b = lo + sh, hi + sh
                            if a < tw_[1] + R and b > tw_[0] - R and not (tw_[0] <= a and b <= tw_[1]):
                                tw_[0], tw_[1] = min(tw_[0], a), max(tw_[1], b)
                                grown = True
            obst.append(tw_)
        else:
            for lo, hi, _t, R in obst:
                if not (lo - R > t_hi and hi + R < t_lo + two_pi):
                    raise ValueError(self._no_room())
        obst.sort(key=lambda o: o[0])
        merged = []
        for o in obst:
            if merged and o[0] - merged[-1][1] < o[3] + merged[-1][3]:
                merged[-1][1] = max(merged[-1][1], o[1])
                merged[-1][2] = merged[-1][2] or o[2]
                merged[-1][3] = max(merged[-1][3], o[3])
            else:
                merged.append(list(o))
        # around the circle: the last one against the first one
        while len(merged) > 1 and (merged[0][0] + two_pi) - merged[-1][1] < merged[0][3] + merged[-1][3]:
            last = merged.pop()
            merged[0] = [min(merged[0][0], last[0] - two_pi), max(merged[0][1], last[1] - two_pi), merged[0][2] or last[2],
                         max(merged[0][3], last[3])]
            merged.sort(key=lambda o: o[0])
        total = sum(hi - lo + 2.0 * R for lo, hi, _t, R in merged)
        if total > two_pi - 1e-6:
            raise ValueError("the TX windows under the RX fingers would cover the whole TX ring (too many fingers "
                             'for the TX vias): use RX_TABS = "single", fewer TX turns, or put the fingers on a layer '
                             "without TX turns (RX_TAB_LAYER)")
        if not parallel:
            for lo, hi, _t, R in merged:
                if not (lo - R > t_hi and hi + R < t_lo + two_pi):
                    raise ValueError(self._no_room())
        finger_kind = "go" if self.tx_goaround else "stitch"
        return [(lo, hi, t, "stitch" if t else finger_kind) for lo, hi, t, _R in merged]

    def _build_tx_placed(self):
        """Every TX that is not one of the original layouts (TXLayout.tx_layout, "new_builder").  The turns follow
        the original shapes ("stepped_diagonal", "stepped_arc" or "spiral", the same steps and terminal).
          single   : the turns on one layer (TX_LAYERS = 1, TX_LAYER_A), the inner tail on the underpass layer.
          series2  : the original two-layer series TX (two mirrored spirals joined by a via at the inner end).
          parallel : the full spiral on one TX layer; on the other one the same turns run in parallel as arcs that
                     end at a via on each side of the TX terminal (and, "stitched", of every finger on that layer),
                     where they join the turn of the same radius.
        Go-around (TXLayout): around a finger on its own layer every turn of that layer runs out, parallel to
        the finger, to a via just outside the TX ring - the outer turns farther from the finger than the inner
        ones - and a bracket on the underpass layer (series: TX_SERIES_UNDERPASS_LAYER / the other TX layer;
        parallel: the full-spiral layer) carries it around the finger to the matching via on the other side."""
        lay = self.tx_lay
        mode = lay["mode"]
        parallel = mode == "parallel"
        g = self._tx_geometry(check=parallel)
        ga = self._go_geometry() if self.tx_goaround else None
        T, steps, pitch, r0 = g["T"], g["steps"], g["pitch"], g["r0"]
        spiral, step, two_pi = g["spiral"], g["step"], 2.0 * math.pi
        cx, cy = self.cx, self.cy
        rot = math.radians(self._tx_start())

        def pt(th, r):
            return (cx + math.cos(th + rot) * r, cy + math.sin(th + rot) * r)

        def r_nom(n, th):
            return r0 + pitch * (n + th / two_pi) if spiral else r0 + n * pitch

        if parallel:
            base, other = lay["base_layer"], lay["arc_layer"]
        else:
            base, other = lay["base_layer"], None
        blayer = lay["bracket_layer"]
        windows = self._tx_windows(g, ga) if (self.tx_windows_on or parallel) else []
        st_windows = [(lo, hi, t) for lo, hi, t, k in windows if k == "stitch"]
        go_windows = [(lo, hi) for lo, hi, _t, k in windows if k == "go"]
        # stitched windows: k = 0 (outermost turn) next to the obstacle, the inner turns farther away
        win_vias = []                          # per window: {n: (th_in, th_out)}
        for lo, hi, _t in st_windows:
            vv = {}
            for n in range(T):
                k = T - 1 - n
                off = g["d0"] + k * g["stag"]
                vv[n] = (lo - off / r_nom(n, lo % two_pi), hi + off / r_nom(n, hi % two_pi))
            win_vias.append(vv)
        # jogs: next to a stitching via of turn m, turn m+1 bends outwards and turn m-1 inwards
        bumps = {}                              # (turn, layer) -> [(theta, sign)]
        for vv in win_vias:
            for m, (a, b) in vv.items():
                for th in (a, b):
                    for n, layer, sgn in ((m + 1, other, +1), (m + 1, base, +1), (m - 1, base, -1)):
                        if 0 <= n < T and g["delta"] > 0:
                            bumps.setdefault((n, layer), []).append((th, sgn))
        f, ramp, delta = g["need"], g["ramp"], g["delta"]

        def bump(n, layer, th):
            out = 0.0
            for tv, sgn in bumps.get((n, layer), ()):
                d = abs(((th - tv + math.pi) % two_pi) - math.pi) * r_nom(n, th)
                if d < f:
                    out += sgn * delta
                elif d < f + ramp:
                    out += sgn * delta * (1.0 - (d - f) / ramp)
            return out

        def sample(n, ta, tb, layer, sigma=1):
            """turn n from local angle ta to tb (actual angle sigma * local)"""
            ths = {ta, tb}
            k0, k1 = math.ceil(ta / step + 1e-9), math.floor(tb / step - 1e-9)
            ths.update(k * step for k in range(k0, k1 + 1))
            for tv, _s in bumps.get((n, layer), ()):
                for dd in (f, f + ramp):
                    for sg in (-1.0, 1.0):
                        th = tv + sg * dd / r_nom(n, tv % two_pi)
                        for sh in (-two_pi, 0.0, two_pi):
                            if ta < th + sh < tb:
                                ths.add(th + sh)
            out = []
            for th in sorted(ths):
                end = th == ta or th == tb
                out.append(pt(sigma * th, r_nom(n, th) + (0.0 if end else bump(n, layer, th))))
            return out

        segs, info, vias, via_turn = [], [], [], []

        def add_poly(pts, layer, turn, kind):
            for a, b in zip(pts[:-1], pts[1:]):
                if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-9:
                    segs.append((a, b, layer)); info.append((turn, kind))

        def plen(pts):
            return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts[:-1], pts[1:]))

        def side_angle(lam, side, gn, r):
            # the run-out line of a window side: parallel to the finger leg at (local) angle lam, gn away from it
            return lam + side * math.asin(min(1.0, gn / r))

        def cut_angle(n, lam, side, gn):
            th = side_angle(lam, side, gn, r_nom(n, lam))
            return side_angle(lam, side, gn, r_nom(n, th))

        def emit_turn(n, tid, layer, sigma, ta, tb, gos, kind):
            """Turn n (id tid) on `layer` from local angle ta to tb, around the go-around windows `gos` (local
            (lo, hi) inside (ta, tb)).  Returns the length of the turn pieces."""
            cur, length = ta, 0.0
            for lo, hi in sorted(gos):
                gn, rv, Rn = ga["g"][n], ga["via_r"], ga["bracket_r"][n]
                a, b = cut_angle(n, lo, -1, gn), cut_angle(n, hi, +1, gn)
                pts = sample(n, cur, a, layer, sigma)
                add_poly(pts, layer, tid, kind)
                length += plen(pts)
                va = pt(sigma * side_angle(lo, -1, gn, rv), rv)
                vb = pt(sigma * side_angle(hi, +1, gn, rv), rv)
                add_poly([pts[-1], va], layer, tid, "stub")              # run-out to the via outside the ring
                vias.append(va); via_turn.append(tid)
                ba, bb = side_angle(lo, -1, gn, Rn), side_angle(hi, +1, gn, Rn)
                ths = [ba] + [k * step for k in range(math.ceil(ba / step + 1e-9), math.floor(bb / step - 1e-9) + 1)]
                br = [pt(sigma * th, Rn) for th in ths + [bb]]
                if Rn > rv + 1e-9:
                    br = [va] + br + [vb]
                add_poly(br, blayer, tid, "bracket")                     # around the finger on the underpass layer
                vias.append(vb); via_turn.append(tid)
                add_poly([vb, pt(sigma * b, r_nom(n, b))], layer, tid, "stub")
                cur = b
            pts = sample(n, cur, tb, layer, sigma)
            add_poly(pts, layer, tid, kind)
            return length + plen(pts)

        plan = None if spiral else self._step_plan()
        arc = None if spiral else self._arc_plan()
        arc_polys = []                         # "stepped_arc": (layer, sigma, n, points) of every arc

        def step_end(n):
            # TX_STEPPED_ANGLE_DEG: local angle where the step from turn n reaches turn n + 1 (each step staggered
            # back from the one inside it; mm along the turn it lands on)
            return (plan["first"] - n * plan["stagger"]) / (r0 + (n + 1) * pitch)

        def step_start(n):
            # ... and where it leaves turn n: one run earlier, in mm along turn n - so that on every turn the end of
            # the step inside it and the start of the next step are exactly stagger + run apart
            return (plan["first"] - n * plan["stagger"] - plan["run"]) / (r0 + n * pitch)

        def turn_span(n):
            """local angles (ta, tb) of turn n between the steps"""
            if arc is not None:
                # "stepped_arc": from the arc of the turn inside it (turn 0: from the terminal via) to its own arc
                return (0.0 if n == 0 else arc["up"][n - 1]), two_pi + arc["low"][n]
            if plan is None:
                return 0.0, (two_pi if spiral else two_pi - step)
            return (0.0 if n == 0 else step_end(n - 1)), two_pi + step_start(n)

        def step_poly(n, layer, sigma):
            if arc is not None:
                # "stepped_arc": an arc centred on the terminal via, from turn n to turn n + 1 (the last one up to
                # its outermost point, where the outer tail starts); sharp corners where it meets the turns
                xv, rho = arc["xv"], arc["rho"][n]
                b0, b1 = arc["b_low"][n], (arc["b_up"][n] if n < T - 1 else 0.0)
                m = max(2, int(math.ceil(abs(b1 - b0) / (2.0 * math.acos(max(-1.0, 1.0 - arc["tol"] / rho))))))
                pts = [pt(sigma * (two_pi + arc["low"][n]), r0 + n * pitch)]
                for b in np.linspace(b0, b1, m + 1)[1:-1]:
                    x, y = xv + rho * math.cos(b), rho * math.sin(b)
                    pts.append(pt(sigma * math.atan2(y, x), math.hypot(x, y)))
                pts.append(pt(sigma * arc["up"][n], r0 + (n + 1) * pitch) if n < T - 1 else pt(0.0, arc["apex"]))
                add_poly(pts, layer, -1, "step")
                arc_polys.append((layer, sigma, n, pts))
                return
            if plan is not None:
                # one straight piece at TX_STEPPED_ANGLE_DEG from turn n to the next one (or the outer terminal)
                pts = [pt(sigma * (two_pi + step_start(n)), r0 + n * pitch), pt(sigma * step_end(n), r0 + (n + 1) * pitch)]
                if n == T - 1 and step_end(n) < -1e-12:
                    # the outermost step lands before the terminal: along the circle to the outer tail
                    e = step_end(n)
                    ths = [e] + [-k * step for k in range(int(math.floor(-e / step - 1e-9)), 0, -1)] + [0.0]
                    pts += [pt(sigma * th, r0 + T * pitch) for th in ths[1:]]
                add_poly(pts, layer, -1, "step")
                return
            # radial step from turn n to the next one (or to the outer terminal), exactly as in the original layout
            last = pt(sigma * (two_pi - step), r0 + n * pitch)
            a1 = ((n + 1) * -0.08 - 0.75) * step
            a2 = ((n + 1) * -0.08 - 0.30) * step
            add_poly([last, pt(sigma * a1, r0 + n * pitch), pt(sigma * a2, r0 + (n + 1) * pitch - pitch / 3.0),
                      pt(0.0, r0 + (n + 1) * pitch)], layer, -1, "step")

        tail_end = pt(0.0, self.tx_tail_end_radius)
        parallel_len = 0.0
        if mode == "series2":
            p_layer, q_layer = lay["layers"]
            for layer, sigma, id0 in ((p_layer, -1, 0), (q_layer, +1, T)):
                gos = []
                if layer == self.tab_layer:
                    gos = [(lo, hi) if sigma > 0 else (two_pi - hi, two_pi - lo) for lo, hi in go_windows]
                for n in range(T):
                    emit_turn(n, id0 + n, layer, sigma, *turn_span(n), gos, "turn")
                    if not spiral:
                        step_poly(n, layer, sigma)
                add_poly([pt(0.0, arc["apex"] if arc is not None else r0 + T * pitch), tail_end], layer, -1, "tail")
            vias.insert(0, pt(0.0, r0)); via_turn.insert(0, 0)          # joins the two spirals at the inner end
            tail_inner = None
        else:
            tail_inner = lay["tail_layer"]
            # terminal: inner tail and the via joining it to the start of the spiral (as in the original layout)
            add_poly([pt(0.0, r0), tail_end], tail_inner, -1, "tail")
            if plan is not None or arc is not None:
                vias.append(pt(0.0, r0)); via_turn.append(0)               # (on the trace ends)
            else:
                vias.append(pt(0.15 * step, r0 + (pitch * 0.15 / steps if spiral else 0.0))); via_turn.append(0)
            for n in range(T):
                emit_turn(n, n, base, +1, *turn_span(n), [] if parallel else go_windows, "turn")
                if not spiral:
                    step_poly(n, base, +1)
                if not parallel:
                    continue
                # the parallel arcs of this turn on the other TX layer, between the stitched windows
                order = sorted(range(len(st_windows)), key=lambda i: st_windows[i][0])
                for idx, i in enumerate(order):
                    j = order[(idx + 1) % len(order)]
                    a = win_vias[i][n][1]
                    b = win_vias[j][n][0] + (two_pi if idx + 1 == len(order) else 0.0)
                    if b - a <= 1e-6:
                        continue
                    gos = [(lo + sh, hi + sh) for lo, hi in go_windows for sh in (-two_pi, 0.0, two_pi)
                           if a < lo + sh and hi + sh < b]
                    if not gos:
                        pts = sample(n, a, b, other)
                        add_poly(pts, other, n, "arc")
                        parallel_len += plen(pts)
                        vias.append(pts[0]); via_turn.append(n)
                        vias.append(pts[-1]); via_turn.append(n)
                    else:
                        parallel_len += emit_turn(n, n, other, +1, a, b, gos, "arc")
                        vias.append(pt(a, r_nom(n, a))); via_turn.append(n)
                        vias.append(pt(b, r_nom(n, b))); via_turn.append(n)
            add_poly([pt(0.0, arc["apex"] if arc is not None else r0 + T * pitch), tail_end], base, -1, "tail")
        self.tx_segments, self.tx_vias = segs, vias
        self.tx_seg_info, self.tx_via_turn = info, via_turn
        self.tx_parallel_length_mm = parallel_len
        self.tx_base_layer, self.tx_other_layer, self.tx_tail_layer = base, other, tail_inner
        self.tx_window_list = [(math.degrees(lo + rot), math.degrees(hi + rot), t, k) for lo, hi, t, k in windows]
        if arc is not None:
            self._check_arc_region(arc_polys, pt(0.0, r0))

    def _tx_summary(self):
        P = self.P
        lay, T = self.tx_lay, int(P.TX_TURNS)
        shape = str(P.TX_TURN_SHAPE).lower()
        if self.tx_mode == "series2":
            txt = (f"  TX (series): {T} turns on {self.tx_layer_p} + {T} turns on {self.tx_layer_q}, joined by a via "
                   f"at the inner end, {shape} turns")
        elif self.tx_mode == "single":
            txt = f"  TX (series): {T} turns on {lay['base_layer']}, inner tail on {lay['tail_layer']}, {shape} turns"
        else:
            txt = (f"  TX (parallel): {T} turns on {lay['base_layer']} and the same turns in parallel on "
                   f"{lay['arc_layer']}, stitched through vias around the TX terminal; tail on {lay['arc_layer']}")
        wl = getattr(self, "tx_window_list", None) if self.tx_new_builder else None
        if wl:
            n_f = len(self.tab_segments) // 3
            go = [w for w in wl if w[3] == "go"]
            st = [w for w in wl if w[3] == "stitch" and not w[2]]
            if go:
                txt += (f"\n  TX go-around: {len(go)} window(s) around the {n_f} finger(s) on {self.tab_layer} "
                        f"(neighbouring fingers share one): every turn runs out to a via just outside the TX ring "
                        f"and around the finger on {lay['bracket_layer']}; finger tips at r = {self.tab_end_radius:.2f} mm")
            if st:
                txt += (f"\n  TX windows: {len(st)} around the {n_f} finger(s) on {self.tab_layer}, the turns on "
                        f"{self.tab_layer} stitched to {lay['base_layer']}")
            txt += f"; {len(self.tx_vias) - 1} TX vias besides the terminal via"
        arc = self._arc_plan()
        if arc is not None:
            txt += (f"\n  TX arcs: {T} around the terminal via (stepped_arc), radius {arc['rho'][0]:.3f} ... "
                    f"{arc['rho'][-1]:.3f} mm" + (" (TX_STEPPED_ARC_RADIUS_MM = auto)" if arc["auto"] else "")
                    + (f", smallest gap to other TX copper {self.tx_arc_gap:.3f} mm"
                       if getattr(self, "tx_arc_gap", None) is not None else "")
                    + f"; the outer tail starts at r = {arc['apex']:.3f} mm")
        plan = self._step_plan()
        if plan is not None:
            txt += (f"\n  TX steps: {math.degrees(plan['theta']):g} deg to the turns (TX_STEPPED_ANGLE_DEG), "
                    f"{plan['run']:.2f} mm along the turn each, {plan['gap']:.3f} mm between neighbouring steps")
            if plan["stagger"] > 0:
                txt += f", each step {plan['stagger']:.2f} mm before the one inside it"
        if getattr(self, "min_tx_self_clearance", None) is not None:
            txt += (f"\n  TX copper: smallest gap between different turns {self.min_tx_self_clearance:.3f} mm, "
                    f"TX via to RX copper {self.min_tx_via_rx_clearance:.3f} mm")
        return txt

    def _check_tx_copper(self):
        """New TX builder: TX copper against itself (all turns are one net, so KiCad's DRC cannot see a via or a
        jog touching another turn - it would short two turns) and the TX vias against the RX copper."""
        P = self.P
        clr, vr = float(P.MIN_CLEARANCE_MM), float(P.VIA_DIAMETER_MM) / 2.0
        tw, rw = float(P.TX_TRACE_WIDTH_MM), float(P.RX_TRACE_WIDTH_MM)
        pitch, T = float(P.TX_PITCH_MM), int(P.TX_TURNS)
        info = self.tx_seg_info
        A = np.array([[s[0][0], s[0][1]] for s in self.tx_segments])
        B = np.array([[s[1][0], s[1][1]] for s in self.tx_segments])
        layer = np.array([s[2] for s in self.tx_segments])
        turn = np.array([t for t, _k in info])
        kind = np.array([k for _t, k in info])
        worst_tt, worst_tv, worst_vr = pitch - tw, 1e9, 1e9
        cut = max(pitch, tw + clr) + 0.5                   # distances above this are of no interest
        spiral = str(P.TX_TURN_SHAPE).lower() == "spiral"
        rot = math.radians(self._tx_start())
        # away from the window vias the turns run at the nominal pitch (checked with the parameters), so only the
        # copper near a via (the jogs, the run-outs, the brackets, the via ends) is measured
        Vw = np.array(self.tx_vias[1:], dtype=float).reshape(-1, 2)
        reach = 2.0 * vr + 2.0 * pitch + 1.5 + (T * pitch if self.tx_goaround else 0.0)
        if len(Vw):
            cA = np.hypot(*(A[:, None, :] - Vw[None, :, :]).transpose(2, 0, 1)).min(axis=1) if len(Vw) * len(A) < 4e7 \
                else points_segments_min_distance(A, Vw, Vw)
            close = cA < reach
        else:
            close = np.zeros(len(A), dtype=bool)
        for L in set(layer.tolist()):
            on = layer == L
            for n in sorted(set(turn[on & close].tolist())):
                if n < 0:
                    continue
                mine = on & (turn == n) & close
                others = on & (((turn != n) & (turn >= 0)) | ((kind == "tail") & (turn < 0))) & close
                if not others.any():
                    continue
                pts = np.vstack([A[mine], B[mine], 0.5 * (A[mine] + B[mine])])
                if spiral:
                    # a spiral turn runs straight on into the next one at the TX start angle: skip those junctions
                    nl = n % T
                    for rj in (self.tx_first_radius + nl * pitch, self.tx_first_radius + (nl + 1) * pitch):
                        J = np.array([self.cx + math.cos(rot) * rj, self.cy + math.sin(rot) * rj])
                        pts = pts[np.hypot(*(pts - J).T) > 2.0 * pitch + tw]
                if len(pts):
                    worst_tt = min(worst_tt, near_points_segments_min_distance(pts, A[others], B[others], cut) - tw)
        # TX vias against the traces of the other turns (all layers: through vias), each other, and the RX copper
        rxa = np.array([[s[0][0], s[0][1]] for s in self.rx_segments])
        rxb = np.array([[s[1][0], s[1][1]] for s in self.rx_segments])
        V = np.array(self.tx_vias, dtype=float).reshape(-1, 2)
        vt = np.array(self.tx_via_turn)
        # RX copper near the TX ring only (the rest is far away)
        rmin = self.tx_first_radius - 2.0 * vr - 4.0
        near = np.hypot(rxa[:, 0] - self.cx, rxa[:, 1] - self.cy) > rmin
        near |= np.hypot(rxb[:, 0] - self.cx, rxb[:, 1] - self.cy) > rmin
        if near.any():
            worst_vr = float(points_segments_min_distance(V, rxa[near], rxb[near]).min()) - rw / 2.0 - vr
        for n in sorted(set(vt[1:].tolist())):
            sel = ((turn != n) & (turn >= 0)) | ((kind == "tail") & (turn < 0)) | ((kind == "step") & (turn < 0))
            sel &= close
            vs = V[1:][vt[1:] == n]                        # (the terminal via sits on the tails by design)
            if sel.any():
                worst_tv = min(worst_tv, near_points_segments_min_distance(vs, A[sel], B[sel], cut + vr) - tw / 2.0 - vr)
            ov = V[1:][vt[1:] != n]
            if len(ov):
                dd = np.hypot(*(vs[:, None, :] - ov[None, :, :]).transpose(2, 0, 1)).min()
                worst_tv = min(worst_tv, float(dd) - 2.0 * vr)
        self.min_tx_self_clearance = min(worst_tt, worst_tv)
        self.min_tx_via_rx_clearance = worst_vr
        if worst_tt < clr - 1e-6:
            print(f"WARNING: two TX turns come within {worst_tt:.3f} mm of each other (wanted {clr} mm): all TX turns "
                  f"are one net, so KiCad's DRC will not flag it, but it shorts turns; raise TX_PITCH_MM",
                  file=sys.stderr)
        if worst_tv < clr - 1e-6:
            print(f"WARNING: a TX via comes within {worst_tv:.3f} mm of another TX turn or via (wanted {clr} mm): all "
                  f"TX turns are one net, so KiCad's DRC will not flag it, but it shorts turns; raise TX_PITCH_MM or "
                  f"use smaller vias", file=sys.stderr)
        if worst_vr < clr - 1e-6:
            print(f"WARNING: a TX via comes within {worst_vr:.3f} mm of RX copper (wanted {clr} mm)", file=sys.stderr)

    def _build_tx_one_layer_spiral(self):
        P = self.P
        cx, cy = self.cx, self.cy
        r0 = self.tx_first_radius
        rot = math.radians(self._tx_start())

        def pt(angle, radius):
            angle += rot
            return (cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)

        pts = self._spiral_points(+1, pt)
        tail_end = pt(0.0, self.tx_tail_end_radius)
        self.tx_segments, self.tx_vias = [], []
        self.tx_segments.append((pts[0], tail_end, "F.Cu"))                 # terminal tail on Top
        for a, b in zip(pts[:-1], pts[1:]):
            self.tx_segments.append((a, b, "B.Cu"))
        self.tx_segments.append((pts[-1], tail_end, "B.Cu"))                # terminal tail on Bottom
        self.tx_vias.append(pt(0.15 / self.tx_steps * 2.0 * math.pi, r0 + P.TX_PITCH_MM * 0.15 / self.tx_steps))

    def _build_tx_two_layers(self):
        """TX on two layers: a spiral that runs INWARDS (counter-clockwise) on layer P from the terminal,
        a through via at the innermost point, and a spiral that runs OUTWARDS (counter-clockwise) on
        layer Q back to the terminal.  Both terminals leave radially outwards at TX_START_ANGLE_DEG."""
        P = self.P
        cx, cy = self.cx, self.cy
        steps, turns = self.tx_steps, int(P.TX_TURNS)
        r0, pitch = self.tx_first_radius, P.TX_PITCH_MM
        rot = math.radians(self._tx_start())

        def pt(angle, radius):
            angle += rot
            return (cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)

        def outward(sense):
            """vertices of an outward spiral starting at (r0, angle 0); ends at the tail start
            (r0 + turns*pitch, angle 0).  sense = +1 counter-clockwise, -1 its mirror image."""
            pts = []
            for n in range(turns + 1):
                radius = r0 + n * pitch
                if n > 0:
                    a1 = (n * -0.08 - 0.75) / steps * 2.0 * math.pi
                    a2 = (n * -0.08 - 0.30) / steps * 2.0 * math.pi
                    pts.append(pt(sense * a1, r0 + (n - 1) * pitch))
                    pts.append(pt(sense * a2, radius - pitch / 3.0))
                if n == turns:
                    pts.append(pt(0.0, radius))
                    break
                for s in range(steps):
                    pts.append(pt(sense * s / steps * 2.0 * math.pi, radius))
            return pts

        tail_end = pt(0.0, self.tx_tail_end_radius)
        if str(P.TX_TURN_SHAPE).lower() == "spiral":
            q_pts = self._spiral_points(+1, pt)
            p_pts = self._spiral_points(-1, pt)[::-1]
        else:
            q_pts = outward(+1)                   # layer Q: outwards, counter-clockwise
            p_pts = outward(-1)[::-1]             # layer P: its mirror image, run inwards = counter-clockwise
        self.tx_segments, self.tx_vias = [], []
        for pts, layer in ((p_pts, self.tx_layer_p), (q_pts, self.tx_layer_q)):
            for a, b in zip(pts[:-1], pts[1:]):
                self.tx_segments.append((a, b, layer))
        self.tx_segments.append((p_pts[0], tail_end, self.tx_layer_p))
        self.tx_segments.append((q_pts[-1], tail_end, self.tx_layer_q))
        self.tx_vias.append(pt(0.0, r0))          # joins the two spirals at their innermost point

    # --------------------------------------------------- generation warnings
    def _warn_clearances(self):
        P = self.P
        need = P.VIA_DIAMETER_MM / 2.0 + P.MIN_CLEARANCE_MM
        a = np.array([[s[0][0], s[0][1]] for s in self.rx_segments])
        b = np.array([[s[1][0], s[1][1]] for s in self.rx_segments])
        owner = np.array([s[4] for s in self.rx_segments])
        txa = np.array([[s[0][0], s[0][1]] for s in self.tx_segments])
        txb = np.array([[s[1][0], s[1][1]] for s in self.tx_segments])
        worst = (1e9, None)
        for p, net, k, j in self.rx_vias:
            other = owner != k
            d = point_segments_distance(np.asarray(p), a[other], b[other]).min() - P.RX_TRACE_WIDTH_MM / 2.0
            dtx = point_segments_distance(np.asarray(p), txa, txb).min() - P.TX_TRACE_WIDTH_MM / 2.0
            d = min(d, dtx)
            if d < worst[0]:
                worst = (d, (k, j))
        # via-to-via clearance (RX and TX vias, any net)
        centers = np.array([v[0] for v in self.rx_vias] + list(self.tx_vias))
        via_gap = 1e9
        if len(centers) > 1:
            dx = centers[:, None, 0] - centers[None, :, 0]
            dy = centers[:, None, 1] - centers[None, :, 1]
            dist = np.hypot(dx, dy) + np.eye(len(centers)) * 1e9
            via_gap = float(dist.min()) - P.VIA_DIAMETER_MM
        self.min_via_clearance = (worst[0] - P.VIA_DIAMETER_MM / 2.0) if worst[1] else None
        if via_gap < P.MIN_CLEARANCE_MM:
            print(f"WARNING: two vias are only {via_gap:.3f} mm apart (wanted {P.MIN_CLEARANCE_MM} mm)",
                  file=sys.stderr)
        if worst[1] and worst[0] < need:
            print(f"WARNING: a via sits only {worst[0] - P.VIA_DIAMETER_MM / 2.0:.3f} mm from other copper "
                  f"(wanted {P.MIN_CLEARANCE_MM} mm); phase/node {worst[1]}", file=sys.stderr)
        # bridging fingers against the TX tail (F.Cu) and the TX via (through all layers)
        if self.tab_segments:
            fa = np.array([[t[0][0], t[0][1]] for t in self.tab_segments])
            fb = np.array([[t[1][0], t[1][1]] for t in self.tab_segments])
            tail = [(np.array(t[0]), np.array(t[1])) for t in self.tx_segments if t[2] == self.tab_layer]
            if len(tail) > 50:
                # many TX segments on the finger layer (TX on that layer): the exact test only for the ones that
                # come anywhere near a finger
                ta_ = np.array([t[0] for t in tail]); tb_ = np.array([t[1] for t in tail])
                ln = np.hypot(*(tb_ - ta_).T)
                dmin = np.minimum(points_segments_min_distance(ta_, fa, fb), points_segments_min_distance(tb_, fa, fb))
                tail = [t for t, d, l in zip(tail, dmin, ln) if d < l + 1.0 + P.MIN_CLEARANCE_MM]
            # finger against TX tail: copper gap between two traces (0 distance when the TX tail crosses a finger)
            g_tail = 1e9
            for ta, tb in tail:
                for i in range(len(fa)):
                    g_tail = min(g_tail, segment_distance(fa[i], fb[i], ta, tb))
            g_tail -= (P.RX_TRACE_WIDTH_MM + P.TX_TRACE_WIDTH_MM) / 2.0
            # finger against TX via: copper gap between a trace and a via pad
            g_via = 1e9
            for v in self.tx_vias:
                g_via = min(g_via, float(point_segments_distance(np.asarray(v), fa, fb).min()))
            g_via -= (P.VIA_DIAMETER_MM + P.RX_TRACE_WIDTH_MM) / 2.0
            gmin = min(g_tail, g_via)
            self.min_tab_tx_clearance = gmin
            if self.n_sub > 1:
                fo = np.array([t[4] for t in self.tab_segments])
                gf = 1e9
                for i in range(len(fa)):
                    other = fo != fo[i]
                    if not other.any():
                        continue
                    for pnt in (fa[i], fb[i]):
                        gf = min(gf, point_segments_distance(pnt, fa[other], fb[other]).min())
                gf -= P.RX_TRACE_WIDTH_MM
                self.min_finger_gap = gf
                if gf < P.MIN_CLEARANCE_MM:
                    print(f"WARNING: fingers of neighbouring sub-coils are only {gf:.3f} mm apart "
                          f"(wanted {P.MIN_CLEARANCE_MM} mm); raise RX_SUBCOIL_SPLIT_ELEC_DEG or lower RX_TAB_WIDTH_MM",
                          file=sys.stderr)
            if gmin < P.MIN_CLEARANCE_MM:
                print(f"WARNING: an RX bridging finger comes within {gmin:.3f} mm of the TX tail/via on {self.tab_layer}; "
                      f"change TX_START_ANGLE_DEG", file=sys.stderr)
        if self.inner_edge_clear() < 0.3:
            print("WARNING: inner-tip vias are closer than 0.3 mm to the inner board edge", file=sys.stderr)
        if getattr(self, "tx_seg_info", None) is not None:
            self._check_tx_copper()

    def inner_edge_clear(self):
        P = self.P
        return (self.ri - P.VIA_DIAMETER_MM / 2.0) - self.inner_edge_radius

    # ------------------------------------------------------------- output
    def write(self, path):
        """Write the stator to `path` (RunCoilGenerator.py chooses it: OutputDirectoryManager.py)."""
        P = self.P
        if not path:
            raise ValueError("StatorDesign.write needs the file path; boards are written by RunCoilGenerator.py")
        title, comments = self.title_block()
        self.page_mm = page_size(P, self.cx, self.cy, self.outer_edge_radius)
        board = KiCadBoard(title=title, comments=comments, page=self.page_mm, thickness=P.PCB_THICKNESS_MM,
                           copper_layers=P.PCB_LAYERS)
        for net in (P.TX_NET, P.RX_NET_PHASE_1_3, P.RX_NET_PHASE_0_2):
            board.net(net)
        for p, q, layer, net, _ in self.rx_segments:
            board.segment(p, q, P.RX_TRACE_WIDTH_MM, layer, net)
        for p, q, layer in self.tx_segments:
            board.segment(p, q, P.TX_TRACE_WIDTH_MM, layer, P.TX_NET)
        for p, net, _, _ in self.rx_vias:
            board.via(p, P.VIA_DIAMETER_MM, P.VIA_DRILL_MM, net)
        for p in self.tx_vias:
            board.via(p, P.VIA_DIAMETER_MM, P.VIA_DRILL_MM, P.TX_NET)
        board.circle((self.cx, self.cy), self.inner_edge_radius, "Edge.Cuts", P.EDGE_LINE_WIDTH_MM)
        board.circle((self.cx, self.cy), self.outer_edge_radius, "Edge.Cuts", P.EDGE_LINE_WIDTH_MM)
        board.save(path)
        return path

    LAYER_WORDS = {"F.Cu": "Top", "In1.Cu": "Inner-1", "In2.Cu": "Inner-2", "B.Cu": "Bottom"}

    def title_block(self):
        """(title, comment lines) for the KiCad title block (the frame of the drawing; File > Page Settings), as
        "Keyword: value" pairs.  KiCad's default drawing sheet shows Comment1 ... Comment4 (Comment1 at the
        bottom); the rest are kept in the file."""
        P = self.P
        w = lambda l: self.LAYER_WORDS.get(l, l)
        f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
        loops = f"{self.N} loop" + ("s" if self.N != 1 else "")
        subs = "no sub-coils" if self.n_sub == 1 else f"{self.n_sub} sub-coils"
        title = f"Stator {loops}, {subs}"
        lay = self.tx_lay
        T = int(P.TX_TURNS)
        if self.tx_mode == "series2":
            tx = f"TX: Series, Turns: {T} {w(self.tx_layer_p)} {T} {w(self.tx_layer_q)}"
        elif self.tx_mode == "parallel":
            tx = f"TX: Parallel, Turns: {T} {w(lay['layers'][0])} {T} {w(lay['layers'][1])}"
        else:
            tx = f"TX: Single Layer, Turns: {T} {w(lay['base_layer'])}, Tail: {w(lay['tail_layer'])}"
        if self.tx_windows_on:
            tx += ", Style: " + ("Around the Finger" if self.tx_goaround else "Stitched")
        n_f = len(self.tab_segments) // 3
        kind = {"all": "Every Outer Tip", "single": "One per Coil"}.get(str(P.RX_TABS).lower(), "")
        fingers = f"Fingers: {n_f} {w(self.tab_layer)}, Style: {kind}" if n_f else "Fingers: None"
        comments = [
            tx,                                                                              # Comment1 (bottom)
            f"Loops: {self.N}, SIN: Net {P.RX_NET_PHASE_0_2}, Phase 0 (+) / 2 (-), "
            f"COS: Net {P.RX_NET_PHASE_1_3}, Phase 1 (+) / 3 (-)",
            f"RX: Rising: {w(self.rising_layer)}, Falling: {w(self.falling_layer)}, {fingers}",
            f"Radius-Outer: {f(self.outer_edge_radius)} mm, Radius-Inner: {f(self.inner_edge_radius)} mm, "
            f"Width-TX: {f(float(P.TX_TRACE_WIDTH_MM))} mm, Width-RX: {f(float(P.RX_TRACE_WIDTH_MM))} mm",  # Comment4
            f"RX Band: Radius-Inner: {f(self.ri)} mm, Radius-Outer: {f(self.ro)} mm, Sub-Coils: {self.n_sub}"
            + (f", Split: {f(self.split_deg)} el. deg" if self.n_sub > 1 else ""),
            "Generator: StatorGenerator.py",
        ]
        return title, comments

    def summary(self):
        P = self.P
        lines = [
            f"Stator: {self.N} loop(s) -> {self.N} electrical period(s) per turn, "
            f"unique range {360.0 / self.N:g} deg",
            f"  RX band r = {self.ri:g} ... {self.ro:g} mm, profile = {P.RX_PROFILE}, "
            f"{self.S} segments per period (RX chord tolerance {chord_tolerance(P, 'RX'):g} mm); "
            f"TX {self.tx_steps} points per turn",
            f"  PCB layers {P.PCB_LAYERS}: RX rising edges on {self.rising_layer}, falling edges on {self.falling_layer}",
            (f"  RX sub-coils per coil: {self.n_sub}, split {self.split_deg:g} electrical deg "
             f"(requested {P.RX_SUBCOIL_SPLIT_ELEC_DEG:g}), {len(self.junction)} junctions"
             if self.n_sub > 1 else "  RX sub-coils per coil: 1"),
            self._tx_summary(),
            f"  RX segments {len(self.rx_segments)}, RX vias {len(self.rx_vias)} "
            f"(+{len(self.tx_vias)} TX), TX segments {len(self.tx_segments)}",
            f"  RX bridging fingers: {'none' if not self.tab_segments else str(len(self.tab_segments) // 3) + ' (3 segments each on %s), tip radius %.2f mm' % (self.tab_layer, self.tab_end_radius)}"
            + ("".join(f"\n    {t['net']}: one finger at {t['angle_deg']:.1f} deg, {t['tx_offset_deg']:.1f} deg from the TX tail"
                       for t in self.single_tabs) if self.single_tabs else ""),
            f"  TX ring r = {self.tx_first_radius:g} ... {self.tx_radii[-1]:g} mm (tail end "
            f"{self.tx_tail_end_radius:g} mm)"
            + (f"; terminal via {abs(self.terminal_via_shift):g} mm "
               f"{'inside' if self.terminal_via_shift > 0 else 'outside'} the first turn (TX_INSIDE_VIA_DISTANCE_MM), "
               f"{self.terminal_via_clearance:.3f} mm from the other turns"
               if getattr(self, "terminal_via_shift", 0.0) and getattr(self, "terminal_via_clearance", None) is not None
               else (f"; terminal via on the first turn (the centre of the arcs), {self.terminal_via_clearance:.3f} mm "
                     f"from the other turns"
                     if self.tx_shape == "arc" and getattr(self, "terminal_via_clearance", None) is not None else "")),
            f"  board edge: bore r = {self.inner_edge_radius:g} mm, outer r = {self.outer_edge_radius:g} mm",
        ]
        b = self.band
        if b["mode"] != "radii" or b["inner_from"] != "band" or b["outer_from"] != "band":
            parts = []
            if b["mode"] == "centre":
                parts.append(f"RX band = RX_R_BASE_MM {(b['ri'] + b['ro']) / 2:g} +- RX_A_MM {(b['ro'] - b['ri']) / 2:g}")
            if b["inner_from"] == "edge":
                parts.append(f"the RX inside radius by INNER_EDGE_RADIUS_MM (+ INNER_EDGE_INSET_MM {P.INNER_EDGE_INSET_MM:g})")
            if b["outer_from"] == "edge":
                parts.append(f"the RX outside radius by OUTER_EDGE_RADIUS_MM (- {outer_edge_room(P):g} mm for the TX turns, "
                             f"tail and margins)")
            given = [n for n, how in (("bore", b["inner_from"]), ("outer edge", b["outer_from"])) if how == "both"]
            if given:
                parts.append(f"board {' and '.join(given)} as given (RX band and board edge both set)")
            lines.append("  set from the board edge: " + "; ".join(parts) if b["mode"] == "board" or
                         "edge" in (b["inner_from"], b["outer_from"]) else "  " + "; ".join(parts))
        if self.min_via_clearance is not None:
            lines.append(f"  smallest via-to-copper clearance {self.min_via_clearance:.3f} mm")
        return "\n".join(lines)


def main():
    """Only RunCoilGenerator.py writes boards (a new folder per run, see OutputDirectoryManager.py).
    Run alone, this prints the summary and writes nothing."""
    stator = StatorDesign(P_DEFAULT)
    print(stator.summary())
    print("No file written: boards are written by RunCoilGenerator.py, into a new folder for every run.")


if __name__ == "__main__":
    main()
