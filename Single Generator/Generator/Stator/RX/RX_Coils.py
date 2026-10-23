"""
RX_Coils.py  -  the RX coils: the polyline resolution, the four phases (and their sub-coils) as closed curves,
the layer of every edge, the series junctions with their vias, and the copper itself (segments, vias, fingers).
The functions take the RX builder (`rx`, RX_Builder.py).  Nothing to edit here.

Phase k (k = 0..3) is one closed polyline going once around the axis, LOOPS sine periods per turn, phase k rotated
by a quarter period.  Phases 0 and 2 are in antiphase and together make one coil (net A); phases 1 and 3 make the
other coil, 90 deg later (net B).  Per coil, the two strands cross each other 2 * LOOPS times; the crossings of
different phases all fall exactly on polyline nodes.
  * Net weight: strand "+" is traversed forward, strand "-" backward, so the coil is the chain of 2 * LOOPS lobes
    of alternating orientation.  The net area is zero (no pick-up of the uniform TX field).
  * Layers: every crossing needs the two traces on different layers.  Each phase carries its RISING edges on one
    layer and its FALLING edges on the other, with the layer swap (via) at the outer and inner tip of every lobe.
    That is the layout with the fewest vias that also keeps the two strands of a coil on opposite layers (equal
    air-gap exposure of SIN and COS).  It needs 8 vias per period.
  * Series junction: one crossing per coil is turned into a connection (both traces swap layers there without a
    via) so the two strands become ONE closed series loop.  The loop is broken by hand wherever the terminals go.
  * Sub-coils (RX_SUBCOILS > 1): every coil is built from several antiphase pairs ("sub-coils") spread
    RX_SUBCOIL_SPLIT_ELEC_DEG apart and wired in series by extra junctions: more signal (2 * cos(split / 2) for
    two) and the low odd harmonics attenuated.  Each coil is still ONE closed series loop.
"""

import math
import sys

import numpy as np

from Generator.Stator.RX import RX_Fingers
from Generator.Core import Layers
from Generator.Core.Conflict import ParameterConflict
from Generator.Core.Copper import Segment, Via
from Generator.Core.Geometry import point_segments_distance, chord_tolerance

RISING, FALLING = 0, 1          # edge classes (radius grows / shrinks with angle)


def chord_error(rx, S):
    """Largest distance (mm) between an RX curve and its chords with S chords per loop: rx needs radius(s) (the radius
    law, RX_Profiles.radius_law) and L (one loop, rad).  Used by pick_steps and by ConflictRules."""
    def point(t):
        xi = 2.0 * math.pi * t / S
        r = rx.radius(np.sin(xi))
        phi = rx.L * t / S
        return np.stack([r * np.cos(phi), r * np.sin(phi)], axis=-1)
    i = np.arange(S, dtype=float)
    p0, p1, pm = point(i), point(i + 1), point(i + 0.5)
    return float(np.max(np.hypot(*(pm - 0.5 * (p0 + p1)).T)))


def pick_steps(rx):
    P = rx.P
    if P.STEPS_PER_LOOP != "auto":
        return int(P.STEPS_PER_LOOP)
    err = None
    tol = chord_tolerance(P, "RX")
    for S in range(48, 1025, 8):
        err = chord_error(rx, S)
        if err <= tol:
            return S
    # the limit of 1024 chords per loop was reached without meeting the tolerance
    print(f"WARNING: RX_CHORD_TOLERANCE_MM = {tol:g} mm needs more than 1024 chords per loop; "
          f"STEPS_PER_LOOP = auto stops at 1024 ({err:.4f} mm chord error). Raise RX_CHORD_TOLERANCE_MM, or set "
          f"STEPS_PER_LOOP to a fixed value (a multiple of 8, up to 4096)", file=sys.stderr)
    return 1024

# ------------------------------------------------------------ sub-coils


def setup_subcoils(rx):
    P, S = rx.P, rx.S
    rx.n_sub = int(P.RX_SUBCOILS)
    if rx.n_sub > 1:
        unit = 2.0 * 360.0 / S                       # two polyline nodes, in electrical degrees
        m = int(round(P.RX_SUBCOIL_SPLIT_ELEC_DEG / unit))
        if m < 1:
            raise ParameterConflict(("RX_SUBCOIL_SPLIT_ELEC_DEG", "STEPS_PER_LOOP"), f"the split is below the polyline "
                                    f"resolution ({unit:g} electrical degrees per node pair); raise the split or "
                                    f"STEPS_PER_LOOP")
        rx.split_nodes = 2 * m
    else:
        rx.split_nodes = 0
    rx.split_deg = rx.split_nodes * 360.0 / S
    # shift of every sub-coil in polyline nodes (symmetric about the coil axis)
    rx.sub_shift = [int(round((s - (rx.n_sub - 1) / 2.0) * rx.split_nodes)) for s in range(rx.n_sub)]

# ------------------------------------------------------------ polylines


def phase_nodes(rx):
    N, S = rx.N, rx.S
    rx.NS = N * S
    j = np.arange(rx.NS)
    xi = 2.0 * math.pi * (j % S) / S
    r = rx.radius(np.sin(xi))
    rx.rnode = r
    rx.curves = []                  # one entry per closed curve: sub-coil s, phase k
    rx.nodes = []
    for s in range(rx.n_sub):
        shift = rx.L * rx.sub_shift[s] / S
        for k in range(4):
            phi = rx.L * (j / S) + k * rx.L / 4.0 + shift
            rx.nodes.append(np.stack([rx.cx + r * np.cos(phi), rx.cy + r * np.sin(phi)], axis=1))
            rx.curves.append(dict(sub=s, k=k, off=k * S // 4 + rx.sub_shift[s],
                                    net=[rx.P.RX_NET_PHASE_0_2, rx.P.RX_NET_PHASE_1_3][k % 2]))
    rx.nets_of_phase = [c["net"] for c in rx.curves]
    rx.ncurves = len(rx.curves)


def curve_index(rx, sub, k):
    return sub * 4 + k

# --------------------------------------------------------- layer scheme


def assign_layers(rx):
    P, N, S, NS = rx.P, rx.N, rx.S, rx.NS
    # segment j runs from node j to node j+1; its edge class follows from
    # where it sits between the two tip vias.
    tip = int(round(P.RX_VIA_ELECTRICAL_DEG / 360.0 * S))
    tip = min(max(tip, S // 8 + 2), 3 * S // 8 - 2)        # keep clear of crossings
    low_tip = tip + S // 2
    i = np.arange(NS) % S
    base = np.where(((i - low_tip) % S) < S // 2, RISING, FALLING)
    rx.edge_class = [base.copy() for _ in range(rx.ncurves)]
    rx._tip, rx._low_tip = tip, low_tip % S          # node of the outer / inner tip via of every lobe

    # Series junction: a crossing of a RISING strand ("plus", traversed forward)
    # with a FALLING strand ("minus", traversed backward) is turned into a
    # connection (both traces swap layers there without a via).  Two closed
    # curves joined this way become ONE closed series loop.
    rx.junction = []
    rx._jvias = []                  # (x, y) of every junction via placed so far
    rx._windows = [[] for _ in range(rx.ncurves)]   # reserved node ranges per curve
    # 1) inside every sub-coil: the antiphase pair (phase 0/2 or 1/3) at mid radius.
    #    Coil B's junction is placed about half a turn from coil A's (LOOPS // 2 loops on, plus the quarter period
    #    between the coils), so the junction vias of different nets stay apart; for LOOPS = 1 they are only a
    #    quarter turn apart, for LOOPS = 2 about 135 deg.
    for sub in range(rx.n_sub):
        for kp, km, loop_pref in ((0, 2, 0), (1, 3, N // 2)):
            plus, minus = curve_index(rx, sub, kp), curve_index(rx, sub, km)
            loops = [loop_pref] if rx.n_sub == 1 else [(loop_pref + t) % N for t in range(N)]
            done = False
            for loop in loops:
                jp = loop * S
                jm = ((loop - 1) * S + S // 2) % NS
                d = try_junction(rx, plus, jp, minus, jm, legacy=True)
                if d is not None:
                    commit_junction(rx, plus, jp, minus, jm, d)
                    done = True
                    break
            if not done:
                raise ParameterConflict(("LOOPS", "RX_SUBCOILS", "RX_TRACE_WIDTH_MM", "VIA_DIAMETER_MM",
                                         "MIN_CLEARANCE_MM"),
                                        "the junction vias that join the two strands of a coil do not fit between "
                                        "the curves with the required clearance (half a via + half an RX trace + "
                                        "MIN_CLEARANCE_MM from the other strand, and MIN_CLEARANCE_MM between the two "
                                        "vias): fewer loops or sub-coils, a wider RX band, smaller vias, narrower RX "
                                        "traces or a smaller clearance give them room")
    # 2) between neighbouring sub-coils of one coil: join "plus" of sub-coil s
    #    with "minus" of sub-coil s+1 (an antiphase partner, so the signals ADD)
    for sub in range(rx.n_sub - 1):
        for kp, km in ((0, 2), (1, 3)):
            plus, minus = curve_index(rx, sub, kp), curve_index(rx, sub + 1, km)
            cands = crossings(rx, plus, minus)
            placed = False
            for ja, jb in cands:
                d = try_junction(rx, plus, ja, minus, jb, legacy=False)
                if d is not None:
                    commit_junction(rx, plus, ja, minus, jb, d)
                    placed = True
                    break
            if not placed:
                raise ParameterConflict(("RX_SUBCOILS", "RX_SUBCOIL_SPLIT_ELEC_DEG", "RX_VIA_ELECTRICAL_DEG", "LOOPS"),
                                        "no crossing of neighbouring sub-coils is clear enough for the via that joins "
                                        "them.  The junction stub must end before the tip via of its lobe and keep "
                                        "clear of the other phases, so it fits only when RX_VIA_ELECTRICAL_DEG is "
                                        "near 90 (with 2 sub-coils about 45 + split / 2 ... 135 - split / 2, less a "
                                        "few degrees for the stub).  Bring RX_VIA_ELECTRICAL_DEG closer to 90 or "
                                        "lower the split (a wider RX band does not widen that range).  A large split "
                                        "can fail at every angle: with the default band, 0.8 mm vias and 0.2 mm "
                                        "traces and clearance it fits up to a split of about 47; a wider RX band, "
                                        "smaller vias, narrower RX traces or a smaller clearance give room for more")

# -- helpers for junctions ------------------------------------------------


def min_dist(rx, p, curve, node_idx):
    a = rx.nodes[curve][node_idx[:-1]]
    b = rx.nodes[curve][node_idx[1:]]
    return float(point_segments_distance(np.asarray(p), a, b).min())


def angular_position(rx, ja, curve):
    x, y = rx.nodes[curve][ja % rx.NS]
    return math.atan2(y - rx.cy, x - rx.cx)


def crossings(rx, a, b):
    """(ja, jb) where curve a (on a rising edge) and curve b (on a falling edge) cross at a node,
    best first (farthest from the junctions already placed)."""
    NS, S = rx.NS, rx.S
    ia = np.arange(NS)
    jb = (ia + rx.curves[a]["off"] - rx.curves[b]["off"]) % NS
    same = np.abs(rx.rnode[ia] - rx.rnode[jb]) < 1e-9
    out = []
    for ja in np.where(same)[0]:
        jbb = int(jb[ja])
        u = (ja % S - rx._low_tip) % S               # position along the rising half
        w = (jbb % S - rx._tip) % S                  # position along the falling half
        if 1 <= u < S // 2 and 1 <= w < S // 2:
            out.append((int(ja), jbb))
    used = [math.atan2(y - rx.cy, x - rx.cx) for x, y in rx._jvias]

    def score(c):
        ang = angular_position(rx, c[0], a)
        if not used:
            return 4.0
        return min(abs((ang - u0 + math.pi) % (2 * math.pi) - math.pi) for u0 in used)
    out.sort(key=lambda c: (-round(score(c), 3), c[0]))
    return out


def overlaps(rx, curve, lo, hi):
    """True when the (circular) node range lo..hi of a curve touches a reserved window."""
    NS = rx.NS
    for wlo, whi in rx._windows[curve]:
        for sh in (-NS, 0, NS):
            if lo + sh <= whi and wlo <= hi + sh:
                return True
    return False


def try_junction(rx, plus, jp, minus, jm, legacy):
    """Smallest stub length d (in nodes) for which the junction fits with the required
    clearances, or None."""
    P, S, NS = rx.P, rx.S, rx.NS
    req = P.VIA_DIAMETER_MM / 2.0 + P.RX_TRACE_WIDTH_MM / 2.0 + P.MIN_CLEARANCE_MM
    dmax = S // 8 - 2
    if not legacy:
        u = (jp % S - rx._low_tip) % S
        w = (jm % S - rx._tip) % S
        dmax = min(dmax, S // 2 - S // 8 - u - 2, w - S // 8 - 2)
    for cand in range(1, dmax + 1):
        if rx.n_sub > 1 or not legacy:
            if overlaps(rx, plus, jp - 2, jp + cand + 2) or overlaps(rx, minus, jm - cand - 2, jm + 2):
                continue
        via_minus = rx.nodes[minus][(jm - cand) % NS]
        via_plus = rx.nodes[plus][(jp + cand) % NS]
        near_plus = np.arange(jp - cand - 4, jp + cand + 5) % NS
        near_minus = np.arange(jm - cand - 4, jm + cand + 5) % NS
        d1 = min_dist(rx, via_minus, plus, near_plus)
        d2 = min_dist(rx, via_plus, minus, near_minus)
        pair_gap = float(np.hypot(*(via_minus - via_plus))) - P.VIA_DIAMETER_MM
        if not (min(d1, d2) >= req and pair_gap >= P.MIN_CLEARANCE_MM):
            continue
        if rx.n_sub > 1 or not legacy:
            # clear of every other curve (through-hole vias touch all layers) and of other junction vias
            ok = True
            for c in range(rx.ncurves):
                if c in (plus, minus):
                    continue
                for v in (via_minus, via_plus):
                    a_, b_ = rx.nodes[c], np.roll(rx.nodes[c], -1, axis=0)
                    if float(point_segments_distance(np.asarray(v), a_, b_).min()) < req:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                for (vx, vy) in rx._jvias:
                    for v in (via_minus, via_plus):
                        if math.hypot(v[0] - vx, v[1] - vy) - P.VIA_DIAMETER_MM < P.MIN_CLEARANCE_MM:
                            ok = False
            if not ok:
                continue
        return cand
    return None


def commit_junction(rx, plus, jp, minus, jm, d):
    NS = rx.NS
    for t in range(d):
        rx.edge_class[minus][(jm - d + t) % NS] = RISING
        rx.edge_class[plus][(jp + t) % NS] = FALLING
    rx._windows[plus].append((jp - 2, jp + d + 2))
    rx._windows[minus].append((jm - d - 2, jm + 2))
    for c, node in ((minus, (jm - d) % NS), (plus, (jp + d) % NS)):
        rx._jvias.append(tuple(rx.nodes[c][node]))
    rx.junction.append(dict(plus=plus, minus=minus, jp=jp, jm=jm, stub=d))


def layer_name(rx, edge_class):
    return rx.rising_layer if edge_class == RISING else rx.falling_layer

# ------------------------------------------------------ items to write



def emit_copper(rx, starts_of, q):
    """The copper of every curve: its segments (Segment: a, b, layer, net, curve), one via at every layer change
    that is not a junction, and - where a finger starts (starts_of[curve] = start nodes, q = nodes between its legs) - the three
    pieces of the finger on the finger layer, out to rx.tab_end_radius and back.  Fills rx.rx_segments, rx.rx_vias
    and rx.tab_segments (the finger pieces, a subset of rx_segments)."""
    NS = rx.NS
    rx.rx_segments, rx.rx_vias = [], []        # Segment / Via records (Core/Copper.py)
    rx.tab_segments = []                        # subset of rx_segments that are bridging fingers
    junction_nodes = set()
    for jn in rx.junction:
        junction_nodes.add((jn["plus"], jn["jp"]))
        junction_nodes.add((jn["minus"], jn["jm"]))
    outward = RX_Fingers.outward(rx)
    for k in range(rx.ncurves):
        cls, net = rx.edge_class[k], rx.nets_of_phase[k]
        em = []                                      # (p, q, layer, node_start, node_end)
        j = 0
        while j < NS:
            if j in starts_of[k]:
                c = (j + q) % NS
                pa, pc = rx.nodes[k][j], rx.nodes[k][c]
                pao, pco = outward(pa), outward(pc)
                em.append((pa, pao, rx.tab_layer, j, None))
                em.append((pao, pco, rx.tab_layer, None, None))
                em.append((pco, pc, rx.tab_layer, None, c))
                j += q
            else:
                em.append((rx.nodes[k][j], rx.nodes[k][(j + 1) % NS],
                           layer_name(rx, cls[j]), j, (j + 1) % NS))
                j += 1
        for i, (p, qq, layer, n0, n1) in enumerate(em):
            rx.rx_segments.append(Segment(p, qq, layer, net=net, curve=k))
            if layer != em[i - 1][2] and n0 is not None and (k, n0) not in junction_nodes:
                rx.rx_vias.append(Via(p, net=net, curve=k, node=n0, layers=Layers.via_pair(em[i - 1][2], layer)))
            if n0 is None or n1 is None:
                rx.tab_segments.append(rx.rx_segments[-1])
