"""
BandLayout.py  -  where the RX band and the board edges are, from the parameters (used by StatorGenerator.py and
ParameterChecker.py, so both apply the same rules).

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

RADII = ("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM")
CENTRE = ("RX_R_BASE_MM", "RX_A_MM")
EDGES = ("INNER_EDGE_RADIUS_MM", "OUTER_EDGE_RADIUS_MM")


def _number(name, val, positive=True):
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or (positive and val <= 0):
        raise ValueError(f"{name} must be a number greater than 0, or None; it is {val!r}")
    return float(val)


def resolve(get, room):
    """get(name) -> the parameter value (None when it is None or missing); room() -> the room outside the band for the
    TX turns, the TX tail, the fingers and the margins (mm; StatorGenerator.outer_edge_room), called only when needed.

    Returns dict(ri, ro, hole, outer_edge, mode, inner_from, outer_from):
      ri, ro       the RX band (mm)
      hole         the centre-hole radius (mm)
      outer_edge   OUTER_EDGE_RADIUS_MM, or None = calculated later from the finished stator (as before)
      mode         "radii" | "centre" | "board"
      inner_from / outer_from   "band" (the edge follows the band), "both" (both given) or "edge" (the band follows
                                the edge)
    Raises ValueError with a message that says what to change."""
    ins, out = get(RADII[0]), get(RADII[1])
    rb, a = get(CENTRE[0]), get(CENTRE[1])
    e_in, e_out = get(EDGES[0]), get(EDGES[1])
    inset = float(get("INNER_EDGE_INSET_MM"))
    have_r = (ins is not None, out is not None)
    have_c = (rb is not None, a is not None)
    if any(have_r) and not all(have_r):
        missing = RADII[have_r.index(False)]
        raise ValueError(f"INSIDE_RADIUS_MM and OUTSIDE_RADIUS_MM go together: {missing} is None. Set both (the RX "
                         f"band), or both to None (the band then comes from RX_R_BASE_MM / RX_A_MM or the board edges)")
    if any(have_c) and not all(have_c):
        missing = CENTRE[have_c.index(False)]
        raise ValueError(f"RX_R_BASE_MM and RX_A_MM go together: {missing} is None. Set both (the RX band is "
                         f"RX_R_BASE_MM - RX_A_MM ... RX_R_BASE_MM + RX_A_MM), or both to None")
    if all(have_r) and all(have_c):
        raise ValueError("the RX band is given twice: INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM and RX_R_BASE_MM / RX_A_MM "
                         "are all set. Set one pair to None (RX_Parameters.py)")
    if e_in is not None:
        e_in = _number(EDGES[0], e_in)
    if e_out is not None:
        e_out = _number(EDGES[1], e_out)

    if all(have_r):
        mode = "radii"
        ri, ro = _number(RADII[0], ins), _number(RADII[1], out)
        if ri >= ro:
            raise ValueError(f"INSIDE_RADIUS_MM ({ri:g}) must be smaller than OUTSIDE_RADIUS_MM ({ro:g})")
    elif all(have_c):
        mode = "centre"
        rb, a = _number(CENTRE[0], rb), _number(CENTRE[1], a)
        ri, ro = rb - a, rb + a
        if ri <= 0:
            raise ValueError(f"RX_A_MM ({a:g}) must be smaller than RX_R_BASE_MM ({rb:g}): the RX band would start at "
                             f"r = {ri:g} mm")
    else:
        mode = "board"
        if e_in is None or e_out is None:
            unset = " and ".join(n for n, e in zip(EDGES, (e_in, e_out)) if e is None)
            raise ValueError(f"the RX band is not given (INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM and RX_R_BASE_MM / "
                             f"RX_A_MM are all None), so it has to come from the board edges, but {unset} "
                             f"{'is' if ' and ' not in unset else 'are'} None. Set the RX band (RX_Parameters.py) or "
                             f"both board edges (Board_Parameters.py)")
        ri, ro = e_in + inset, round(e_out - float(room()), 9)
        if ri >= ro:
            raise ValueError(f"the board is too small for an RX band: from the board edges it would run from r = "
                             f"{ri:g} (INNER_EDGE_RADIUS_MM {e_in:g} + INNER_EDGE_INSET_MM {inset:g}) to r = {ro:g} "
                             f"(OUTER_EDGE_RADIUS_MM {e_out:g} - {e_out - ro:g} mm for the TX turns, the TX tail, the "
                             f"fingers and the margins). Enlarge the board, or lower INNER_EDGE_INSET_MM, TX_TURNS, "
                             f"TX_PITCH_MM, TX_TAIL_EXTRA_MM or OUTER_EDGE_OFFSET_MM")

    band_txt = {"radii": "INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM", "centre": "RX_R_BASE_MM / RX_A_MM"}.get(mode)
    # ---- inner side
    if e_in is None:
        hole, inner_from = ri - inset, "band"
        if hole <= 0:
            raise ValueError(f"INNER_EDGE_INSET_MM ({inset:g}) is not smaller than the RX band start ({ri:g} mm): the "
                             f"centre hole would have a zero or negative radius. Lower INNER_EDGE_INSET_MM "
                             f"(Board_Parameters.py) or move the RX band out")
    elif mode == "board":
        hole, inner_from = e_in, "edge"
    else:
        hole, inner_from = e_in, "both"
        if e_in > ri - inset + 1e-9:
            raise ValueError(f"INNER_EDGE_RADIUS_MM ({e_in:g}) does not leave INNER_EDGE_INSET_MM ({inset:g}) inside "
                             f"the RX band, which starts at r = {ri:g} mm ({band_txt}): the hole may be at most "
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
            raise ValueError(f"OUTER_EDGE_RADIUS_MM ({e_out:g}) is too small for the RX band ending at r = {ro:g} mm "
                             f"({band_txt}): the TX turns, the TX tail, the fingers and the margins need the edge at "
                             f"r = {need:g} mm or more. Set {band_txt} to None to fit the band to the board, raise "
                             f"OUTER_EDGE_RADIUS_MM, move the RX band in, or lower OUTER_EDGE_OFFSET_MM / "
                             f"OUTER_EDGE_TAIL_MARGIN_MM")
    return dict(ri=float(ri), ro=float(ro), hole=float(hole), outer_edge=outer_edge, mode=mode,
                inner_from=inner_from, outer_from=outer_from)


def describe(b):
    """One line for the summaries: how the band and the edges were set."""
    band = {"radii": "INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM", "centre": "RX_R_BASE_MM / RX_A_MM",
            "board": "the board edges"}[b["mode"]]
    edges = []
    for side, how in (("hole", b["inner_from"]), ("outer edge", b["outer_from"])):
        edges.append(f"{side} {'from the RX band' if how == 'band' else 'as given'}")
    return f"RX band from {band}; board {', '.join(edges)}"
