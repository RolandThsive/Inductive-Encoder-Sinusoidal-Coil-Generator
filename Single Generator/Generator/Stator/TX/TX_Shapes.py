"""
TX_Shapes.py  -  the shape of the TX turns (TX_SHAPE): where every turn runs between its steps or arcs, the
straight steps of "stepped_diagonal" (step_plan), the arcs of "stepped_arc" around the terminal via (arc_plan), the
smooth "spiral", and the number of points per turn.  The functions take the TX builder (`tx`, TX_Builder.py) that
holds the geometry.  Nothing to edit here.
"""

import math

import numpy as np

from Generator.Core.Conflict import ParameterConflict
from Generator.Core.Geometry import chord_tolerance

ARC_MARGIN_MM = 0.02           # added to the smallest arc radius on "auto" (and the chord sag of the turns)


def arc_radius_limits(P):
    """Limits of the radius of the innermost arc of a "stepped_arc" TX (mm):
      corner : the arcs are one pitch apart and arc n must reach turn n + 1, so the innermost radius must be
               larger than TX_PITCH_MM
      via    : the innermost arc keeps MIN_CLEARANCE_MM from the terminal via (via radius + half a trace +
               clearance)
      top    : the last arc ends (radius + (turns - 1) x pitch) outside the first turn, where the outer tail starts;
               it must stay inside the tail end, so the radius must be smaller than TX_PITCH_MM + TX_TAIL_EXTRA_MM"""
    p = float(P.TX_PITCH_MM)
    via = float(P.VIA_DIAMETER_MM) / 2.0 + float(P.TX_TRACE_WIDTH_MM) / 2.0 + float(P.MIN_CLEARANCE_MM)
    return dict(corner=p, via=via, top=p + float(P.TX_TAIL_EXTRA_MM))


def arc_first_radius(P, sag=0.0):
    """Radius of the innermost arc of a "stepped_arc" TX (mm): TX_STEPPED_ARC_RADIUS_MM, or ("auto") the smallest
    radius that forms a corner with the next turn and clears the via, plus ARC_MARGIN_MM and the chord sag."""
    v = getattr(P, "TX_STEPPED_ARC_RADIUS_MM", "auto")
    if _is_auto(v):
        lim = arc_radius_limits(P)
        return max(lim["corner"], lim["via"]) + ARC_MARGIN_MM + float(sag)
    return float(v)


def _is_auto(v):
    return isinstance(v, str) and v.strip().lower() == "auto"


def points_per_turn(P, outer_radius):
    """Points per TX turn: TX_STEPS, or (auto) the fewest, a multiple of 8, whose chords of the outermost turn lie
    within TX_CHORD_TOLERANCE_MM of the circle."""
    s = getattr(P, "TX_STEPS", "auto")
    if not (isinstance(s, str) and s.lower() == "auto"):
        return int(s)
    r, tol = float(outer_radius), chord_tolerance(P, "TX")
    n = int(math.ceil(math.pi / math.acos(max(-1.0, 1.0 - tol / r))))
    return max(48, -(-n // 8) * 8)


def step_plan(tx):
    """The steps between the turns of a "stepped_diagonal" TX at TX_STEPPED_ANGLE_DEG (None for the other
    shapes).  Every step is one straight piece from a turn to the next one at that angle to the turn
    (90 = straight out).  Two neighbouring steps are parallel, one pitch apart along the radius, so the copper
    gap between them is pitch * cos(angle) - trace width: when that is below MIN_CLEARANCE_MM, each step starts
    a little earlier than the one inside it (stagger), which opens the gap to pitch * cos + stagger * sin.
      theta (rad), run (mm along the turn that one step takes), stagger (mm per turn), span (mm: how far the
      steps reach back from the terminal, all turns)."""
    P = tx.P
    if tx.tx_shape != "diagonal":
        return None
    th = math.radians(min(90.0, max(1.0, float(P.TX_STEPPED_ANGLE_DEG))))
    p, tw, clr = float(P.TX_PITCH_MM), float(P.TX_TRACE_WIDTH_MM), float(P.MIN_CLEARANCE_MM)
    run = p * math.cos(th) / math.sin(th)
    gap = p * math.cos(th) - tw                                  # copper gap between neighbouring steps
    T = int(P.TX_TURNS)
    # (the turns are polylines: a chord lies up to `sag` inside its circle, plus a hair)
    sag = (tx.tx_first_radius + T * p) * (1.0 - math.cos(math.pi / float(tx.tx_steps)))
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


def ramp_angle(tx):
    """Slope (rad) of the run from a turn down to the terminal via: the TX's own step angle (TX_STEPPED_ANGLE_DEG),
    45 deg for the shapes without straight steps."""
    return step_plan(tx)["theta"] if tx.tx_shape == "diagonal" else math.radians(45.0)


def arc_plan(tx):
    """The arcs of a "stepped_arc" TX (None for the other shapes).  All arcs are centred on the terminal via,
    which sits on the first turn at the TX start angle; arc n (radius rho0 + n x pitch) leaves turn n where it
    crosses it on the far side of the terminal and runs round the via to turn n + 1, which it meets on the near
    side; the last arc ends at its outermost point, where the outer tail starts.  Arcs one pitch apart have the
    same copper gap as the turns.  Local coordinates: x towards the terminal, angles from the centre relative
    to the TX start angle (positive = the way the turns run on a counter-clockwise layer).
      rho, xv (the via's distance from the centre), low[n] / up[n] (angle where arc n meets turn n / n + 1),
      b_low[n] / b_up[n] (the same points seen from the via), apex (radius where the outer tail starts),
      ext (smallest, largest angle of the arcs), tol (chord tolerance)."""
    if tx.tx_shape != "arc":
        return None
    if getattr(tx, "_arc_cache", None) is not None:
        return tx._arc_cache
    P = tx.P
    T, p = int(P.TX_TURNS), float(P.TX_PITCH_MM)
    r0 = float(tx.tx_first_radius)
    sag = (r0 + T * p) * (1.0 - math.cos(math.pi / float(tx.tx_steps)))
    rho0 = arc_first_radius(P, sag)
    lim = arc_radius_limits(P)
    if rho0 <= lim["corner"] + 1e-9:
        raise ParameterConflict(("TX_STEPPED_ARC_RADIUS_MM", "TX_PITCH_MM"), f"the innermost arc radius ({rho0:g} mm) "
                                f"must be larger than the pitch ({p:g} mm): the arcs are one pitch apart and each "
                                f"must reach the next turn")
    if rho0 >= lim["top"] - 1e-9:
        raise ParameterConflict(("TX_STEPPED_ARC_RADIUS_MM", "TX_PITCH_MM", "TX_TAIL_EXTRA_MM"), f"the innermost arc "
                                f"radius ({rho0:g} mm) must be smaller than pitch + tail length ({lim['top']:g} mm): "
                                f"the last arc would reach past the end of the TX tail")
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
    tx._arc_cache = dict(rho=rho, xv=xv, low=low, up=up, b_low=b_low, b_up=b_up, apex=xv + rho[-1], ext=ext,
                           tol=chord_tolerance(P, "TX"), auto=isinstance(getattr(P, "TX_STEPPED_ARC_RADIUS_MM",
                                                                                  "auto"), str))
    return tx._arc_cache


def step_end(tx, n):
    """stepped_diagonal: local angle where the step from turn n reaches turn n + 1 (each step staggered back
    from the one inside it; mm along the turn it lands on)."""
    return (tx.plan["first"] - n * tx.plan["stagger"]) / (tx.r0 + (n + 1) * tx.pitch)


def step_start(tx, n):
    """... and where it leaves turn n: one run earlier, in mm along turn n - so that on every turn the end of
    the step inside it and the start of the next step are exactly stagger + run apart."""
    return (tx.plan["first"] - n * tx.plan["stagger"] - tx.plan["run"]) / (tx.r0 + n * tx.pitch)


def turn_span(tx, n):
    """Local angles (ta, tb) of turn n between its steps or arcs."""
    two_pi = 2.0 * math.pi
    if tx.spiral:
        return 0.0, two_pi
    if tx.arc is not None:
        # "stepped_arc": from the arc of the turn inside it (turn 0: from the terminal via) to its own arc
        return (0.0 if n == 0 else tx.arc["up"][n - 1]), two_pi + tx.arc["low"][n]
    return (0.0 if n == 0 else step_end(tx, n - 1)), two_pi + step_start(tx, n)


def outer_tail_start(tx):
    """Radius where the outer tail leaves: the apex of the last arc, or the circle outside the last turn."""
    return tx.arc["apex"] if tx.arc is not None else tx.r0 + tx.T * tx.pitch


def emit_step(tx, n, layer, sigma):
    """The step from turn n to turn n + 1 (the last one to the outer tail): an arc centred on the terminal via
    (stepped_arc) or one straight piece at TX_STEPPED_ANGLE_DEG (stepped_diagonal).  Nothing for a spiral."""
    if tx.spiral:
        return
    two_pi, T, r0, pitch = 2.0 * math.pi, tx.T, tx.r0, tx.pitch
    if tx.arc is not None:
        # an arc from turn n round the via to turn n + 1 (the last one up to its outermost point, where the outer
        # tail starts); sharp corners where it meets the turns
        arc = tx.arc
        xv, rho = arc["xv"], arc["rho"][n]
        b0, b1 = arc["b_low"][n], (arc["b_up"][n] if n < T - 1 else 0.0)
        m = max(2, int(math.ceil(abs(b1 - b0) / (2.0 * math.acos(max(-1.0, 1.0 - arc["tol"] / rho))))))
        pts = [tx.pt(sigma * (two_pi + arc["low"][n]), r0 + n * pitch)]
        for b in np.linspace(b0, b1, m + 1)[1:-1]:
            x, y = xv + rho * math.cos(b), rho * math.sin(b)
            pts.append(tx.pt(sigma * math.atan2(y, x), math.hypot(x, y)))
        pts.append(tx.pt(sigma * arc["up"][n], r0 + (n + 1) * pitch) if n < T - 1 else tx.pt(0.0, arc["apex"]))
        tx.add_poly(pts, layer, -1, "step")
        tx.arc_polys.append((layer, sigma, n, pts))
        return
    pts = [tx.pt(sigma * (two_pi + step_start(tx, n)), r0 + n * pitch),
           tx.pt(sigma * step_end(tx, n), r0 + (n + 1) * pitch)]
    if n == T - 1 and step_end(tx, n) < -1e-12:
        # the outermost step lands before the terminal: along the circle to the outer tail
        e = step_end(tx, n)
        ths = [e] + [-k * tx.step for k in range(int(math.floor(-e / tx.step - 1e-9)), 0, -1)] + [0.0]
        pts += [tx.pt(sigma * th, r0 + T * pitch) for th in ths[1:]]
    tx.add_poly(pts, layer, -1, "step")

# ------------------------------------------------------------ the layouts
