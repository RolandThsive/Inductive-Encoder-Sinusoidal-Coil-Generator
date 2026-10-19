"""
Dual_DesignChecks.py  -  checks on the finished dual boards that the Single Generator's own checks (run on each set)
cannot make: the gap between the two sets measured on the built copper, and the gap between the two rotor rings.
Returns Report items in the Single Generator's style.  Nothing to edit here.
"""

import math

from Generator.Core.Conflict import Report


def _segment_radii(seg, cx, cy, half_width):
    """(smallest, largest) distance from the centre of a straight piece of track, copper width included."""
    ax, ay, bx, by = seg.a[0] - cx, seg.a[1] - cy, seg.b[0] - cx, seg.b[1] - cy
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 <= 1e-18 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L2))
    near = math.hypot(ax + t * dx, ay + t * dy)
    far = max(math.hypot(ax, ay), math.hypot(bx, by))
    return near - half_width, far + half_width


def _extent(stator, parts):
    """(innermost, outermost) radius (mm) of the given copper: parts = ((segments, trace width), ...), (vias,)."""
    P, cx, cy = stator.P, stator.cx, stator.cy
    lo, hi = math.inf, 0.0
    for segs, w in parts[0]:
        for s in segs:
            a, b = _segment_radii(s, cx, cy, w / 2.0)
            lo, hi = min(lo, a), max(hi, b)
    vr = float(P.VIA_DIAMETER_MM) / 2.0
    for v in parts[1]:
        r = math.hypot(v.at[0] - cx, v.at[1] - cy)
        lo, hi = min(lo, r - vr), max(hi, r + vr)
    return lo, hi


def copper_extent(stator):
    """(innermost, outermost) radius of a set's copper (mm): every RX and TX segment with its width, every via
    with its diameter."""
    P = stator.P
    return _extent(stator, (((stator.rx_segments, float(P.RX_TRACE_WIDTH_MM)),
                             (stator.tx_segments, float(P.TX_TRACE_WIDTH_MM))), stator.rx_vias + stator.tx_vias))


def rx_extent(stator):
    """(innermost, outermost) radius of a set's RX copper only (mm): the RX segments with their width and the RX
    vias with their diameter."""
    P = stator.P
    return _extent(stator, (((stator.rx_segments, float(P.RX_TRACE_WIDTH_MM)),), stator.rx_vias))


def check_sets(P, layout, stator1, stator2):
    """The gap between the sets on the built copper.  Returns (Report, measured gap)."""
    rep = Report()
    _lo1, reach1 = copper_extent(stator1)
    inner2, _hi2 = copper_extent(stator2)
    gap = inner2 - reach1
    required = layout.gap_required
    if gap < required - 1e-6:
        rep.conflict(("TRACK_GAP_MM", "INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM", "RX_R_BASE_MM", "RX_A_MM"),
                     f"on the built copper set 1 reaches r = {reach1:.3f} mm and set 2 starts at r = {inner2:.3f} mm: "
                     f"{gap:.3f} mm apart, but {required:g} mm must stay free between the sets"
                     + (" (TRACK_GAP_MM)" if layout.gap_setting is not None else " (MIN_CLEARANCE_MM)")
                     + f". Move the RX2 band out by {required - gap:.3f} mm or more")
    else:
        rep.info(f"gap between the sets on the built copper: set 1 reaches r = {reach1:.3f} mm, set 2 starts at "
                 f"r = {inner2:.3f} mm, {gap:.3f} mm free (at least {required:g} needed)")
    tol = float(getattr(P.BOARD, "LAYOUT_TOLERANCE_MM", 0.0) or 0.0)
    if abs(gap - layout.gap_expected) > tol + 1e-9:
        rep.warn(f"the built copper differs from the layout formulas by more than LAYOUT_TOLERANCE_MM ({tol:g} mm): "
                 f"the gap measures {gap:.3f} mm, the formulas expected {layout.gap_expected:.3f} mm (set 1 reach "
                 f"{layout.reach1:.3f} -> {reach1:.3f}, set 2 start {layout.inner2:.3f} -> {inner2:.3f}). The boards "
                 f"are as built; report this difference")
    return rep, gap


def check_rings(P, layout, rotor1, rotor2, stator1=None, stator2=None):
    """The gap between the two rotor rings, each ring's distance from the OTHER set's RX copper, and either ring
    reaching over the other set.  With the built stators the copper radii are measured; without them the layout
    formulas are used.  Returns a Report."""
    rep = Report()
    B = P.BOARD
    reach1 = inner2 = None
    rx1_out, rx2_in = layout.band1["ro"], layout.band2["ri"]
    if stator1 is not None and stator2 is not None:
        reach1, inner2 = copper_extent(stator1)[1], copper_extent(stator2)[0]
        rx1_out, rx2_in = rx_extent(stator1)[1], rx_extent(stator2)[0]
    need = float(B.ROTOR_TRACK_GAP_MM)
    gap = rotor2.r_in - rotor1.r_out
    custom = str(B.ROTOR_MODE).lower() == "custom"
    if gap < need - 1e-6:
        if custom:
            names = ("ROTOR_TRACK_GAP_MM", "ROTOR_CUSTOM_OUTER_RADIUS_MM", "ROTOR_CUSTOM_INNER_RADIUS_MM")
            fix = ("lower ROTOR_CUSTOM_OUTER_RADIUS_MM in Dual_Rotor1_Parameters.py or raise "
                   "ROTOR_CUSTOM_INNER_RADIUS_MM in Dual_Rotor2_Parameters.py")
        else:
            names = ("ROTOR_TRACK_GAP_MM", "ROTOR_AUTO_EXTENSION_OUTER_MM", "ROTOR_AUTO_EXTENSION_INNER_MM")
            fix = ("lower ROTOR_AUTO_EXTENSION_OUTER_MM in Dual_Rotor1_Parameters.py or "
                   "ROTOR_AUTO_EXTENSION_INNER_MM in Dual_Rotor2_Parameters.py (or widen the gap between the sets)")
        rep.conflict(names, f"the rotor rings are too close: ring 1 ends at r = {rotor1.r_out:.2f} mm and ring 2 starts "
                     f"at r = {rotor2.r_in:.2f} mm, {gap:.2f} mm apart, but ROTOR_TRACK_GAP_MM ({need:g} mm) must stay "
                     f"bare between them; {fix}")
    else:
        rep.info(f"gap between the rotor rings: ring 1 ends at r = {rotor1.r_out:.2f} mm, ring 2 starts at "
                 f"r = {rotor2.r_in:.2f} mm, {gap:.2f} mm bare (at least {need:g} needed)")
    r1 = layout.reach1 if reach1 is None else reach1
    i2 = layout.inner2 if inner2 is None else inner2
    # each ring's metal against the other set's RX band (the quantity ROTOR_TRACK_GAP_MM stands in for)
    custom_names = {1: ("ROTOR_CUSTOM_OUTER_RADIUS_MM",), 2: ("ROTOR_CUSTOM_INNER_RADIUS_MM",)}
    auto_names = {1: ("ROTOR_AUTO_EXTENSION_OUTER_MM",), 2: ("ROTOR_AUTO_EXTENSION_INNER_MM",)}
    d12 = rx2_in - rotor1.r_out
    need12 = float(B.ROTOR_1_TO_RX2_MM)
    if d12 < need12 - 1e-6:
        names = ("ROTOR_1_TO_RX2_MM",) + (custom_names[1] if custom else auto_names[1])
        rep.warn(f"ring 1 ends at r = {rotor1.r_out:.2f} mm and set 2's RX copper starts at r = {rx2_in:.2f} mm: "
                 f"{d12:.2f} mm apart, less than ROTOR_1_TO_RX2_MM ({need12:g} mm). The {rotor1.sectors}-sector coarse "
                 f"target so close to the fine RX band modulates the fine signal once per turn (a first-harmonic "
                 f"error that no fine-track calibration removes). Shorten ring 1 ({names[1]} in "
                 f"Dual_Rotor1_Parameters.py), widen TRACK_GAP_MM, or move the RX2 band out", names=names)
    else:
        rep.info(f"ring 1 ends {d12:.2f} mm inside set 2's RX copper (at least ROTOR_1_TO_RX2_MM = {need12:g} needed)")
    d21 = rotor2.r_in - rx1_out
    need21 = float(B.ROTOR_2_TO_RX1_MM)
    if d21 < need21 - 1e-6:
        names = ("ROTOR_2_TO_RX1_MM",) + (custom_names[2] if custom else auto_names[2])
        rep.warn(f"ring 2 starts at r = {rotor2.r_in:.2f} mm and set 1's RX copper ends at r = {rx1_out:.2f} mm: "
                 f"{d21:.2f} mm apart, less than ROTOR_2_TO_RX1_MM ({need21:g} mm). The fine target adds a ripple of "
                 f"{rotor2.sectors} per turn to the coarse signal. Shorten ring 2 ({names[1]} in "
                 f"Dual_Rotor2_Parameters.py), widen TRACK_GAP_MM, or move the RX1 band in", names=names)
    else:
        rep.info(f"ring 2 starts {d21:.2f} mm outside set 1's RX copper (at least ROTOR_2_TO_RX1_MM = {need21:g} needed)")
    if rotor1.r_out > i2 + 1e-6:
        rep.warn(f"ring 1 reaches r = {rotor1.r_out:.2f} mm, over set 2's copper (which starts at r = {i2:.2f} mm): "
                 f"the coarse target would modulate the fine set once per turn. Shorten ring 1's outer extension")
    elif rotor1.r_out > r1 + 1e-6:
        rep.warn(f"ring 1 reaches r = {rotor1.r_out:.2f} mm, past the TX1 ring (r = {r1:.2f} mm) into the gap between "
                 f"the sets. Shorten ring 1's outer extension")
    if rotor2.r_in < r1 - 1e-6:
        rep.warn(f"ring 2 starts at r = {rotor2.r_in:.2f} mm, over set 1's TX ring (which reaches r = {r1:.2f} mm): "
                 f"the fine target would modulate TX1 {rotor2.sectors} times per turn. Shorten ring 2's inner "
                 f"extension (ROTOR_AUTO_EXTENSION_INNER_MM in Dual_Rotor2_Parameters.py)")
    return rep
