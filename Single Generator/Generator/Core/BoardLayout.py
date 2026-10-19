"""
BoardLayout.py  -  the radii of the board, from the parameters: where the RX band is, where the board edges are,
where the TX turns run (tx_ring), the sizes of the TX go-around windows (goaround_dims) and the shape word of the
TX (tx_shape).  Used by the RX and TX builders, the stator assembly, the rotor and the checks, so all of them
apply the same rules.  Nothing to edit here.

The RX band (the radii the RX coils swing between) is given in exactly ONE of two ways, or not at all:

    RX radii        INSIDE_RADIUS_MM, OUTSIDE_RADIUS_MM = numbers      (RX_R_BASE_MM, RX_A_MM = None)
                    band = INSIDE_RADIUS_MM ... OUTSIDE_RADIUS_MM
    centre + swing  RX_R_BASE_MM, RX_A_MM = numbers                    (INSIDE_RADIUS_MM, OUTSIDE_RADIUS_MM = None)
                    band = RX_R_BASE_MM - RX_A_MM ... RX_R_BASE_MM + RX_A_MM
    not given       all four = None: the band comes from the board edges (both must then be set)

Each pair goes together (both numbers or both None), and only one pair may be set.

Then the board edges (INNER_EDGE_RADIUS_MM = centre hole, OUTER_EDGE_RADIUS_MM = outer edge), each on its own:

    edge None      calculated from the band: hole = band start - INNER_EDGE_INSET_MM; outer edge = band end +
                   the room for the TX turns, the TX tail, the fingers and the margins (outer_edge_room)
    edge set       band given: both are used exactly as given.  The edge must leave at least those same margins
                   (INNER_EDGE_INSET_MM inside the band; the TX room outside it) - lower INNER_EDGE_INSET_MM,
                   OUTER_EDGE_OFFSET_MM, OUTER_EDGE_TAIL_MARGIN_MM ... to allow a tighter board.  Extra space is
                   simply margin.
                   band not given: the band is calculated from the edge (the reverse of the rule above).
"""

import math

from Generator.Core.Conflict import ParameterConflict

RADII = ("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM")
CENTRE = ("RX_R_BASE_MM", "RX_A_MM")
EDGES = ("INNER_EDGE_RADIUS_MM", "OUTER_EDGE_RADIUS_MM")

# TX_SHAPE: the values it may take, and the shape each one gives
#   "stepped_diagonal" : concentric turns joined by straight (diagonal) steps
#   "stepped_arc"      : concentric turns joined by arcs centred on the TX terminal via
#   "spiral"           : one smooth Archimedean spiral
TX_SHAPE_VALUES = ("stepped_diagonal", "stepped_arc", "spiral")
_SHAPES = {"stepped_diagonal": "diagonal", "stepped_arc": "arc", "spiral": "spiral"}


def tx_shape(P):
    """'diagonal', 'arc' or 'spiral' for TX_SHAPE (any letter case).  Raises ValueError for anything else."""
    s = str(getattr(P, "TX_SHAPE", "stepped_diagonal")).strip().lower()
    if s not in _SHAPES:
        raise ValueError('TX_SHAPE must be "stepped_diagonal", "stepped_arc" or "spiral"')
    return _SHAPES[s]


def _number(name, val, positive=True):
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or (positive and val <= 0):
        raise ValueError(f"{name} must be a number greater than 0, or None; it is {val!r}")
    return float(val)


def resolve(get, room):
    """get(name) -> the parameter value (None when it is None or missing); room() -> the room outside the band for the
    TX turns, the TX tail, the fingers and the margins (mm; outer_edge_room), called only when needed.

    Returns dict(ri, ro, hole, outer_edge, mode, inner_from, outer_from):
      ri, ro       the RX band (mm)
      hole         the centre-hole radius (mm)
      outer_edge   OUTER_EDGE_RADIUS_MM, or None = calculated later from the finished stator (StatorAssembly.Stator:
                   the largest of the OUTER_EDGE_OFFSET_MM, tail and finger rules)
      mode         "radii" | "centre" | "board"
      inner_from / outer_from   "band" (the edge follows the band), "both" (both given) or "edge" (the band follows
                                the edge)
    Raises ParameterConflict (a ValueError that names the parameters) with a message that says what to change."""
    ins, out = get(RADII[0]), get(RADII[1])
    rb, a = get(CENTRE[0]), get(CENTRE[1])
    e_in, e_out = get(EDGES[0]), get(EDGES[1])
    inset = float(get("INNER_EDGE_INSET_MM"))
    have_r = (ins is not None, out is not None)
    have_c = (rb is not None, a is not None)
    if any(have_r) and not all(have_r):
        missing = RADII[have_r.index(False)]
        raise ParameterConflict(RADII, f"the two RX band radii go together, but {missing} is None. Set both (the RX "
                                f"band), or both to None (the band then comes from RX_R_BASE_MM / RX_A_MM or the board "
                                f"edges)")
    if any(have_c) and not all(have_c):
        missing = CENTRE[have_c.index(False)]
        raise ParameterConflict(CENTRE, f"the band centre and its swing go together, but {missing} is None. Set both (the "
                                f"RX band is RX_R_BASE_MM - RX_A_MM ... RX_R_BASE_MM + RX_A_MM), or both to None")
    if all(have_r) and all(have_c):
        raise ParameterConflict(RADII + CENTRE, "the RX band is given twice: as two radii and as centre + swing. Set one "
                                "pair to None (RX_Parameters.py)")
    if e_in is not None:
        e_in = _number(EDGES[0], e_in)
    if e_out is not None:
        e_out = _number(EDGES[1], e_out)
    if e_in is not None and e_out is not None and e_in >= e_out:
        raise ParameterConflict(EDGES, f"the board's inner radius (the centre hole, {e_in:g} mm) cannot be larger than its "
                                f"outer radius ({e_out:g} mm)")

    if all(have_r):
        mode = "radii"
        ri, ro = _number(RADII[0], ins), _number(RADII[1], out)
        if ri >= ro:
            raise ParameterConflict(RADII, f"the RX band's inside radius ({ri:g} mm) must be smaller than its outside "
                                    f"radius ({ro:g} mm)")
    elif all(have_c):
        mode = "centre"
        rb, a = _number(CENTRE[0], rb), _number(CENTRE[1], a)
        ri, ro = rb - a, rb + a
        if ri <= 0:
            raise ParameterConflict(CENTRE, f"the swing ({a:g} mm) must be smaller than the band centre radius ({rb:g} "
                                    f"mm): the RX band would start at r = {ri:g} mm")
    else:
        mode = "board"
        if e_in is None or e_out is None:
            unset = " and ".join(n for n, e in zip(EDGES, (e_in, e_out)) if e is None)
            raise ParameterConflict(RADII + CENTRE + EDGES, f"the RX band is not given (the radii and centre + swing are all "
                                    f"None), so it has to come from the board edges, but {unset} "
                                    f"{'is' if ' and ' not in unset else 'are'} None too. Set the RX band "
                                    f"(RX_Parameters.py) or both board edges (Board_Parameters.py)")
        ri, ro = e_in + inset, round(e_out - float(room()), 9)
        if ri >= ro:
            raise ParameterConflict(EDGES, f"the board is too small for an RX band: from the board edges it would run "
                                    f"from r = {ri:g} (inner edge {e_in:g} + INNER_EDGE_INSET_MM {inset:g}) to r = {ro:g} "
                                    f"(outer edge {e_out:g} - {e_out - ro:g} mm for the TX turns, the TX tail, the "
                                    f"fingers and the margins). Enlarge the board, or lower INNER_EDGE_INSET_MM, or "
                                    f"{_room_names(get)}")

    band_txt = {"radii": "INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM", "centre": "RX_R_BASE_MM / RX_A_MM"}.get(mode)
    # ---- inner side
    if e_in is None:
        hole, inner_from = ri - inset, "band"
        if hole <= 0:
            raise ParameterConflict(("INNER_EDGE_INSET_MM",) + (RADII if mode == "radii" else CENTRE),
                                    f"the inset ({inset:g} mm) is not smaller than the RX band start ({ri:g} mm): the "
                                    f"centre hole would have a zero or negative radius. Lower INNER_EDGE_INSET_MM "
                                    f"(Board_Parameters.py) or move the RX band out")
    elif mode == "board":
        hole, inner_from = e_in, "edge"
    else:
        hole, inner_from = e_in, "both"
        if e_in > ri - inset + 1e-9:
            raise ParameterConflict(("INNER_EDGE_RADIUS_MM",) + (RADII if mode == "radii" else CENTRE),
                                    f"the centre hole ({e_in:g} mm) does not leave INNER_EDGE_INSET_MM ({inset:g} mm) "
                                    f"inside the RX band, which starts at r = {ri:g} mm: the hole may be at most "
                                    f"{ri - inset:g} mm. Set {band_txt} to None to fit the band to the board, lower "
                                    f"INNER_EDGE_RADIUS_MM or INNER_EDGE_INSET_MM, or move the RX band out")
    # ---- outer side
    if e_out is None:
        outer_edge, outer_from = None, "band"
    elif mode == "board":
        outer_edge, outer_from = e_out, "edge"
    else:
        outer_edge, outer_from = e_out, "both"
        need = ro + float(room())
        if e_out < need - 1e-9:
            raise ParameterConflict(("OUTER_EDGE_RADIUS_MM",) + (RADII if mode == "radii" else CENTRE),
                                    f"the outer board edge ({e_out:g} mm) is too small for the RX band ending at r = "
                                    f"{ro:g} mm: the TX turns, the TX tail, the fingers and the margins need the edge "
                                    f"at r = {need:g} mm or more. Set {band_txt} to None to fit the band to the board, "
                                    f"raise OUTER_EDGE_RADIUS_MM, move the RX band in, or lower {_room_names(get)}")
    return dict(ri=float(ri), ro=float(ro), hole=float(hole), outer_edge=outer_edge, mode=mode,
                inner_from=inner_from, outer_from=outer_from)


def rx_band(P):
    """The RX band and the board edges from the parameters (resolve): dict(ri, ro, hole, outer_edge, mode,
    inner_from, outer_from).  Raises ValueError for settings that do not fit together."""
    def room():
        try:
            return outer_edge_room(P)
        except (TypeError, ValueError, AttributeError) as e:
            raise ValueError(f"the room for the TX turns and the TX tail outside the RX band cannot be worked out "
                             f"(a TX / RX tab / margin setting is not a number: {e})")
    return resolve(lambda n: getattr(P, n, None), room)


def tx_ring(P, ro):
    """The TX turn radii (mm) outside an RX band ending at `ro`: dict(radii [every complete turn], first, outer [the
    outermost complete turn], inner_edge [inner edge of the first turn's copper], tail_end [where the TX tail ends],
    outer_copper_edge [outer edge of the outermost copper: a spiral's last turn reaches one pitch farther out])."""
    T, pitch, tw = int(P.TX_TURNS), float(P.TX_PITCH_MM), float(P.TX_TRACE_WIDTH_MM)
    first = float(ro) + float(P.TX_OFFSET_MM)
    outer = first + (T - 1) * pitch
    edge = outer + (pitch if tx_shape(P) == "spiral" else 0.0) + tw / 2.0
    return dict(radii=[first + n * pitch for n in range(T)], first=first, outer=outer, inner_edge=first - tw / 2.0,
                tail_end=first + T * pitch + float(P.TX_TAIL_EXTRA_MM), outer_copper_edge=edge)


def goaround_dims(P):
    """Sizes of a go-around window (mm), relative to the RX outside radius where they are radii:
      g[n]      : distance of turn n's run-out (and via) from the centre line of the finger leg (n = 0 innermost)
      via_off   : radius of the via circle, minus the RX outside radius
      bracket_off[n] : radius of bracket n, minus the RX outside radius (bracket 0 runs at the via circle)
      reach     : how far the window reaches beyond the finger leg (with half a clearance)
      tip_off   : the radius the finger tips must reach, minus the RX outside radius."""
    T = int(P.TX_TURNS)
    pitch, tw, rw = float(P.TX_PITCH_MM), float(P.TX_TRACE_WIDTH_MM), float(P.RX_TRACE_WIDTH_MM)
    vr, clr = float(P.VIA_DIAMETER_MM) / 2.0, float(P.MIN_CLEARANCE_MM)
    spiral = tx_shape(P) == "spiral"
    r_out = float(P.TX_OFFSET_MM) + (T if spiral else T - 1) * pitch     # outermost TX copper (centre line)
    via_off = r_out + tw / 2.0 + clr + vr + 0.02
    first = vr + tw / 2.0 + clr + 0.02                 # bracket 1 must pass over the vias of bracket 0
    s = max(pitch, tw + clr + 0.02)
    bracket_off = [via_off] + [via_off + first + (n - 1) * s for n in range(1, T)]
    g0 = rw / 2.0 + max(vr, tw / 2.0) + clr + 0.05
    dg = max(2.0 * vr + clr, tw + clr) + 0.02
    g = [g0 + n * dg for n in range(T)]
    reach = g[-1] + vr + clr / 2.0 + 0.02
    tip_off = bracket_off[-1] + tw / 2.0 + rw / 2.0 + clr + 0.2
    return dict(T=T, g=g, dg=dg, g0=g0, via_off=via_off, bracket_off=bracket_off, reach=reach, tip_off=tip_off,
                vr=vr, tw=tw, clr=clr, s=s)


def _room_names(get):
    """The parameters of the term that decides outer_edge_room (the largest one), for the advice in a message."""
    every = ("OUTER_EDGE_OFFSET_MM, OUTER_EDGE_TAIL_MARGIN_MM, RX_TAB_LENGTH_MM, TX_OFFSET_MM, TX_TURNS, TX_PITCH_MM "
             "or TX_TAIL_EXTRA_MM")
    try:
        margin = float(get("OUTER_EDGE_TAIL_MARGIN_MM"))
        terms = [(float(get("OUTER_EDGE_OFFSET_MM")), "OUTER_EDGE_OFFSET_MM"),
                 (float(get("TX_OFFSET_MM")) + float(get("TX_TURNS")) * float(get("TX_PITCH_MM"))
                  + float(get("TX_TAIL_EXTRA_MM")) + margin,
                  "TX_OFFSET_MM, TX_TURNS, TX_PITCH_MM, TX_TAIL_EXTRA_MM or OUTER_EDGE_TAIL_MARGIN_MM (the TX tail)")]
        if str(get("RX_TABS")).lower() in ("all", "single"):
            terms.append((float(get("RX_TAB_LENGTH_MM")) + float(get("RX_TRACE_WIDTH_MM")) / 2.0 + margin,
                          "RX_TAB_LENGTH_MM or OUTER_EDGE_TAIL_MARGIN_MM (the fingers)"))
    except (TypeError, ValueError):
        return every
    return max(terms)[1]


def outer_edge_room(P):
    """Distance from the RX outside radius to the outer board edge that the automatic edge rule gives (mm).
    Every term of that rule is the RX outside radius plus a constant, so this does not depend on the radius:
        the larger of  OUTER_EDGE_OFFSET_MM,
                       the TX tail end + OUTER_EDGE_TAIL_MARGIN_MM,
                       the end of the RX bridging fingers (RX_TAB_LENGTH_MM) + half a trace + OUTER_EDGE_TAIL_MARGIN_MM
                       (RX_TABS = "all" or "single")."""
    margin = float(P.OUTER_EDGE_TAIL_MARGIN_MM)
    room = max(float(P.OUTER_EDGE_OFFSET_MM),
               P.TX_OFFSET_MM + P.TX_TURNS * P.TX_PITCH_MM + P.TX_TAIL_EXTRA_MM + margin)
    if str(P.RX_TABS).lower() in ("all", "single"):
        room = max(room, P.RX_TAB_LENGTH_MM + P.RX_TRACE_WIDTH_MM / 2.0 + margin)
    return float(room)
