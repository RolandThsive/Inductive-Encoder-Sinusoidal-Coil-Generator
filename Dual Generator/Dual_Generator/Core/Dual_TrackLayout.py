"""
Dual_TrackLayout.py  -  where the two coil sets sit: the RX band of each set, the bore and the outline, and the
gap between the sets, from the dual parameters, in one of FOUR MODES chosen with DUAL_MODE
(Dual_Board_Parameters.py; the bands in Dual_RX1 / RX2_Parameters.py):

    DUAL_MODE 1   TRACK_GAP_MM + both edges set; both bands None  -> both bands fitted between the edges (BAND_SPLIT)
    DUAL_MODE 2   both bands set; TRACK_GAP_MM and both edges None -> edges from the bands; the gap is measured
    DUAL_MODE 3   one band + TRACK_GAP_MM set; the rest None        -> the other band placed across the gap, same RX_A_MM
    DUAL_MODE 4   both bands + both edges set; TRACK_GAP_MM None    -> all as given; edges checked; the gap is measured

What is set is held against the chosen mode (needs(mode) below): every value the mode needs that is None, and
every value the mode wants None that is set, is reported by name, with the mode that matches what is set when
there is one.

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

import math
import types

from Generator.Core import BoardLayout
from Generator.Rotor import RotorBuilder as RB
from Generator.Core.Conflict import ParameterConflict

from Dual_Generator.Core import Dual_SetParameters as SP

MODE_TEXT = {
    1: "DUAL_MODE = 1: TRACK_GAP_MM and both board edges set, both RX bands None - the bands are fitted between the edges",
    2: "DUAL_MODE = 2: both RX bands set, TRACK_GAP_MM and both board edges None - the edges come from the bands",
    3: "DUAL_MODE = 3: one RX band and TRACK_GAP_MM set, the other band and both edges None - the other band is placed "
       "across the gap",
    4: "DUAL_MODE = 4: both RX bands and both board edges set, TRACK_GAP_MM None - everything as given",
}
MODE_LIST = ("the four modes (DUAL_MODE in Dual_Board_Parameters.py) are:\n"
             "  1: TRACK_GAP_MM + INNER_EDGE_RADIUS_MM + OUTER_EDGE_RADIUS_MM set, both RX bands None\n"
             "  2: both RX bands set, TRACK_GAP_MM and both edges None\n"
             "  3: one RX band + TRACK_GAP_MM set, the other band and both edges None\n"
             "  4: both RX bands + both edges set, TRACK_GAP_MM None")
# what each mode needs: (TRACK_GAP_MM set, both edges set, how many RX bands set)
MODE_NEEDS = {1: (True, True, 0), 2: (False, False, 2), 3: (True, False, 1), 4: (False, True, 2)}
MODE_SHORT = {1: "the bands fitted between the edges", 2: "the edges from the bands",
              3: "the other band placed across the gap", 4: "everything as given"}
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
    return dict(ri=ri, ro=ro, how="placed", names={"RX_R_BASE_MM": round((ri + ro) / 2.0, 9),
                                                    "RX_A_MM": round((ro - ri) / 2.0, 9)})


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


def _setting(module, name, default):
    """A rotor / board setting, the Single Generator's default when the line is missing or None."""
    v = getattr(module, name, None)
    return default if v is None else v


def ring_vertex_sag(board, rotor, rx, r):
    """How far the outermost polygon vertices of a rotor ring of radius r reach past r (mm): the ring's arcs are
    chords whose vertices sit on a slightly larger circle (RotorBuilder.sector_polygon).  With
    ROTOR_ARC_STEPS_PER_SECTOR = "auto" that is ROTOR_CHORD_TOLERANCE_MM; with a number of steps it follows from
    the chord angle."""
    steps = getattr(board, "ROTOR_ARC_STEPS_PER_SECTOR", "auto")
    if isinstance(steps, str) and steps.strip().lower() == "auto":
        return float(_setting(board, "ROTOR_CHORD_TOLERANCE_MM", 0.001))
    half = float(rotor.ROTOR_AUTO_DUTY) * 2.0 * math.pi / int(rx.LOOPS) / max(8, int(steps)) / 2.0
    return float(r) * (1.0 / math.cos(half) - 1.0)


def outer_room(tx, board, rotor=None, rx=None):
    """From the RX2 band end to the outline (mm): the Single Generator's own rule (BoardLayout.outer_edge_room),
    and, when ring 2 of the rotor covers the TX2 turns (ROTOR_AUTO_COVER_TX, according_to_stator), also room for
    its overhang past the outermost turn as RotorBuilder limits the ring: ROTOR_AUTO_EDGE_CLEARANCE_MM inside
    the outline, then LAYOUT_TOLERANCE_MM of slack or, when they need more, half the edge line plus the polygon
    vertices (ring_vertex_sag), which the ring also keeps inside the outline (the disc has the stator's
    outline).  The rotor settings default as in the Single Generator."""
    room = BoardLayout.outer_edge_room(_tx_namespace(tx, board))
    if rotor is not None and str(getattr(board, "ROTOR_MODE", "")).lower() == "according_to_stator" \
            and bool(_setting(rotor, "ROTOR_AUTO_COVER_TX", RB.DEFAULT_COVER_TX)):
        ring = BoardLayout.tx_ring(_tx_namespace(tx, board), 0.0)
        overhang = _setting(rotor, "ROTOR_AUTO_TX_OVERHANG_MM", RB.DEFAULT_TX_OVERHANG_MM)
        clearance = _setting(board, "ROTOR_AUTO_EDGE_CLEARANCE_MM", 0.0)
        edge_line = _setting(board, "EDGE_LINE_WIDTH_MM", 0.0)
        tol = _setting(board, "LAYOUT_TOLERANCE_MM", 0.0)
        try:
            edge = ring["outer_copper_edge"] + float(overhang)
            sag = ring_vertex_sag(board, rotor, rx, edge) if rx is not None else 0.0
            room = max(room, edge + float(clearance) + max(float(tol), float(edge_line) / 2.0 + sag))
        except (TypeError, ValueError):
            pass                                   # a bad value: the Single Generator's checks report it
    return room


def inner_margin(rx, board):
    """From the RX2 band start inwards to the set's innermost copper (mm): the inner-tip vias, or half a trace."""
    return max(float(rx.RX_TRACE_WIDTH_MM) / 2.0, float(board.VIA_DIAMETER_MM) / 2.0)


def mode_of(P):
    """DUAL_MODE as an int 1 ... 4, or ParameterConflict."""
    m = getattr(P.BOARD, "DUAL_MODE", None)
    if isinstance(m, bool) or not isinstance(m, (int, float)) or m not in (1, 2, 3, 4):
        raise ParameterConflict(("DUAL_MODE",), f"DUAL_MODE = {m!r} ({BOARD_FILE}): must be 1, 2, 3 or 4. {MODE_LIST}")
    return int(m)


def mode_matching(gap_set, edges_set, bands_set):
    """The mode whose needs are exactly what is set, or None."""
    for m, needs in MODE_NEEDS.items():
        if needs == (gap_set, edges_set, bands_set):
            return m
    return None


def check_mode(P, mode, gap, e_in, e_out, b1, b2):
    """What is set against what DUAL_MODE needs: ParameterConflict naming every value to set or to clear."""
    need_gap, need_edges, need_bands = MODE_NEEDS[mode]
    bands = (b1, b2)
    wrong, names = [], []
    if need_gap and gap is None:
        wrong.append(f"TRACK_GAP_MM is None ({BOARD_FILE}) but the mode needs it")
        names.append("TRACK_GAP_MM")
    if not need_gap and gap is not None:
        wrong.append(f"TRACK_GAP_MM = {gap!r} ({BOARD_FILE}) but the mode measures the gap: set it to None")
        names.append("TRACK_GAP_MM")
    for n, v in (("INNER_EDGE_RADIUS_MM", e_in), ("OUTER_EDGE_RADIUS_MM", e_out)):
        if need_edges and v is None:
            wrong.append(f"{n} is None ({BOARD_FILE}) but the mode needs both edges")
            names.append(n)
        if not need_edges and v is not None:
            wrong.append(f"{n} = {v!r} ({BOARD_FILE}) but the mode takes the edges from the bands: set it to None")
            names.append(n)
    n_set = sum(b is not None for b in bands)
    if n_set != need_bands:
        names += list(SP.BAND_NAMES)
        if need_bands == 1 and n_set == 0:
            wrong.append("no RX band is given (all four values None in Dual_RX1 and Dual_RX2) but the mode needs one "
                         "band: give INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM or RX_R_BASE_MM / RX_A_MM in one of them")
        elif need_bands == 1 and n_set == 2:
            wrong.append("both RX bands are given (Dual_RX1 and Dual_RX2) but the mode places the other band: set "
                         "one band's four values to None")
        else:
            for k, b in ((1, b1), (2, b2)):
                if b is None and need_bands == 2:
                    wrong.append(f"the RX{k} band is None ({RX_FILES[k]}: INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM or "
                                 f"RX_R_BASE_MM / RX_A_MM) but the mode needs both bands")
                if b is not None and need_bands == 0:
                    given = ", ".join(f"{n} = {v:g}" for n, v in b["names"].items())
                    wrong.append(f"the RX{k} band is given ({RX_FILES[k]}: {given}) but the mode places both bands: "
                                 f"set its four values to None")
    if not wrong:
        return
    edges = e_in is not None if (e_in is None) == (e_out is None) else None     # one edge alone matches no mode
    match = mode_matching(gap is not None, edges, n_set)
    hint = (f" What is set matches DUAL_MODE = {match} ({MODE_SHORT[match]}); choose that mode, or change the values."
            if match is not None and match != mode else " Change the values, or choose another DUAL_MODE.")
    raise ParameterConflict(("DUAL_MODE",) + tuple(dict.fromkeys(names)),
                            f"DUAL_MODE = {mode} ({MODE_SHORT[mode]}) does not match what is set: "
                            + "; ".join(wrong) + "." + hint + " " + MODE_LIST)


def resolve(P):
    """The Layout for these parameters, or ParameterConflict."""
    B = P.BOARD
    mode = mode_of(P)
    e_in, e_out = getattr(B, "INNER_EDGE_RADIUS_MM", None), getattr(B, "OUTER_EDGE_RADIUS_MM", None)
    gap = getattr(B, "TRACK_GAP_MM", None)
    b1, b2 = band_of(P.RX1, 1), band_of(P.RX2, 2)
    check_mode(P, mode, gap, e_in, e_out, b1, b2)
    edges_set = e_in is not None
    if edges_set:
        e_in, e_out = _num("INNER_EDGE_RADIUS_MM", e_in, BOARD_FILE), _num("OUTER_EDGE_RADIUS_MM", e_out, BOARD_FILE)
        if e_in >= e_out:
            raise ParameterConflict(SP.EDGE_NAMES, f"the board's inner radius (the centre hole, {e_in:g} mm) cannot be "
                                    f"larger than its outer radius ({e_out:g} mm)")
    if gap is not None:
        gap = _num("TRACK_GAP_MM", gap, BOARD_FILE)
    inset = float(B.INNER_EDGE_INSET_MM)
    clearance = float(B.MIN_CLEARANCE_MM)
    room1 = tx_room(P.TX1, B)                    # TX1 reach past the RX1 band end
    margin2 = inner_margin(P.RX2, B)             # set 2's copper inside its RX band start
    room2 = outer_room(P.TX2, B, P.ROTOR2, P.RX2)   # from the RX2 band end to the outline (ring 2's overhang included)

    # ---- the bands (the mode is DUAL_MODE, checked above against what is set)
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
            raise AssertionError("DUAL_MODE 1 placed the bands without the gap")  # (cannot happen: the bands are placed)
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
