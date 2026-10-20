"""
TX_Terminal.py  -  the TX terminal: the via that joins the inner tail to the first turn (or the two spirals of a
series TX), moved TX_INSIDE_VIA_DISTANCE_MM towards the centre, with every turn that starts there running down to
it - and where the terminal goes (find_terminal_angle): the TX is built once at 0 deg without finger windows, the
copper of its terminal is swept around the ring against the RX copper, and the angle with the largest gap (or, with
RX_TABS = "single", the nearest to the two fingers that keeps MIN_CLEARANCE_MM) is taken.  The functions take the
TX builder (`tx`, TX_Builder.py).  Nothing to edit here.
"""

import math

import numpy as np

from Generator.Core.Copper import Segment
from Generator.Core.Geometry import points_segments_min_distance
from Generator.Stator.TX import TX_Shapes

OWN_COPPER_MM = 2.0          # TX copper within this path length of the terminal via is the via's own


def node(p, layer):
    """Dictionary key of a polyline node: its position (rounded) and layer."""
    return (round(float(p[0]), 5), round(float(p[1]), 5), layer)


def adjacency(tx, segs):
    """node -> [indices of the pieces that end there] (pieces removed by the trimming are None)."""
    adj = {}
    for i, s in enumerate(segs):
        if s is None:
            continue
        adj.setdefault(node(s.a, s.layer), []).append(i)
        adj.setdefault(node(s.b, s.layer), []).append(i)
    return adj


def place_terminal_via(tx):
    """The via at the TX terminal (tx_vias[0]: inner tail -> first turn, or the via joining the two spirals of a
    series TX).  TX_INSIDE_VIA_DISTANCE_MM moves it that far towards the centre (negative: away from it), at the
    terminal's azimuth (the via and the copper next to it are measured against the other TX turns and the RX band by
    DesignChecks.measure_terminal_via).  A "stepped_arc" TX keeps the via on the first turn: its arcs are
    centred on it."""
    P = tx.P
    D = 0.0 if tx.tx_shape == "arc" else float(getattr(P, "TX_INSIDE_VIA_DISTANCE_MM",
                                                       TX_Shapes.DEFAULT_INSIDE_VIA_DISTANCE_MM))
    tx.terminal_via_shift = D
    tx.terminal_via_clearance = None
    if not tx.tx_vias:
        return
    tx.terminal_pieces_added = shift_terminal_via(tx, D) if abs(D) > 1e-9 else 0


def shift_terminal_via(tx, D):
    """Move the terminal via D mm towards the centre.  Every turn that starts at the terminal leaves its circle a
    little before it and runs down to the via at the slope of the TX's own steps, with a short flat piece (one
    via radius) into the via; a radial inner tail simply runs on to the via.  Returns the number of pieces
    added (they are appended after the kept pieces)."""
    vr = float(tx.P.VIA_DIAMETER_MM) / 2.0
    segs = list(tx.tx_segments)
    adj = adjacency(tx, segs)
    v0 = np.asarray(tx.tx_vias[0].at, dtype=float)
    c = np.array([tx.cx, tx.cy])
    ends = [k for k, e in adj.items() if len(e) == 1 and math.hypot(k[0] - v0[0], k[1] - v0[1]) < vr]
    if not ends:
        return 0
    s0 = segs[adj[ends[0]][0]]                                  # the exact end point (the key is rounded)
    e0 = np.array(s0.a if node(s0.a, s0.layer) == ends[0] else s0.b, dtype=float)
    u = (e0 - c) / np.linalg.norm(e0 - c)                       # outwards at the terminal
    t = np.array([-u[1], u[0]])                                 # along the circle (counter-clockwise)
    r_e = float(np.linalg.norm(e0 - c))
    V = c + u * (r_e - D)
    th = TX_Shapes.ramp_angle(tx)
    flat = vr                                                   # the flat piece into the via
    x_trim = flat + abs(D) / math.tan(th)                       # where the turn leaves its circle (mm along it)

    def along(p):                                               # signed distance along the circle from the terminal
        q = p - c
        return r_e * math.atan2(float(q @ t), float(q @ u))

    def on_circle(x, r):
        a_ = x / r_e
        return c + r * (u * math.cos(a_) + t * math.sin(a_))
    added = []
    for k in ends:
        l = k[2]
        i = adj[k][0]
        a, b = np.asarray(segs[i].a, float), np.asarray(segs[i].b, float)
        far = b if np.hypot(*(a - e0)) < 1e-4 else a
        d = far - e0
        if abs(float(d @ u)) > abs(float(d @ t)):
            # a radial tail: it runs on to the via
            segs[i] = segs[i]._replace(a=(float(V[0]), float(V[1])), b=(float(far[0]), float(far[1])))
            continue
        s = 1.0 if float(d @ t) > 0 else -1.0                   # the way the turn leaves the terminal
        # walk along the turn, removing it up to x_trim, and split the piece that crosses x_trim
        cur, seg_i = e0, i
        while True:
            a, b = np.asarray(segs[seg_i].a, float), np.asarray(segs[seg_i].b, float)
            nxt = b if np.hypot(*(a - cur)) < 1e-4 else a
            xa, xb = s * along(cur), s * along(nxt)
            if xb >= x_trim:
                f = (x_trim - xa) / (xb - xa) if xb > xa else 1.0
                p_trim = cur + (nxt - cur) * f
                segs[seg_i] = segs[seg_i]._replace(a=(float(p_trim[0]), float(p_trim[1])), b=(float(nxt[0]), float(nxt[1])))
                break
            segs[seg_i] = None                                  # removed
            nk = node(nxt, l)
            others = [j for j in adj.get(nk, ()) if j != seg_i and segs[j] is not None]
            if len(others) != 1:
                p_trim = nxt
                break
            cur, seg_i = nxt, others[0]
        F = on_circle(s * flat * (r_e - D) / r_e, r_e - D)
        for p, q in ((V, F), (F, p_trim)):
            added.append(Segment((float(p[0]), float(p[1])), (float(q[0]), float(q[1])), l, turn=-1, kind="terminal"))
    tx.tx_segments = [sg for sg in segs if sg is not None] + added
    tx.tx_vias[0] = tx.tx_vias[0]._replace(at=(float(V[0]), float(V[1])))
    return len(added)


# ================================================================== where the terminal goes
SEARCH_STEP_DEG = 0.5          # the coarse sweep around the ring
REFINE_STEP_DEG = 0.01         # the fine sweep around the best coarse angle
SAMPLE_MM = 0.01               # spacing of the points the terminal copper is sampled with
CHORD_MARGIN_MM = 0.02         # extra gap asked for in the search (the polyline chords and the sampling)
ROUND_MM = 1e-3                # gaps are rounded to this before they are compared (ties are then real ties)
GAP_CAP_MM = 10.0              # a gap is never reported larger than this (nothing nearby)
BLOCKED = -math.inf            # the "gap" of an angle where a finger window would reach the terminal


def terminal_footprint(probe):
    """The copper of the TX that is not a plain turn: the tails, the steps or arcs, the terminal via, the stitching
    vias and the jogs next to them - sampled as points, in the frame where the terminal sits at 0 deg.
    Returns dict(pts {layer: (n, 2) array}, vias (m, 2) array, lo, hi (rad: the angular extent of the terminal, as
    tx_geometry gives it), r_min, r_max (mm))."""
    c = np.array([probe.cx, probe.cy])
    mirrored = probe.tx_lay["layers"][0] if probe.mode == "series" else None   # (series: layer P runs the other way)
    pts = {}
    for s in probe.tx_segments:
        a, b = np.asarray(s.a) - c, np.asarray(s.b) - c
        if s.kind in ("turn", "arc"):
            # a plain piece of a turn runs on its nominal circle (or spiral); the jogs next to the stitching vias
            # do not
            on = True
            for p in (a, b):
                th = (math.atan2(p[1], p[0]) - probe.rot) * (-1.0 if s.layer == mirrored else 1.0)
                if abs(math.hypot(*p) - probe.r_nom(s.turn % probe.T, th % (2.0 * math.pi))) > 1e-6:
                    on = False
            if on:
                continue
        n = max(2, int(math.ceil(np.hypot(*(b - a)) / SAMPLE_MM)) + 1)
        pts.setdefault(s.layer, []).append(a[None, :] + (b - a)[None, :] * np.linspace(0.0, 1.0, n)[:, None])
    pts = {layer: np.vstack(v) for layer, v in pts.items()}
    vias = np.array([np.asarray(v.at) - c for v in probe.tx_vias], dtype=float).reshape(-1, 2)
    allp = np.vstack(list(pts.values()) + [vias])
    r = np.hypot(allp[:, 0], allp[:, 1])
    lo, hi = probe.g["tail"]
    return dict(pts=pts, vias=vias, lo=lo, hi=hi, r_min=float(r.min()), r_max=float(r.max()))


def _rotated(xy, th):
    c, s = math.cos(th), math.sin(th)
    return xy @ np.array([[c, s], [-s, c]])


def terminal_gap(fp, rx_obst, th, P):
    """The smallest copper gap (mm) between the terminal footprint turned to the angle th (rad) and the RX copper
    (traces on the same layer; vias against everything)."""
    tw, rw, vr = float(P.TX_TRACE_WIDTH_MM), float(P.RX_TRACE_WIDTH_MM), float(P.VIA_DIAMETER_MM) / 2.0
    gap = math.inf
    V = _rotated(fp["vias"], th)
    for layer, p in fp["pts"].items():
        q = _rotated(p, th)
        A, B = rx_obst["segs"].get(layer, (None, None))
        if A is not None and len(A):
            gap = min(gap, float(points_segments_min_distance(q, A, B).min()) - tw / 2.0 - rw / 2.0)
        if len(rx_obst["vias"]):
            d = np.hypot(*(q[:, None, :] - rx_obst["vias"][None, :, :]).transpose(2, 0, 1)).min()
            gap = min(gap, float(d) - tw / 2.0 - vr)
    if len(V):
        A, B = rx_obst["all_segs"]
        if len(A):
            gap = min(gap, float(points_segments_min_distance(V, A, B).min()) - vr - rw / 2.0)
        if len(rx_obst["vias"]):
            d = np.hypot(*(V[:, None, :] - rx_obst["vias"][None, :, :]).transpose(2, 0, 1)).min()
            gap = min(gap, float(d) - 2.0 * vr)
    return gap


class RXObstacles:
    """The RX copper as arrays relative to the centre (segments per layer, all segments, vias), with the angle and
    the outer radius of every piece, so that the pieces near one angle can be picked quickly."""

    def __init__(self, rx):
        c = np.array([rx.cx, rx.cy])
        self.layers = {}
        for layer in sorted({s.layer for s in rx.rx_segments}):
            A = np.array([s.a for s in rx.rx_segments if s.layer == layer], dtype=float) - c
            B = np.array([s.b for s in rx.rx_segments if s.layer == layer], dtype=float) - c
            self.layers[layer] = (A, B, self._ang(0.5 * (A + B)), np.maximum(np.hypot(*A.T), np.hypot(*B.T)))
        A = np.array([s.a for s in rx.rx_segments], dtype=float).reshape(-1, 2) - c
        B = np.array([s.b for s in rx.rx_segments], dtype=float).reshape(-1, 2) - c
        self.all = (A, B, self._ang(0.5 * (A + B)), np.maximum(np.hypot(*A.T), np.hypot(*B.T)))
        V = np.array([v.at for v in rx.rx_vias], dtype=float).reshape(-1, 2) - c
        self.vias = (V, self._ang(V), np.hypot(*V.T))

    @staticmethod
    def _ang(p):
        return np.arctan2(p[:, 1], p[:, 0]) if len(p) else np.zeros(0)

    def near(self, th_lo, th_hi, r_lo):
        """dict(segs {layer: (A, B)}, all_segs (A, B), vias (n, 2)): the pieces between the angles th_lo and th_hi
        (rad) that reach out to r_lo or farther."""
        span = (th_hi - th_lo) % (2.0 * math.pi)

        def sel(ang, rmax):
            return (((ang - th_lo) % (2.0 * math.pi)) <= span) & (rmax >= r_lo)
        segs = {l: (A[m], B[m]) for l, (A, B, ang, rmax) in self.layers.items() for m in (sel(ang, rmax),)}
        A, B, ang, rmax = self.all
        m = sel(ang, rmax)
        V, vang, vr = self.vias
        return dict(segs=segs, all_segs=(A[m], B[m]), vias=V[sel(vang, vr)])


def finger_windows_block(probe, rx, th):
    """True when, with the terminal at th (rad), a go-around or stitched window around a finger on a TX layer would
    reach the terminal: the rule TX_Windows.tx_windows applies (no_room) when a TX that is not parallel is built.  A
    parallel TX takes such finger windows into its stitched tail window instead, so nothing blocks it."""
    if not probe.tx_windows_on or not rx.tab_segments or probe.tx_mode == "parallel":
        return False
    g = probe.g
    R = probe.ga["reach_ang"] if probe.tx_goaround else g["reach"] / g["r0"]
    t_lo, t_hi = g["tail"]
    two_pi = 2.0 * math.pi
    for i in range(0, len(rx.tab_segments) - 2, 3):
        legs = [rx.tab_segments[i].a, rx.tab_segments[i + 2].b]
        rel = [((math.atan2(p[1] - rx.cy, p[0] - rx.cx) - th + math.pi) % two_pi) - math.pi for p in legs]
        lo, hi = min(rel), max(rel)
        if hi - lo > math.pi:
            lo, hi = hi, lo + two_pi
        for shift in (-two_pi, 0.0, two_pi):
            if lo - R + shift < t_hi and hi + R + shift > t_lo:
                return True
    return False


def find_terminal_angle(rx, probe, single_target_deg=None):
    """Where the TX terminal goes (deg, in the RX's frame): the angle with the largest copper gap between the
    terminal footprint and the RX copper; with RX_TABS = "single" (single_target_deg = the middle of the two
    fingers) the angle nearest that target whose gap is at least MIN_CLEARANCE_MM - or, when no angle keeps it, the
    largest gap anywhere (the clearance checks then report the shortfall).  A coarse sweep of the whole ring, then a
    fine one around the chosen angle.  Returns (angle_deg, gap_mm, note or None)."""
    P = probe.P
    clr = float(P.MIN_CLEARANCE_MM) + CHORD_MARGIN_MM
    fp = terminal_footprint(probe)
    obstacles = RXObstacles(rx)
    reach = float(P.MIN_CLEARANCE_MM) + float(P.VIA_DIAMETER_MM) + float(P.RX_TRACE_WIDTH_MM) + 0.5
    margin = reach / fp["r_min"] + 0.3                       # (rad) around the terminal's own angular extent

    def gaps(angles_deg):
        out = []
        for a in angles_deg:
            th = math.radians(a)
            if finger_windows_block(probe, rx, th):
                out.append(BLOCKED)
                continue
            out.append(round(min(real_gap(th), GAP_CAP_MM) / ROUND_MM) * ROUND_MM)
        return np.array(out)

    def real_gap(th):
        obst = obstacles.near(th + fp["lo"] - margin, th + fp["hi"] + margin, fp["r_min"] - reach)
        return terminal_gap(fp, obst, th, P)

    def nearest(cand, ref):
        d = np.abs((cand - ref + 180.0) % 360.0 - 180.0)
        return float(cand[int(np.argmin(d))])

    def pick(angles, g, target):
        """the largest gap (ties: nearest the reference angle), or - single mode - the angle nearest the target with
        gap >= clr (None when there is none)"""
        if target is None:
            return nearest(angles[g >= g.max() - 1e-12], reference_angle(rx))
        ok = angles[g >= clr - 1e-12]
        return nearest(ok, target) if len(ok) else None

    note = None
    coarse = np.arange(0.0, 360.0, SEARCH_STEP_DEG)
    g = gaps(coarse)
    th0 = pick(coarse, g, single_target_deg)
    if th0 is None:                                          # single: nowhere near the fingers keeps the clearance
        th0 = pick(coarse, g, None)
        if np.isfinite(g).any():
            note = (f"no place keeps the TX terminal MIN_CLEARANCE_MM ({P.MIN_CLEARANCE_MM:g} mm) from the RX copper; "
                    f"it went where the gap is largest ({g[np.isfinite(g)].max():.3f} mm)")
        else:
            note = ("no place keeps the TX terminal clear of the RX fingers: every angle is blocked by the finger "
                    "windows")
        single_target_deg = None
    fine = np.arange(th0 - SEARCH_STEP_DEG, th0 + SEARCH_STEP_DEG + 1e-9, REFINE_STEP_DEG)
    gf = gaps(fine)
    th1 = pick(fine, gf, single_target_deg)
    if th1 is None or single_target_deg is None:
        th1 = nearest(fine[gf >= gf.max() - 1e-12], th0)
    gap = float(gf[int(np.argmin(np.abs(fine - th1)))])
    if not math.isfinite(gap):
        # every angle here is blocked by a finger window: report the real gap at the chosen angle, never the marker
        gap = real_gap(math.radians(th1))
    return th1 % 360.0, gap, note


def reference_angle(rx):
    """The angle (deg) that settles a tie between equally good places: the middle of the gap that follows the
    sin+ tip of the first loop, so the terminal has the same place in the pattern on every board."""
    j0 = rx.S // 4                                           # the outer tip of the first lobe of phase 0
    tip = rx.nodes[0][j0]
    ang = math.degrees(math.atan2(tip[1] - rx.cy, tip[0] - rx.cx))
    return (ang + 45.0 / rx.N) % 360.0
