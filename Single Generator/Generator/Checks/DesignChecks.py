"""
DesignChecks.py  -  checks on the finished boards (after the builders): the board outline against what it must
contain, the inner hole against the vias, the page, the rotor's edges (check_design); the RX vias and fingers
against the TX, the TX against itself (all TX turns are one net, so KiCad's DRC cannot see a via or a jog touching
another turn), the TX terminal via against the other turns and the RX band, the arcs of a stepped_arc TX, and the
TX vias against the RX copper (check_stator_clearances, check_tx_terminal, check_tx_copper: they print WARNING
lines on stderr, which classify_generator_output turns into report items).  Nothing to edit here.
"""

import math
import sys

import numpy as np

from Generator.Core.Geometry import (point_segments_distance, points_segments_min_distance,
                                     near_points_segments_min_distance, segment_distance)
from Generator.Core.Conflict import Report
from Generator.Core.KiCadWriter import SHEET_FRAME_MM, PAGE_GAP_MM, page_size
from Generator.Stator.TX import TX_Shapes, TX_Terminal


def check_tx_terminal(tx):
    """The arcs around the terminal via (stepped_arc) and the terminal via itself, after the TX is built."""
    if getattr(tx, "terminal_search_note", None):
        print(tx.terminal_search_note, file=sys.stderr)
    if tx.arc is not None:
        check_arc_region(tx, tx.arc_polys, tx.pt(0.0, tx.r0))
    if tx.tx_vias:
        measure_terminal_via(tx, tx.terminal_via_shift, tx.terminal_pieces_added)


def check_arc_region(tx, arc_polys, via):
    """"stepped_arc": the smallest copper gap around the terminal via between pieces of TX copper on the same layer
    that are not joined there (all TX turns are one net, so KiCad's DRC cannot see it).  The pieces: every arc,
    the start and the end of every turn (a full turn apart along the copper), the outer tail.  Joined: arc n with
    the end of turn n and the start of turn n + 1, the last arc with the outer tail.  (The via itself is measured
    by _place_terminal_via.)"""
    P = tx.P
    T, tw, clr = int(P.TX_TURNS), float(P.TX_TRACE_WIDTH_MM), float(P.MIN_CLEARANCE_MM)
    arc = TX_Shapes.arc_plan(tx)
    V = np.asarray(via, dtype=float)
    reach = arc["rho"][-1] + 1.5
    rot = math.radians(tx.start())
    sig = {layer: sg for layer, sg, _n, _p in arc_polys}
    pieces = {}                                       # (layer, name) -> list of (a, b)

    def put(layer, name, a, b):
        a, b = np.asarray(a, float), np.asarray(b, float)
        if min(np.hypot(*(a - V)), np.hypot(*(b - V))) <= reach:
            pieces.setdefault((layer, name), []).append((a, b))
    for layer, _sg, n, pts in arc_polys:
        for a, b in zip(pts[:-1], pts[1:]):
            put(layer, ("arc", n), a, b)
    for a, b, layer, _net, _curve, tid, kind in tx.tx_segments:
        if layer not in sig:
            continue
        if kind == "turn" and tid >= 0:
            n = tid % T
            m = 0.5 * (np.asarray(a) + np.asarray(b)) - (tx.cx, tx.cy)
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
    tx.tx_arc_gap = worst if math.isfinite(worst) else None
    tx.tx_arc_gap_pieces = who
    if tx.tx_arc_gap is not None and worst < clr - 1e-6:
        name = lambda k: " ".join(str(x) for x in k[1])
        print(f"WARNING: around the TX terminal via the arcs of the stepped_arc TX come within {worst:.3f} mm of "
              f"other TX copper ({name(who[0])} / {name(who[1])} on {who[0][0]}, wanted {clr} mm): all TX turns are "
              f"one net, so KiCad's DRC will not flag it, but it shorts turns; raise TX_STEPPED_ARC_RADIUS_MM or "
              f"TX_PITCH_MM", file=sys.stderr)

# ================================================================== the terminal via


def measure_terminal_via(tx, D, n_added):
    """How close the terminal via and the copper added by the shift (the last n_added pieces) come to the other
    TX turns and to the RX band; warns below MIN_CLEARANCE_MM."""
    P = tx.P
    vr, tw, clr = float(P.VIA_DIAMETER_MM) / 2.0, float(P.TX_TRACE_WIDTH_MM), float(P.MIN_CLEARANCE_MM)
    rw = float(P.RX_TRACE_WIDTH_MM)
    c = np.array([tx.cx, tx.cy])
    segs = tx.tx_segments
    A = np.array([s_.a for s_ in segs], dtype=float)
    B = np.array([s_.b for s_ in segs], dtype=float)
    vpos = np.asarray(tx.tx_vias[0].at, dtype=float)
    adj = TX_Terminal.adjacency(tx, segs)
    start = [k for k in adj if math.hypot(k[0] - vpos[0], k[1] - vpos[1]) < vr + 1e-6]
    own, best, front = set(), {k: 0.0 for k in start}, [(k, 0.0) for k in start]
    # copper this close to the via along the TX is the via's own (its run down from the turn is vr + D / sin)
    own_reach = TX_Terminal.OWN_COPPER_MM + abs(D) * 3.0
    if abs(D) > 1e-9:
        own_reach = max(own_reach, TX_Terminal.OWN_COPPER_MM + vr + abs(D) / math.sin(TX_Shapes.ramp_angle(tx)))
    while front:
        k, dd0 = front.pop()
        for i in adj.get(k, ()):
            a, b, l = segs[i].a, segs[i].b, segs[i].layer
            own.add(i)
            for p in (a, b):
                kk = TX_Terminal.node(p, l)
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
    lay_f = np.array([s_.layer for s_ in segs])[foreign]
    for sg in segs[len(segs) - n_added:] if n_added else []:
        same = lay_f == sg.layer                                # (traces: the same layer only)
        if not same.any():
            continue
        p, q = np.asarray(sg.a), np.asarray(sg.b)
        n = max(2, int(math.ceil(np.hypot(*(q - p)) / 0.05)))
        pts = p[None, :] + (q - p)[None, :] * np.linspace(0.0, 1.0, n)[:, None]
        g_new = min(g_new, float(points_segments_min_distance(pts, Af[same], Bf[same]).min()) - tw)
    g_rx = float(np.linalg.norm(vpos - c)) - vr - (tx.ro + rw / 2.0)
    tx.terminal_via_clearance = min(g_via, g_new)
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

# ------------------------------------------------- TX windows and the TX layouts of the new builder


def check_tx_copper(tx):
    """New TX builder: TX copper against itself (all turns are one net, so KiCad's DRC cannot see a via or a
    jog touching another turn - it would short two turns) and the TX vias against the RX copper."""
    P = tx.P
    clr, vr = float(P.MIN_CLEARANCE_MM), float(P.VIA_DIAMETER_MM) / 2.0
    tw, rw = float(P.TX_TRACE_WIDTH_MM), float(P.RX_TRACE_WIDTH_MM)
    pitch, T = float(P.TX_PITCH_MM), int(P.TX_TURNS)
    A = np.array([[s.a[0], s.a[1]] for s in tx.tx_segments])
    B = np.array([[s.b[0], s.b[1]] for s in tx.tx_segments])
    layer = np.array([s.layer for s in tx.tx_segments])
    turn = np.array([s.turn for s in tx.tx_segments])
    kind = np.array([s.kind for s in tx.tx_segments])
    worst_tt, worst_tv, worst_vr = pitch - tw, 1e9, 1e9
    cut = max(pitch, tw + clr) + 0.5                   # distances above this are of no interest
    spiral = tx.tx_shape == "spiral"
    rot = math.radians(tx.start())
    # away from the window vias the turns run at the nominal pitch (checked with the parameters), so only the
    # copper near a via (the jogs, the run-outs, the brackets, the via ends) is measured
    Vw = np.array([v.at for v in tx.tx_vias[1:]], dtype=float).reshape(-1, 2)
    reach = 2.0 * vr + 2.0 * pitch + 1.5 + (T * pitch if tx.tx_goaround else 0.0)
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
                for rj in (tx.tx_first_radius + nl * pitch, tx.tx_first_radius + (nl + 1) * pitch):
                    J = np.array([tx.cx + math.cos(rot) * rj, tx.cy + math.sin(rot) * rj])
                    pts = pts[np.hypot(*(pts - J).T) > 2.0 * pitch + tw]
            if len(pts):
                worst_tt = min(worst_tt, near_points_segments_min_distance(pts, A[others], B[others], cut) - tw)
    # TX vias against the traces of the other turns (all layers: through vias), each other, and the RX copper
    rxa = np.array([[s.a[0], s.a[1]] for s in tx.rx_segments])
    rxb = np.array([[s.b[0], s.b[1]] for s in tx.rx_segments])
    V = np.array([v.at for v in tx.tx_vias], dtype=float).reshape(-1, 2)
    vt = np.array([v.turn for v in tx.tx_vias])
    # RX copper near the TX ring only (the rest is far away)
    rmin = tx.tx_first_radius - 2.0 * vr - 4.0
    near = np.hypot(rxa[:, 0] - tx.cx, rxa[:, 1] - tx.cy) > rmin
    near |= np.hypot(rxb[:, 0] - tx.cx, rxb[:, 1] - tx.cy) > rmin
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
    tx.min_tx_self_clearance = min(worst_tt, worst_tv)
    tx.min_tx_via_rx_clearance = worst_vr
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


def check_stator_clearances(stator):
    """The RX vias against the other copper, via against via, the fingers against the TX tail and via, the fingers of
    neighbouring sub-coils, the inner-tip vias against the centre hole, and the TX copper (check_tx_copper).  Prints
    WARNING lines; sets stator.min_via_clearance."""
    P = stator.P
    need = P.VIA_DIAMETER_MM / 2.0 + P.MIN_CLEARANCE_MM
    a = np.array([[s.a[0], s.a[1]] for s in stator.rx_segments])
    b = np.array([[s.b[0], s.b[1]] for s in stator.rx_segments])
    owner = np.array([s.curve for s in stator.rx_segments])
    txa = np.array([[s.a[0], s.a[1]] for s in stator.tx_segments])
    txb = np.array([[s.b[0], s.b[1]] for s in stator.tx_segments])
    worst = (1e9, None)
    for p, _net, k, j, _turn in stator.rx_vias:
        other = owner != k
        d = point_segments_distance(np.asarray(p), a[other], b[other]).min() - P.RX_TRACE_WIDTH_MM / 2.0
        dtx = point_segments_distance(np.asarray(p), txa, txb).min() - P.TX_TRACE_WIDTH_MM / 2.0
        d = min(d, dtx)
        if d < worst[0]:
            worst = (d, (k, j))
    # via-to-via clearance (RX and TX vias, any net)
    centers = np.array([v.at for v in stator.rx_vias] + [v.at for v in stator.tx_vias])
    via_gap = 1e9
    if len(centers) > 1:
        dx = centers[:, None, 0] - centers[None, :, 0]
        dy = centers[:, None, 1] - centers[None, :, 1]
        dist = np.hypot(dx, dy) + np.eye(len(centers)) * 1e9
        via_gap = float(dist.min()) - P.VIA_DIAMETER_MM
    stator.min_via_clearance = (worst[0] - P.VIA_DIAMETER_MM / 2.0) if worst[1] else None
    if via_gap < P.MIN_CLEARANCE_MM:
        print(f"WARNING: two vias are only {via_gap:.3f} mm apart (wanted {P.MIN_CLEARANCE_MM} mm)",
              file=sys.stderr)
    if worst[1] and worst[0] < need:
        print(f"WARNING: a via sits only {worst[0] - P.VIA_DIAMETER_MM / 2.0:.3f} mm from other copper "
              f"(wanted {P.MIN_CLEARANCE_MM} mm); phase/node {worst[1]}", file=sys.stderr)
    # bridging fingers against the TX tail (F.Cu) and the TX via (through all layers)
    if stator.tab_segments:
        fa = np.array([[t.a[0], t.a[1]] for t in stator.tab_segments])
        fb = np.array([[t.b[0], t.b[1]] for t in stator.tab_segments])
        tail = [(np.array(t.a), np.array(t.b)) for t in stator.tx_segments if t.layer == stator.tab_layer]
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
        for v in stator.tx_vias:
            g_via = min(g_via, float(point_segments_distance(np.asarray(v.at), fa, fb).min()))
        g_via -= (P.VIA_DIAMETER_MM + P.RX_TRACE_WIDTH_MM) / 2.0
        gmin = min(g_tail, g_via)
        if stator.n_sub > 1:
            fo = np.array([t.curve for t in stator.tab_segments])
            gf = 1e9
            for i in range(len(fa)):
                other = fo != fo[i]
                if not other.any():
                    continue
                for pnt in (fa[i], fb[i]):
                    gf = min(gf, point_segments_distance(pnt, fa[other], fb[other]).min())
            gf -= P.RX_TRACE_WIDTH_MM
            if gf < P.MIN_CLEARANCE_MM:
                print(f"WARNING: fingers of neighbouring sub-coils are only {gf:.3f} mm apart "
                      f"(wanted {P.MIN_CLEARANCE_MM} mm); raise RX_SUBCOIL_SPLIT_ELEC_DEG or lower RX_TAB_WIDTH_MM",
                      file=sys.stderr)
        if gmin < P.MIN_CLEARANCE_MM:
            print(f"WARNING: an RX bridging finger comes within {gmin:.3f} mm of the TX tail/via on {stator.tab_layer}",
                  file=sys.stderr)
    if stator.inner_edge_clear() < 0.3:
        print("WARNING: inner-tip vias are closer than 0.3 mm to the inner board edge", file=sys.stderr)
    if stator.tx_segments:
        check_tx_copper(stator.tx)
        stator.min_tx_self_clearance = stator.tx.min_tx_self_clearance
        stator.min_tx_via_rx_clearance = stator.tx.min_tx_via_rx_clearance


def check_design(P, stator, rotor=None):
    """Rules that need the generated stator (and rotor).  Returns a Report."""
    rep = Report()
    R = stator.outer_edge_radius
    cx, cy = stator.cx, stator.cy
    ew = float(P.EDGE_LINE_WIDTH_MM)

    # board outline against what it must contain
    if P.OUTER_EDGE_RADIUS_MM is not None:
        need_tx = stator.tx_outer_radius + P.TX_TRACE_WIDTH_MM / 2 + ew / 2
        if R < need_tx - 1e-6:
            rep.conflict(("OUTER_EDGE_RADIUS_MM", "TX_TURNS", "TX_PITCH_MM"), f"the outer board edge ({R:g} mm) cuts "
                         f"through the outermost TX turn (r = {stator.tx_outer_radius:g} mm); it must be at least "
                         f"{need_tx:.2f} mm")
        if stator.tab_end_radius is not None and R < stator.tab_end_radius + P.RX_TRACE_WIDTH_MM / 2 + ew / 2 - 1e-6:
            rep.conflict(("OUTER_EDGE_RADIUS_MM", "RX_TAB_LENGTH_MM"), f"the outer board edge ({R:g} mm) cuts through "
                         f"the RX bridging fingers (they reach r = {stator.tab_end_radius:.2f} mm); raise the edge, "
                         f"shorten the fingers or set RX_TABS = \"none\"")
        if R < stator.tx_tail_end_radius + ew / 2 - 1e-6:
            rep.conflict(("OUTER_EDGE_RADIUS_MM", "TX_TAIL_EXTRA_MM"), f"the outer board edge ({R:g} mm) cuts off the TX "
                         f"tail (it ends at r = {stator.tx_tail_end_radius:g} mm); raise the edge or shorten the tail")
        elif R < stator.tx_tail_end_radius + P.OUTER_EDGE_TAIL_MARGIN_MM - 1e-6:
            rep.conflict(("OUTER_EDGE_RADIUS_MM", "TX_TAIL_EXTRA_MM", "OUTER_EDGE_TAIL_MARGIN_MM"), f"the TX tail ends at "
                         f"r = {stator.tx_tail_end_radius:g} mm, only {R - stator.tx_tail_end_radius:.2f} mm from the "
                         f"board edge ({R:g} mm); the margin asked for is {P.OUTER_EDGE_TAIL_MARGIN_MM:g} mm",
                         level="warning")

    # inner hole against the inner tip vias
    clear = stator.inner_edge_clear()
    if clear is not None and clear < 0:
        # the vias sit on the inner edge of the RX band, INNER_EDGE_INSET_MM from the hole: only the inset matters
        rep.conflict(("INNER_EDGE_INSET_MM", "VIA_DIAMETER_MM"), f"the inner-tip vias run {-clear:.2f} mm over the "
                     f"centre-hole edge: raise INNER_EDGE_INSET_MM (now {P.INNER_EDGE_INSET_MM:g}) to at least "
                     f"{P.VIA_DIAMETER_MM / 2.0 + 0.3:g} mm (half a via plus 0.3 mm)")

    # copper touching copper
    if stator.min_via_clearance is not None and stator.min_via_clearance <= 0:
        rep.error(f"a via touches copper of another net (clearance {stator.min_via_clearance:.3f} mm): "
                  f"the board would short")

    # board against the KiCad page: the page grows (right and down) so that the board stays clear of the drawing
    # frame and the title block; only the top and left side depend on the centre position
    px, py = P.PAGE_SIZE_MM
    margin = SHEET_FRAME_MM + PAGE_GAP_MM
    if cx - R - ew / 2 < margin or cy - R - ew / 2 < margin:
        rep.conflict(("CENTER_X_MM", "CENTER_Y_MM", "OUTER_EDGE_RADIUS_MM"), f"the board (outer radius {R:g} mm at "
                     f"{cx:g}, {cy:g}) comes within {margin:g} mm of the top or left edge of the KiCad page (the drawing "
                     f"frame); it will still be written, but it crosses the frame. Raise the centre to at least "
                     f"{math.ceil(R + ew / 2 + margin):g}", level="warning")
    else:
        w, h = page_size(P, cx, cy, R)
        if (w, h) != (float(px), float(py)):
            rep.info(f"KiCad page {w:g} x {h:g} mm (PAGE_SIZE_MM {px:g} x {py:g} grown so that the board stays clear "
                     f"of the drawing frame and the title block)")

    # rotor
    if rotor is not None:
        for note in rotor.notes:
            rep.info(note)
        # a solder-mask opening that reaches the bore or the outline is cut off by the board edge
        e_mask = getattr(rotor, "mask_expansion", None)
        if e_mask:
            auto = rotor.mode == "according_to_stator"
            if rotor.bore_radius is not None and rotor.r_in - e_mask < rotor.bore_radius + ew / 2.0:
                fix = ("Raise ROTOR_AUTO_EDGE_CLEARANCE_MM or lower the expansion" if auto else
                       "Raise ROTOR_CUSTOM_INNER_RADIUS_MM, lower ROTOR_CUSTOM_BORE_RADIUS_MM or lower the expansion")
                rep.warn(f"the solder-mask opening (ROTOR_SOLDER_MASK_EXPANSION_MM = {e_mask:g}) reaches the "
                         f"bore edge: the copper is only {max(rotor.r_in - rotor.bore_radius - ew / 2.0, 0.0):.2f} "
                         f"mm from it, so the board edge cuts the opening. {fix}")
            if rotor.outline_radius is not None and rotor.r_out + e_mask > rotor.outline_radius - ew / 2.0:
                fix = ("Lower the expansion" if auto else
                       "Lower ROTOR_CUSTOM_OUTER_RADIUS_MM, raise ROTOR_CUSTOM_OUTLINE_RADIUS_MM or lower the "
                       "expansion")
                rep.warn(f"the solder-mask opening (ROTOR_SOLDER_MASK_EXPANSION_MM = {e_mask:g}) reaches the "
                         f"outline: the copper is only "
                         f"{max(rotor.outline_radius - ew / 2.0 - rotor.r_out, 0.0):.2f} mm from it, so the board "
                         f"edge cuts the opening. {fix}")
        if rotor.mode == "according_to_stator":
            cut = getattr(rotor, "cut_overhang", None)
            if cut is not None and cut[0] - cut[1] > 0.01:
                rep.conflict(("ROTOR_AUTO_TX_OVERHANG_MM", "ROTOR_AUTO_EDGE_CLEARANCE_MM", "OUTER_EDGE_RADIUS_MM"),
                             f"an overhang of {cut[0]:g} mm does not fit: the rotor copper must stay "
                             f"{P.ROTOR_AUTO_EDGE_CLEARANCE_MM:g} mm inside the board outline, so it ends {cut[1]:+.2f} mm "
                             f"past the outermost TX turn", level="warning")
            # an edge that was asked for with ROTOR_AUTO_EXTENSION_INNER_MM / _OUTER_MM but had to be cut back
            for side, name, other, cut, why in (
                    ("inner", "ROTOR_AUTO_EXTENSION_INNER_MM", "ROTOR_AUTO_EDGE_CLEARANCE_MM", getattr(rotor, "cut_in", None),
                     f"{P.ROTOR_AUTO_EDGE_CLEARANCE_MM:g} mm from the bore"),
                    ("outer", "ROTOR_AUTO_EXTENSION_OUTER_MM", "ROTOR_AUTO_TX_CLEARANCE_MM", getattr(rotor, "cut_out", None),
                     f"{getattr(P, 'ROTOR_AUTO_TX_CLEARANCE_MM', '?')} mm inside the TX ring")):
                if cut is not None and cut[0] - cut[1] > 0.01:             # (less than 10 um is not worth a warning)
                    asked, allowed = cut
                    rep.conflict((name, other), f"an extension of {asked:g} mm does not fit: the copper must stay {why}, "
                                 f"so at the {side} edge it reaches {allowed:+.2f} mm past the RX band and the rotor is "
                                 f"made with that", level="warning")
            # copper that stops far short of the RX band leaves part of the receiver uncovered
            gap = float(P.AIR_GAP_MM)
            for side, ext in (("inner", rotor.ext_in), ("outer", rotor.ext_out)):
                if ext < -gap:
                    rep.warn(f"the rotor copper stops {-ext:.2f} mm short of the {side} edge of the RX band (more "
                             f"than one air gap): part of the receiver is not covered, so the signal drops and "
                             f"the harmonics grow")
    return rep


def classify_generator_output(text):
    """Turn the generator's own stderr lines into report items.
    "WARNING: ..." lines become warnings; a WARNING that reports a distance of zero or less means
    copper overlaps copper, which is an error (the board would short)."""
    import re
    rep = Report()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper().startswith("WARNING:"):
            msg = line[len("WARNING:"):].strip()
            m = re.search(r"(?:only|within)\s+(-?\d+(?:\.\d+)?)\s*mm", msg)
            if m and float(m.group(1)) <= 0.0:
                rep.error(msg + "  - the copper overlaps, the board would short")
            else:
                rep.warn(msg)
        else:
            rep.info(line)
    return rep
