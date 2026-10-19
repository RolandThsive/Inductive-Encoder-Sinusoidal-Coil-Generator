"""
Dual_TrackLayout.py  -  where the two coil sets sit: the RX band of each set, the bore and the outline, and the
gap between the sets, from the dual parameters, in one of FOUR MODES detected from what is set
(Dual_Board_Parameters.py, Dual_RX1 / RX2_Parameters.py):

    Mode 1   TRACK_GAP_MM + both edges set; both bands None  -> both bands fitted between the edges (BAND_SPLIT)
    Mode 2   both bands set; TRACK_GAP_MM and both edges None -> edges from the bands; the gap is measured
    Mode 3   one band + TRACK_GAP_MM set; the rest None        -> the other band placed across the gap, same RX_A_MM
    Mode 4   both bands + both edges set; TRACK_GAP_MM None    -> all as given; edges checked; the gap is measured

From the centre out:   bore | RX1 band | TX1 ring | gap | RX2 band | TX2 ring | outline

The radii between the bands come from the Single Generator's own rules, so that the sets it then builds land
exactly where this module put them:
    bore            = RX1 band start - INNER_EDGE_INSET_MM                     (BoardLayout.resolve)
    TX ring reach   = RX band end + TX_OFFSET_MM + TX_TURNS x TX_PITCH_MM + half a trace   (BoardLayout.tx_ring:
                      the series TX has no tail; its two ends sit one pitch outside the last turn)
    set 2 innermost copper = RX2 band start - max(half an RX trace, a via radius)  (the inner-tip vias)
    gap             = set 2 innermost copper - TX1 reach
    outline         = RX2 band end + outer_edge_room  (BoardLayout.outer_edge_room: OUTER_EDGE_OFFSET_MM, or the
                      TX2 reach + OUTER_EDGE_TAIL_MARGIN_MM, whichever is larger)
Dual_DesignChecks measures the same radii on the built copper afterwards.

resolve(P) returns a Layout (below) or raises ParameterConflict in the Single Generator's style (the names of the
settings to change, and what to change).  Nothing to edit here.
"""

import types

from Generator.Core import BoardLayout
from Generator.Core.Conflict import ParameterConflict

from Dual_Generator.Core import Dual_SetParameters as SP

MODE_TEXT = {
    1: "mode 1: TRACK_GAP_MM and both board edges set, both RX bands None - the bands are fitted between the edges",
    2: "mode 2: both RX bands set, TRACK_GAP_MM and both board edges None - the edges come from the bands",
    3: "mode 3: one RX band and TRACK_GAP_MM set, the other band and both edges None - the other band is placed "
       "across the gap",
    4: "mode 4: both RX bands and both board edges set, TRACK_GAP_MM None - everything as given",
}
MODE_LIST = ("the four modes are:\n"
             "  1: TRACK_GAP_MM + INNER_EDGE_RADIUS_MM + OUTER_EDGE_RADIUS_MM set, both RX bands None\n"
             "  2: both RX bands set, TRACK_GAP_MM and both edges None\n"
             "  3: one RX band + TRACK_GAP_MM set, the other band and both edges None\n"
             "  4: both RX bands + both edges set, TRACK_GAP_MM None")
RX_FILES = {1: "Dual_RX1_Parameters.py", 2: "Dual_RX2_Parameters.py"}
BOARD_FILE = "Dual_Board_Parameters.py"


class Layout(types.SimpleNamespace):
    """mode; band1, band2 (dict ri, ro, how = "radii" | "centre" | "placed", names = the single names to set);
    bore, outline (mm) and where each came from; gap_setting (TRACK_GAP_MM or None), gap_required, gap_expected
    (mm, from the formulas); reach1 (TX1 reach), inner2 (set 2 innermost copper); room1, margin2, outer_room2."""

    def set_band(self, k):
        """{single name: value} for set k's RX band (Dual_SetParameters.build)."""
        return dict((self.band1 if k == 1 else self.band2)["names"])

    def edges(self):
        return (self.bore, self.outline)

    def lines(self):
        """Text lines for the summary and the record."""
        f = lambda v: f"{v:.3f}".rstrip("0").rstrip(".")
        how = {"radii": "INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM as given", "centre": "RX_R_BASE_MM / RX_A_MM as given",
               "placed": "placed by the generator"}
        out = [f"layout: {MODE_TEXT[self.mode]}"]
        for k, b in ((1, self.band1), (2, self.band2)):
            a = (b["ro"] - b["ri"]) / 2.0
            out.append(f"  RX{k} band r = {f(b['ri'])} ... {f(b['ro'])} mm (RX_R_BASE_MM {f((b['ri'] + b['ro']) / 2)}, "
                       f"RX_A_MM {f(a)}): {how[b['how']]}")
        out.append(f"  bore r = {f(self.bore)} mm ({self.bore_from}), outline r = {f(self.outline)} mm ({self.outline_from})")
        out.append(f"  TX1 ring reaches r = {f(self.reach1)} mm; set 2 copper starts at r = {f(self.inner2)} mm: "
                   f"gap {f(self.gap_expected)} mm"
                   + (f" (TRACK_GAP_MM = {f(self.gap_setting)})" if self.gap_setting is not None
                      else f" (measured; at least MIN_CLEARANCE_MM = {f(self.gap_required)} needed)"))
        return out


def _num(name, val, file):
    if isinstance(val, bool) or not isinstance(val, (int, float)) or val <= 0:
        raise ParameterConflict((name,), f"{name} must be a number greater than 0, or None; it is {val!r} ({file})")
    return float(val)


def band_of(rx, k):
    """The RX band of set k as given in its file: None (all four None) or dict(ri, ro, how, names).  Raises
    ParameterConflict for a half pair or for both pairs."""
    file = RX_FILES[k]
    ins, out = getattr(rx, "INSIDE_RADIUS_MM", None), getattr(rx, "OUTSIDE_RADIUS_MM", None)
    rb, a = getattr(rx, "RX_R_BASE_MM", None), getattr(rx, "RX_A_MM", None)
    have_r, have_c = (ins is not None, out is not None), (rb is not None, a is not None)
    if any(have_r) and not all(have_r):
        missing = BoardLayout.RADII[have_r.index(False)]
        raise ParameterConflict(BoardLayout.RADII, f"the two RX band radii go together, but {missing} is None in {file}. "
                                f"Set both (the RX band), or both to None")
    if any(have_c) and not all(have_c):
        missing = BoardLayout.CENTRE[have_c.index(False)]
        raise ParameterConflict(BoardLayout.CENTRE, f"the band centre and its swing go together, but {missing} is None "
                                f"in {file}. Set both (the RX band is RX_R_BASE_MM - RX_A_MM ... RX_R_BASE_MM + "
                                f"RX_A_MM), or both to None")
    if all(have_r) and all(have_c):
        raise ParameterConflict(BoardLayout.RADII + BoardLayout.CENTRE, f"the RX{k} band is given twice in {file}: as "
                                f"two radii and as centre + swing. Set one pair to None")
    if all(have_r):
        ri, ro = _num("INSIDE_RADIUS_MM", ins, file), _num("OUTSIDE_RADIUS_MM", out, file)
        if ri >= ro:
            raise ParameterConflict(BoardLayout.RADII, f"the RX{k} band's inside radius ({ri:g} mm) must be smaller than "
                                    f"its outside radius ({ro:g} mm) ({file})")
        return dict(ri=ri, ro=ro, how="radii", names={"INSIDE_RADIUS_MM": ri, "OUTSIDE_RADIUS_MM": ro})
    if all(have_c):
        rb, a = _num("RX_R_BASE_MM", rb, file), _num("RX_A_MM", a, file)
        if rb - a <= 0:
            raise ParameterConflict(BoardLayout.CENTRE, f"the swing ({a:g} mm) must be smaller than the band centre "
                                    f"radius ({rb:g} mm): the RX{k} band would start at r = {rb - a:g} mm ({file})")
        return dict(ri=rb - a, ro=rb + a, how="centre", names={"RX_R_BASE_MM": rb, "RX_A_MM": a})
    return None


def _placed(ri, ro):
    return dict(ri=ri, ro=ro, how="placed", names={"RX_R_BASE_MM": round((ri + ro) / 2.0, 6),
                                                    "RX_A_MM": round((ro - ri) / 2.0, 6)})


def _tx_namespace(tx, board):
    """What the Single Generator's ring formulas read, for one set's TX with no tail and no fingers."""
    return types.SimpleNamespace(
        TX_TURNS=tx.TX_TURNS, TX_PITCH_MM=tx.TX_PITCH_MM, TX_TRACE_WIDTH_MM=tx.TX_TRACE_WIDTH_MM,
        TX_OFFSET_MM=tx.TX_OFFSET_MM, TX_SHAPE=SP.FIXED_REQUIRED["TX_SHAPE"][0], TX_TAIL_EXTRA_MM=0.0, RX_TABS="none",
        OUTER_EDGE_OFFSET_MM=board.OUTER_EDGE_OFFSET_MM, OUTER_EDGE_TAIL_MARGIN_MM=board.OUTER_EDGE_TAIL_MARGIN_MM)


def tx_room(tx, board):
    """How far a set's TX ring reaches past its RX band end (mm): the ends of the series TX one pitch outside the
    last turn, plus half a trace (BoardLayout.tx_ring with no tail)."""
    ring = BoardLayout.tx_ring(_tx_namespace(tx, board), 0.0)
    return max(ring["tail_end"] + float(tx.TX_TRACE_WIDTH_MM) / 2.0, ring["outer_copper_edge"])


def outer_room(tx, board, rotor=None):
    """From the RX2 band end to the outline (mm): the Single Generator's own rule (BoardLayout.outer_edge_room),
    and, when ring 2 of the rotor covers the TX2 turns (ROTOR_AUTO_COVER_TX, according_to_stator), also room for
    its overhang past the outermost turn plus ROTOR_AUTO_EDGE_CLEARANCE_MM and LAYOUT_TOLERANCE_MM (the disc has
    the stator's outline)."""
    room = BoardLayout.outer_edge_room(_tx_namespace(tx, board))
    if rotor is not None and str(getattr(board, "ROTOR_MODE", "")).lower() == "according_to_stator" \
            and bool(getattr(rotor, "ROTOR_AUTO_COVER_TX", False)):
        ring = BoardLayout.tx_ring(_tx_namespace(tx, board), 0.0)
        overhang = getattr(rotor, "ROTOR_AUTO_TX_OVERHANG_MM", 0.0) or 0.0
        clearance = getattr(board, "ROTOR_AUTO_EDGE_CLEARANCE_MM", 0.0) or 0.0
        tol = getattr(board, "LAYOUT_TOLERANCE_MM", 0.0) or 0.0
        try:
            room = max(room, ring["outer_copper_edge"] + float(overhang) + float(clearance) + float(tol))
        except (TypeError, ValueError):
            pass                                   # a bad value: the Single Generator's checks report it
    return room


def inner_margin(rx, board):
    """From the RX2 band start inwards to the set's innermost copper (mm): the inner-tip vias, or half a trace."""
    return max(float(rx.RX_TRACE_WIDTH_MM) / 2.0, float(board.VIA_DIAMETER_MM) / 2.0)


def resolve(P):
    """The Layout for these parameters, or ParameterConflict."""
    B = P.BOARD
    e_in, e_out = getattr(B, "INNER_EDGE_RADIUS_MM", None), getattr(B, "OUTER_EDGE_RADIUS_MM", None)
    gap = getattr(B, "TRACK_GAP_MM", None)
    if (e_in is None) != (e_out is None):
        unset = "INNER_EDGE_RADIUS_MM" if e_in is None else "OUTER_EDGE_RADIUS_MM"
        raise ParameterConflict(SP.EDGE_NAMES, f"the two board edges go together, but {unset} is None ({BOARD_FILE}). "
                                f"Set both (modes 1 and 4) or both to None (modes 2 and 3)")
    edges_set = e_in is not None
    if edges_set:
        e_in, e_out = _num("INNER_EDGE_RADIUS_MM", e_in, BOARD_FILE), _num("OUTER_EDGE_RADIUS_MM", e_out, BOARD_FILE)
        if e_in >= e_out:
            raise ParameterConflict(SP.EDGE_NAMES, f"the board's inner radius (the centre hole, {e_in:g} mm) cannot be "
                                    f"larger than its outer radius ({e_out:g} mm)")
    if gap is not None:
        gap = _num("TRACK_GAP_MM", gap, BOARD_FILE)
    b1, b2 = band_of(P.RX1, 1), band_of(P.RX2, 2)
    inset = float(B.INNER_EDGE_INSET_MM)
    clearance = float(B.MIN_CLEARANCE_MM)
    room1 = tx_room(P.TX1, B)                    # TX1 reach past the RX1 band end
    margin2 = inner_margin(P.RX2, B)             # set 2's copper inside its RX band start
    room2 = outer_room(P.TX2, B, P.ROTOR2)       # from the RX2 band end to the outline (ring 2's overhang included)
    names_all = ("TRACK_GAP_MM",) + SP.EDGE_NAMES + SP.BAND_NAMES

    # ---- the mode
    if b1 is None and b2 is None:
        if gap is None or not edges_set:
            missing = [n for n, v in (("TRACK_GAP_MM", gap), ("INNER_EDGE_RADIUS_MM", e_in),
                                      ("OUTER_EDGE_RADIUS_MM", e_out)) if v is None]
            raise ParameterConflict(names_all, f"no RX band is given (all four radii are None in Dual_RX1 and Dual_RX2), "
                                    f"so the bands have to be fitted between the board edges with TRACK_GAP_MM "
                                    f"(mode 1), but {' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} "
                                    f"None ({BOARD_FILE}). {MODE_LIST}")
        mode = 1
    elif b1 is not None and b2 is not None:
        if gap is not None:
            raise ParameterConflict(("TRACK_GAP_MM",) + SP.BAND_NAMES, f"both RX bands are given, so the gap between "
                                    f"the sets follows from them and is measured; set TRACK_GAP_MM to None "
                                    f"({BOARD_FILE}: mode 2 without edges, mode 4 with edges), or set one band to "
                                    f"None to have it placed TRACK_GAP_MM across (mode 3). {MODE_LIST}")
        mode = 4 if edges_set else 2
    else:
        given = 1 if b1 is not None else 2
        if gap is None:
            raise ParameterConflict(("TRACK_GAP_MM",) + SP.BAND_NAMES, f"only the RX{given} band is given, so the RX"
                                    f"{3 - given} band is placed across the gap (mode 3), but TRACK_GAP_MM is None "
                                    f"({BOARD_FILE}). Set it, or give both bands. {MODE_LIST}")
        if edges_set:
            raise ParameterConflict(SP.EDGE_NAMES + SP.BAND_NAMES, f"only the RX{given} band is given, so the RX"
                                    f"{3 - given} band is placed across TRACK_GAP_MM and the board edges follow from "
                                    f"the bands (mode 3); set INNER_EDGE_RADIUS_MM and OUTER_EDGE_RADIUS_MM to None "
                                    f"({BOARD_FILE}), or give both bands (mode 4). {MODE_LIST}")
        mode = 3

    # ---- the bands
    if mode == 1:
        fixed = inset + room1 + gap + margin2 + room2
        free = e_out - e_in - fixed
        split = float(B.BAND_SPLIT)
        if not 0.0 < split < 1.0:
            raise ParameterConflict(("BAND_SPLIT",), f"BAND_SPLIT must be between 0 and 1 (both excluded); it is "
                                    f"{split!r} ({BOARD_FILE})")
        if free <= 0.0:
            raise ParameterConflict(SP.EDGE_NAMES + ("TRACK_GAP_MM",), f"the board is too small for two RX bands: from "
                                    f"the bore ({e_in:g} mm) to the outline ({e_out:g} mm) there are {e_out - e_in:g} mm, "
                                    f"and {fixed:.2f} mm of that go to INNER_EDGE_INSET_MM ({inset:g}), the TX1 ring "
                                    f"({room1:.2f}), TRACK_GAP_MM ({gap:g}), the RX2 vias ({margin2:.2f}) and the TX2 "
                                    f"ring with the outer margin ({room2:.2f}). Raise OUTER_EDGE_RADIUS_MM above "
                                    f"{e_in + fixed:.2f} mm, lower the bore, or lower the TX turns, pitches, offsets "
                                    f"and margins")
        w1 = split * free
        ri1 = e_in + inset
        ro1 = ri1 + w1
        ri2 = ro1 + room1 + gap + margin2
        ro2 = e_out - room2
        b1, b2 = _placed(ri1, ro1), _placed(ri2, ro2)
        bore, outline, bore_from, outline_from = e_in, e_out, "INNER_EDGE_RADIUS_MM", "OUTER_EDGE_RADIUS_MM"
    elif mode == 3:
        if b1 is not None:
            a = (b1["ro"] - b1["ri"]) / 2.0
            ri2 = b1["ro"] + room1 + gap + margin2
            b2 = _placed(ri2, ri2 + 2.0 * a)
        else:
            a = (b2["ro"] - b2["ri"]) / 2.0
            ro1 = b2["ri"] - margin2 - gap - room1
            ri1 = ro1 - 2.0 * a
            if ri1 - inset <= 0.0:
                raise ParameterConflict(SP.BAND_NAMES + ("TRACK_GAP_MM",), f"the RX1 band placed inside the RX2 band "
                                        f"({b2['ri']:g} ... {b2['ro']:g} mm, same half width {a:g} mm) across "
                                        f"TRACK_GAP_MM ({gap:g}) and the TX1 ring ({room1:.2f} mm) would run from "
                                        f"r = {ri1:.2f} to {ro1:.2f} mm: the bore would have a zero or negative radius. "
                                        f"Move the RX2 band out, lower the gap, or give both bands")
            b1 = _placed(ri1, ro1)
    # modes 2, 3, 4: bore and outline from the bands, or as given (checked)
    if mode in (2, 3):
        bore = b1["ri"] - inset
        if bore <= 0.0:
            raise ParameterConflict(("INNER_EDGE_INSET_MM",) + tuple(b1["names"]), f"the inset ({inset:g} mm) is not "
                                    f"smaller than the RX1 band start ({b1['ri']:g} mm): the centre hole would have a "
                                    f"zero or negative radius. Lower INNER_EDGE_INSET_MM ({BOARD_FILE}) or move the RX1 "
                                    f"band out")
        outline = b2["ro"] + room2
        bore_from, outline_from = "RX1 band start - INNER_EDGE_INSET_MM", "RX2 band end + the TX2 ring and the margin"
    elif mode == 4:
        bore, outline, bore_from, outline_from = e_in, e_out, "INNER_EDGE_RADIUS_MM", "OUTER_EDGE_RADIUS_MM"
        # (the Single Generator checks each edge against its own set's band and reports what it needs)

    # ---- the gap between the sets
    reach1 = b1["ro"] + room1
    inner2 = b2["ri"] - margin2
    expected = inner2 - reach1
    required = gap if gap is not None else clearance
    if expected < required - 1e-9:
        if mode == 1:
            raise AssertionError("mode 1 placed the bands without the gap")      # (cannot happen: the bands are placed)
        need = b1["ro"] + room1 + required + margin2
        raise ParameterConflict(SP.BAND_NAMES, f"the two sets run into each other: the TX1 ring reaches r = {reach1:.2f} "
                                f"mm (RX1 band end {b1['ro']:g} + TX1 offset, turns and pitch) and set 2's copper starts "
                                f"at r = {inner2:.2f} mm (RX2 band start {b2['ri']:g} - its vias), {expected:.2f} mm "
                                f"apart; at least {required:g} mm must stay free. Move the RX2 band start to "
                                f"{need:.2f} mm or more, or the RX1 band in, or lower TX1's turns, pitch or offset")
    if b1["ro"] >= b2["ri"]:
        raise ParameterConflict(SP.BAND_NAMES, f"the RX1 band ({b1['ri']:g} ... {b1['ro']:g} mm) must lie inside the RX2 "
                                f"band ({b2['ri']:g} ... {b2['ro']:g} mm)")
    return Layout(mode=mode, band1=b1, band2=b2, bore=bore, outline=outline, bore_from=bore_from,
                  outline_from=outline_from, gap_setting=gap, gap_required=required, gap_expected=expected,
                  reach1=reach1, inner2=inner2, room1=room1, margin2=margin2, outer_room2=room2)
