"""
TX_Windows.py  -  how the TX makes way for the RX fingers that cross it on a TX layer: the go-around windows
("staggered": every turn runs out to a via beside the finger and a bracket on another layer carries it round) and
the stitched windows of a parallel TX (the turns stop at a via on each side and the other layer carries the
current).  Also the pieces of a turn (sample / emit_turn) and the jogs next to the stitching vias.  The functions
take the TX builder (`tx`, TX_Builder.py).  Nothing to edit here.
"""

import math

from Generator.Core import BoardLayout
from Generator.Core.Conflict import ParameterConflict
from Generator.Stator.TX import TX_Shapes


def tx_geometry(tx, check=True):
    """Dimensions of the stitched windows of a parallel TX (mm and rad): the turns on one layer end at vias -
    staggered along the circle, because the turn pitch is smaller than a via - and the turns of the other
    layer carry the current through the window.  Next to every via the neighbouring turns bend away (jog) far
    enough to keep MIN_CLEARANCE_MM from its pad: all TX turns are one net, so KiCad's DRC would not notice a
    via touching the next turn.  Also gives the angular extent of the TX terminal (`tail`)."""
    P = tx.P
    T, steps = int(P.TX_TURNS), tx.tx_steps
    pitch, tw, rw = float(P.TX_PITCH_MM), float(P.TX_TRACE_WIDTH_MM), float(P.RX_TRACE_WIDTH_MM)
    vr, clr = float(P.VIA_DIAMETER_MM) / 2.0, float(P.MIN_CLEARANCE_MM)
    need = vr + tw / 2.0 + clr                             # via centre to the centre line of another turn
    delta = max(0.0, need + 0.03 - pitch)                  # how far a neighbouring turn bends away
    if check and T > 1 and pitch - tw - delta < clr - 1e-9:
        raise ParameterConflict(("TX_PITCH_MM", "VIA_DIAMETER_MM"), f"a pitch of {pitch:g} mm is too small for the TX "
                                f"vias of the windows: a turn next to a {2 * vr:g} mm via has to bend {delta:.2f} mm "
                                f"away and would then come closer than MIN_CLEARANCE_MM to the turn beyond it. "
                                f"Raise TX_PITCH_MM to at least {(need + 0.03 + tw + clr) / 2.0:.2f} or use smaller "
                                f"vias")
    ramp = max(0.3, 3.0 * delta)
    stag = max(math.sqrt(max(0.0, (2.0 * vr + clr + 0.02) ** 2 - pitch ** 2)), need + ramp + 0.05) if T > 1 else 0.0
    d0 = vr + max(rw, tw) / 2.0 + clr + 0.05               # finger / tail centre line to the nearest via centre
    r0 = tx.tx_first_radius
    reach = d0 + (T - 1) * stag + need + ramp              # how far a window reaches past its obstacle (arc)
    step = 2.0 * math.pi / steps
    spiral = tx.tx_shape == "spiral"
    # around the TX terminal: the steps between the turns (stepped_diagonal), the two tails and the terminal via
    plan = TX_Shapes.step_plan(tx)
    back = plan["span"] / r0 if plan is not None else 0.0          # the steps, behind the terminal
    tail_lo = -back - (tw / 2.0 + clr) / r0
    tail_hi = 0.15 * step + (vr + clr) / r0
    if tx.tx_shape != "arc":
        # the terminal via moved inwards (TX_INSIDE_VIA_DISTANCE_MM) and its run down from the first turn, at the
        # slope TX_Terminal.shift_terminal_via uses (every shape but "stepped_arc", which keeps the via on the turn)
        dv = abs(float(getattr(P, "TX_INSIDE_VIA_DISTANCE_MM", TX_Shapes.DEFAULT_INSIDE_VIA_DISTANCE_MM)))
        ext = (vr + dv / math.tan(TX_Shapes.ramp_angle(tx)) + tw / 2.0 + clr) / r0
        tail_hi = max(tail_hi, ext)
        if tx.tx_mode == "series":                     # the mirrored layer ramps the other way
            tail_lo = min(tail_lo, -ext)
    if tx.tx_mode == "series" and plan is not None:
        # two mirrored spirals: steps on both sides of the terminal
        span = plan["span"] / r0
        tail_lo = min(tail_lo, -span - (tw / 2.0 + clr) / r0)
        tail_hi = max(tail_hi, span + (tw / 2.0 + clr) / r0)
    arc = TX_Shapes.arc_plan(tx)
    if arc is not None:
        # "stepped_arc": the arcs around the terminal via (angles seen from the centre, relative to the terminal)
        lo_a, hi_a = arc["ext"]
        pad = (tw / 2.0 + clr) / r0
        if tx.tx_mode == "series":                     # mirrored arcs on the two layers
            lo_a, hi_a = -max(-lo_a, hi_a), max(-lo_a, hi_a)
        tail_lo = min(tail_lo, lo_a - pad)
        tail_hi = max(tail_hi, hi_a + pad)
    return dict(T=T, steps=steps, pitch=pitch, tw=tw, vr=vr, clr=clr, need=need, delta=delta, ramp=ramp,
                stag=stag, d0=d0, reach=reach, r0=r0, step=step, spiral=spiral, tail=(tail_lo, tail_hi))


def go_geometry(tx):
    """Go-around windows (BoardLayout.goaround_dims) with absolute radii and the angular reach of a window."""
    P = tx.P
    d = dict(BoardLayout.goaround_dims(P))
    d["via_r"] = tx.ro + d["via_off"]
    d["bracket_r"] = [tx.ro + b for b in d["bracket_off"]]
    rmin = tx.tx_first_radius - float(P.TX_TRACE_WIDTH_MM) / 2.0
    d["reach_ang"] = math.asin(min(1.0, d["reach"] / rmin))
    return d


def no_room(tx):
    """The conflict raised when a go-around window would reach the TX terminal."""
    names = ("RX_TABS", "RX_TAB_LAYER", "TX_TURNS")
    msg = ("the TX window under an RX finger would reach the TX terminal (tail / terminal via) wherever the terminal "
           'goes: the fingers leave no room for it between their windows. Use RX_TABS = "single", put the fingers on a '
           'layer without TX turns (RX_TAB_LAYER), use a parallel TX (TX_WIRING = "parallel"), or fewer TX_TURNS')
    plan = TX_Shapes.step_plan(tx)
    if plan is not None and abs(math.degrees(plan["theta"]) - 45.0) > 1e-6:
        names += ("TX_STEPPED_ANGLE_DEG",)
        msg += (f"; or a TX_STEPPED_ANGLE_DEG closer to 45 (now {math.degrees(plan['theta']):g}: its steps take "
                f"{plan['span']:.2f} mm of the turns next to the terminal)")
    return ParameterConflict(names, msg)


def tx_windows(tx, g, ga=None):
    """The windows as obstacle intervals (rad, relative to the TX start, merged where they would overlap):
    [(lo, hi, is_tail_window, kind), ...] sorted.  kind "go" = the turns go around the fingers (go-around),
    "stitch" = the turns of a parallel TX are stitched to the other layer (always around the terminal of a
    parallel TX).  Every window that is not a stitched tail window stays clear of the TX terminal."""
    rot = math.radians(tx.start())
    two_pi = 2.0 * math.pi
    parallel = tx.tx_mode == "parallel"
    spans = []
    for i in range(0, len(tx.tab_segments) - 2, 3):
        legs = [tx.tab_segments[i].a, tx.tab_segments[i + 2].b]
        rel = [((math.atan2(p[1] - tx.cy, p[0] - tx.cx) - rot) % two_pi) for p in legs]
        lo, hi = min(rel), max(rel)
        if hi - lo > math.pi:
            lo, hi = hi, lo + two_pi
        spans.append([lo, hi])
    R_st = g["reach"] / g["r0"]
    R_f = ga["reach_ang"] if tx.tx_goaround else R_st
    obst = [[lo, hi, False, R_f] for lo, hi in spans] if tx.tx_windows_on else []
    t_lo, t_hi = g["tail"]
    if parallel:
        m = (g["need"] + g["ramp"]) / g["r0"]
        tw_ = [t_lo - m, t_hi + m, True, R_st]
        if not tx.tx_windows_on:
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
                raise no_room(tx)
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
        raise ParameterConflict(("RX_TABS", "LOOPS", "TX_TURNS", "RX_TAB_LAYER"), "the TX windows under the RX fingers "
                                'would cover the whole TX ring (too many fingers for the TX vias): use RX_TABS = '
                                '"single", fewer loops or TX turns, or put the fingers on a layer without TX turns')
    if not parallel:
        for lo, hi, _t, R in merged:
            if not (lo - R > t_hi and hi + R < t_lo + two_pi):
                raise no_room(tx)
    finger_kind = "go" if tx.tx_goaround else "stitch"
    return [(lo, hi, t, "stitch" if t else finger_kind) for lo, hi, t, _R in merged]

# ================================================================== building the copper


def plen(pts):
    return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts[:-1], pts[1:]))


def side_angle(lam, side, gn, r):
    """The run-out line of a window side: parallel to the finger leg at the (local) angle lam, gn away from it."""
    return lam + side * math.asin(min(1.0, gn / r))


def cut_angle(tx, n, lam, side, gn):
    th = side_angle(lam, side, gn, tx.r_nom(n, lam))
    return side_angle(lam, side, gn, tx.r_nom(n, th))

# ------------------------------------------------------------ the pieces of a turn


def bump(tx, n, layer, th):
    """Radial jog of turn n on `layer` at th, next to the stitching vias of the neighbouring turns."""
    g, out = tx.g, 0.0
    for tv, sgn in tx.bumps.get((n, layer), ()):
        d = abs(((th - tv + math.pi) % (2.0 * math.pi)) - math.pi) * tx.r_nom(n, th)
        if d < g["need"]:
            out += sgn * g["delta"]
        elif d < g["need"] + g["ramp"]:
            out += sgn * g["delta"] * (1.0 - (d - g["need"]) / g["ramp"])
    return out


def sample(tx, n, ta, tb, layer, sigma=1):
    """Points of turn n from the local angle ta to tb (actual angle sigma x local): the polyline grid plus the
    corners of every jog."""
    two_pi, step, g = 2.0 * math.pi, tx.step, tx.g
    ths = {ta, tb}
    k0, k1 = math.ceil(ta / step + 1e-9), math.floor(tb / step - 1e-9)
    ths.update(k * step for k in range(k0, k1 + 1))
    for tv, _s in tx.bumps.get((n, layer), ()):
        for dd in (g["need"], g["need"] + g["ramp"]):
            for sg in (-1.0, 1.0):
                th = tv + sg * dd / tx.r_nom(n, tv % two_pi)
                for sh in (-two_pi, 0.0, two_pi):
                    if ta < th + sh < tb:
                        ths.add(th + sh)
    out = []
    for th in sorted(ths):
        end = th == ta or th == tb
        out.append(tx.pt(sigma * th, tx.r_nom(n, th) + (0.0 if end else bump(tx, n, layer, th))))
    return out


def emit_turn(tx, n, tid, layer, sigma, ta, tb, gos, kind):
    """Turn n (id tid) on `layer` from the local angle ta to tb, around the go-around windows `gos` (local
    (lo, hi) inside (ta, tb)).  Returns the length of the turn pieces."""
    ga, step = tx.ga, tx.step
    cur, length = ta, 0.0
    for lo, hi in sorted(gos):
        gn, rv, Rn = ga["g"][n], ga["via_r"], ga["bracket_r"][n]
        a, b = cut_angle(tx, n, lo, -1, gn), cut_angle(tx, n, hi, +1, gn)
        pts = sample(tx, n, cur, a, layer, sigma)
        tx.add_poly(pts, layer, tid, kind)
        length += plen(pts)
        va = tx.pt(sigma * side_angle(lo, -1, gn, rv), rv)
        vb = tx.pt(sigma * side_angle(hi, +1, gn, rv), rv)
        tx.add_poly([pts[-1], va], layer, tid, "stub")              # run-out to the via outside the ring
        tx.add_via(va, tid, (layer, tx.blayer))
        ba, bb = side_angle(lo, -1, gn, Rn), side_angle(hi, +1, gn, Rn)
        ths = [ba] + [k * step for k in range(math.ceil(ba / step + 1e-9), math.floor(bb / step - 1e-9) + 1)]
        br = [tx.pt(sigma * th, Rn) for th in ths + [bb]]
        if Rn > rv + 1e-9:
            br = [va] + br + [vb]
        tx.add_poly(br, tx.blayer, tid, "bracket")                # around the finger on the underpass layer
        tx.add_via(vb, tid, (layer, tx.blayer))
        tx.add_poly([vb, tx.pt(sigma * b, tx.r_nom(n, b))], layer, tid, "stub")
        cur = b
    pts = sample(tx, n, cur, tb, layer, sigma)
    tx.add_poly(pts, layer, tid, kind)
    return length + plen(pts)
