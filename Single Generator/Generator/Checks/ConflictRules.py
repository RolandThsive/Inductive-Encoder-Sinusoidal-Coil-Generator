"""
ConflictRules.py  -  the rules between TWO OR MORE parameters: settings that are each fine on their own but cannot
hold together (the RX band against the board edges, the TX pitch against the trace width and the clearance, the
fingers against the TX turns, the rotor against the stator ...).  A finding names the parameters and is printed as

    ERROR   NAME_A conflicts with NAME_B
            why, and what to change

check(P, v, rep) works on the checked values v (ParameterRules.load_values).  Rules about one parameter alone are
in ParameterRules.py; rules on the finished copper in DesignChecks.py.  Nothing to edit here.
"""

import math
import types

from Generator.Core import BoardLayout, Layers
from Generator.Checks.ParameterRules import SPEC, KICAD_EDGE_CLEARANCE_MM, _shape
from Generator.Stator.RX import RX_Coils, RX_Profiles
from Generator.Stator.TX import TX_Shapes

LAYER_NAME = Layers.LAYER_NAMES


def _rx_layers(v):
    if v.get("PCB_LAYERS") == 2:
        return {"F.Cu", "B.Cu"}
    if v.get("PCB_LAYERS") == 4 and "RX_LAYER_A" in v and "RX_LAYER_B" in v:
        return {LAYER_NAME[v["RX_LAYER_A"]], LAYER_NAME[v["RX_LAYER_B"]]}
    return None


_LAYOUT_NAMES = ("PCB_LAYERS", "RX_RISING_EDGE_LAYER", "RX_LAYER_A", "RX_LAYER_B", "RX_TABS", "RX_TAB_LAYER",
                 "TX_TURNS", "TX_OFFSET_MM", "TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "TX_SHAPE", "RX_TRACE_WIDTH_MM",
                 "VIA_DIAMETER_MM", "MIN_CLEARANCE_MM") + Layers.LAYER_SETTINGS


def _tx_layout(P, v, rep):
    """Layers.layer_plan on the checked values (None when a value it needs is missing or invalid; an impossible
    combination is reported as an error)."""
    if v.get("PCB_LAYERS") not in (2, 4) or v.get("RX_TABS") is None:
        return None
    if v["PCB_LAYERS"] == 2 and v.get("RX_RISING_EDGE_LAYER") is None:
        return None
    if v["PCB_LAYERS"] == 4 and (v.get("RX_LAYER_A") is None or v.get("RX_LAYER_B") is None):
        return None
    if v.get("TX_WIRING") is None:
        return None                                        # (TX_WIRING itself is missing or wrong: reported)
    d = {}
    for name in _LAYOUT_NAMES:
        if v.get(name) is not None:
            d[name] = v[name]
        elif hasattr(P, name) and name in Layers.LAYER_SETTINGS:
            # a TX layer setting that failed its own check (reported): leave the layout alone
            active = next((s[4] for s in SPEC if s[1] == name), None)
            if active is None or active(P):
                return None
    try:
        return Layers.layer_plan(types.SimpleNamespace(**d))
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        rep.add_exception(e)
        return None


class _Skip(Exception):
    """a value BoardLayout needs is missing or invalid (its own error is already reported)"""


def _outer_edge_room(v):
    """BoardLayout.outer_edge_room on checked values: how far inside a fixed OUTER_EDGE_RADIUS_MM the RX band
    ends.  None when a value it needs is missing or invalid (its own error is reported)."""
    need = ("OUTER_EDGE_OFFSET_MM", "OUTER_EDGE_TAIL_MARGIN_MM", "TX_OFFSET_MM", "TX_TURNS", "TX_PITCH_MM",
            "TX_TAIL_EXTRA_MM", "RX_TABS")
    if any(v.get(n) is None for n in need):
        return None
    margin = v["OUTER_EDGE_TAIL_MARGIN_MM"]
    room = max(v["OUTER_EDGE_OFFSET_MM"],
               v["TX_OFFSET_MM"] + v["TX_TURNS"] * v["TX_PITCH_MM"] + v["TX_TAIL_EXTRA_MM"] + margin)
    if str(v["RX_TABS"]).lower() in ("all", "single"):
        tab_need = ("RX_TAB_LENGTH_MM", "RX_TRACE_WIDTH_MM")
        if any(v.get(n) is None for n in tab_need):
            return None
        room = max(room, v["RX_TAB_LENGTH_MM"] + v["RX_TRACE_WIDTH_MM"] / 2.0 + margin)
    return float(room)


def _go_dims(v):
    """BoardLayout.goaround_dims on the checked values (None when one is missing)."""
    need = ("TX_TURNS", "TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "RX_TRACE_WIDTH_MM", "VIA_DIAMETER_MM", "MIN_CLEARANCE_MM",
            "TX_SHAPE", "TX_OFFSET_MM")
    if any(v.get(n) is None for n in need):
        return None
    return BoardLayout.goaround_dims(types.SimpleNamespace(**{n: v[n] for n in need}))


def _check_tx_layout(P, v, rep, has, lay):
    """TX_WIRING and its blocks, RX_TAB_LAYER."""
    if lay is None:
        return
    T = v.get("TX_TURNS")
    tab, mode = lay["tab_layer"], lay["mode"]
    tabs = v.get("RX_TABS") in ("all", "single")
    go = lay["goaround"]
    if mode == "single":
        base, tail = lay["base_layer"], lay["tail_layer"]
        if not (base == "B.Cu" and tail == "F.Cu") or lay["windows_on"]:
            rep.info(f"single-layer TX on {base}, the inner tail on {tail}"
                     + (f"; the turns go around every finger on {base} (go-around), with the brackets on "
                        f"{lay['bracket_layer']}" if go else (f"; the fingers cross it on {tab}" if tabs else "")))
    elif mode == "series":
        p, q = lay["layers"]
        rep.info(f"series TX on two layers: {T} turns on {p} + {T} turns on {q}, joined by a via at the inner end"
                 + (f"; the turns on {tab} go around every finger (go-around), with the brackets on "
                    f"{lay['bracket_layer']} outside its turns" if go else (f"; the fingers cross it on {tab}" if tabs else "")))
    else:
        rep.info(f"parallel TX: the same {T} turns on {lay['layers'][0]} and {lay['layers'][1]}, stitched together "
                 f"through vias around the TX terminal"
                 + ((f" and around every finger on {tab}" if lay["style"] == "stitched" else
                     f"; the turns on {tab} go around every finger (go-around), with the brackets on "
                     f"{lay['bracket_layer']} outside its turns") if lay["windows_on"] else ""))
        style = v.get("TX_PARALLEL_BREAK_STYLE")
        if style == "staggered" and not lay["windows_on"]:
            rep.info('TX_PARALLEL_BREAK_STYLE = "staggered" is not used: no finger crosses the TX on its own layer')
    # the stitching vias of a parallel TX: a turn next to a via has to bend away from its pad
    if mode == "parallel" and has("TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "VIA_DIAMETER_MM", "MIN_CLEARANCE_MM",
                                  "TX_TURNS") and v["TX_TURNS"] > 1:
        p, tw, vr, clr = v["TX_PITCH_MM"], v["TX_TRACE_WIDTH_MM"], v["VIA_DIAMETER_MM"] / 2.0, v["MIN_CLEARANCE_MM"]
        delta = max(0.0, vr + tw / 2.0 + clr + 0.03 - p)
        if p - tw - delta < clr - 1e-9:
            rep.conflict(("TX_PITCH_MM", "VIA_DIAMETER_MM", "TX_WIRING"), f"a pitch of {p:g} mm is too small for the "
                         f"stitching vias of the parallel TX (a turn next to a {2 * vr:g} mm via must bend {delta:.2f} mm "
                         f"away and would then touch the turn beyond it). Raise TX_PITCH_MM to at least "
                         f"{(vr + tw / 2.0 + clr + 0.03 + tw + clr) / 2.0:.2f} or use smaller vias")



def check(P, v, rep):
    """Every rule between two or more parameters, on the checked values `v` (ParameterRules.load_values); findings go
    to `rep`.  The values themselves are never changed."""
    has = lambda *names: all(n in v and v[n] is not None for n in names)
    lay = _tx_layout(P, v, rep)                     # TX layers and the finger layer (Layers.py)

    # the IC's oscillator range (IC_Parameters.py; the electrical estimate checks the TX tank against it)
    if has("IC_OSC_MIN_MHZ", "IC_OSC_MAX_MHZ") and v["IC_OSC_MIN_MHZ"] >= v["IC_OSC_MAX_MHZ"]:
        rep.conflict(("IC_OSC_MIN_MHZ", "IC_OSC_MAX_MHZ"), f"the IC's oscillator range "
                     f"{v['IC_OSC_MIN_MHZ']:g} ... {v['IC_OSC_MAX_MHZ']:g} MHz is empty: the minimum must "
                     f"be below the maximum")

    # the RX band and the board edges (BoardLayout.py): the band from INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM, from
    # RX_R_BASE_MM / RX_A_MM, or (both pairs None) from the board edges; an edge that is set is used as given
    inner_derived = outer_derived = False
    band = None
    band_names = BoardLayout.RADII + BoardLayout.CENTRE + BoardLayout.EDGES + ("INNER_EDGE_INSET_MM",)
    band_ok = all(n in v for n in band_names) and v.get("INNER_EDGE_INSET_MM") is not None
    if band_ok:
        def _room():
            r = _outer_edge_room(v)
            if r is None:
                raise _Skip()
            return r
        try:
            band = BoardLayout.resolve(lambda n: v.get(n), _room)
        except _Skip:
            band = None
        except ValueError as e:
            rep.add_exception(e)
            band = None
        for n in BoardLayout.RADII:
            v.pop(n, None)                              # every rule below sees the band actually used
        if band is not None:
            v["INSIDE_RADIUS_MM"], v["OUTSIDE_RADIUS_MM"] = band["ri"], band["ro"]
            inner_derived, outer_derived = band["inner_from"] == "edge", band["outer_from"] == "edge"
            if band["mode"] == "centre":
                rep.info(f"RX_R_BASE_MM = {v['RX_R_BASE_MM']:g}, RX_A_MM = {v['RX_A_MM']:g}: the RX band runs from "
                         f"r = {band['ri']:g} to {band['ro']:g} mm")
            if inner_derived:
                rep.info(f"INNER_EDGE_RADIUS_MM = {v['INNER_EDGE_RADIUS_MM']:g} sets the centre hole: the RX band starts "
                         f"INNER_EDGE_INSET_MM = {v['INNER_EDGE_INSET_MM']:g} outside it, at r = {band['ri']:g} mm")
            if outer_derived:
                rep.info(f"OUTER_EDGE_RADIUS_MM = {v['OUTER_EDGE_RADIUS_MM']:g} sets the outer board edge: the RX band "
                         f"ends {v['OUTER_EDGE_RADIUS_MM'] - band['ro']:g} mm inside it (room for the TX turns, the TX "
                         f"tail and the margins), at r = {band['ro']:g} mm")
            both = [n for n, how in (("INNER_EDGE_RADIUS_MM", band["inner_from"]),
                                     ("OUTER_EDGE_RADIUS_MM", band["outer_from"])) if how == "both"]
            if both:
                rep.info(f"the RX band and {' and '.join(both)} are all set: each is used as given (the board is "
                         f"not fitted to the band)")

    # ------------------------------------------------------------ RX geometry
    if has("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM"):
        ri, ro = v["INSIDE_RADIUS_MM"], v["OUTSIDE_RADIUS_MM"]
        if ri < ro:
            if has("VIA_DIAMETER_MM", "MIN_CLEARANCE_MM", "RX_TRACE_WIDTH_MM"):
                width = ro - ri
                band_names = ("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM", "VIA_DIAMETER_MM")
                if width < v["VIA_DIAMETER_MM"]:
                    rep.conflict(band_names, f"the RX band ({width:g} mm wide) is narrower than one via "
                                             f"({v['VIA_DIAMETER_MM']:g} mm): the outer and inner tip vias would overlap. "
                                             f"Widen the band or use smaller vias")
                elif width < v["VIA_DIAMETER_MM"] + v["MIN_CLEARANCE_MM"] + v["RX_TRACE_WIDTH_MM"]:
                    rep.conflict(band_names, f"the RX band ({width:g} mm wide) is very narrow for {v['VIA_DIAMETER_MM']:g} "
                                             f"mm vias: outer and inner tip vias of the same curve will be crowded",
                                 level="warning")
    if has("LOOPS", "INSIDE_RADIUS_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM") and v["LOOPS"] >= 1:
        # the curves of a coil run side by side near the inner radius: spacing there is about
        # circumference / (4 * loops) per quarter period; it should hold about three times (trace + clearance)
        quarter = 2 * math.pi * v["INSIDE_RADIUS_MM"] / (4 * v["LOOPS"])
        need = v["RX_TRACE_WIDTH_MM"] + v["MIN_CLEARANCE_MM"]
        if quarter < 3 * need:
            rep.conflict(("LOOPS", "INSIDE_RADIUS_MM"), f"at the inner radius a quarter of one loop is only {quarter:.2f} "
                         f"mm of arc for {v['LOOPS']} loops: the RX traces will be tightly packed (trace + clearance = "
                         f"{need:g} mm); check the clearance warnings printed while building", level="warning")

    if has("VIA_DIAMETER_MM", "VIA_DRILL_MM"):
        d, dr = v["VIA_DIAMETER_MM"], v["VIA_DRILL_MM"]
        if dr >= d:
            rep.conflict(("VIA_DRILL_MM", "VIA_DIAMETER_MM"), f"the drill ({dr:g} mm) must be smaller than the via "
                                                               f"diameter ({d:g} mm)")
        elif (d - dr) / 2 < 0.1:
            rep.conflict(("VIA_DRILL_MM", "VIA_DIAMETER_MM"), f"the via's annular ring is {(d - dr) / 2:.3f} mm; below "
                                                               f"about 0.1 mm many fabs cannot guarantee the pad around "
                                                               f"the drill", level="warning")

    # ------------------------------------------------------------ layers
    rx_l, tx_l = _rx_layers(v), (lay["turn_layers"] if lay else None)
    if v.get("PCB_LAYERS") == 4 and has("RX_LAYER_A", "RX_LAYER_B"):
        a, b = v["RX_LAYER_A"], v["RX_LAYER_B"]
        if a == b:
            rep.conflict(("RX_LAYER_A", "RX_LAYER_B"), f"the two RX layers must be different layers; both are "
                                                       f"{LAYER_NAME[a]} ({a})")
        elif {a, b} != {1, 2}:
            rep.conflict(("RX_LAYER_A", "RX_LAYER_B"), f"RX coils on {LAYER_NAME[a]} + {LAYER_NAME[b]}: in a standard "
                         f"4-layer stack-up Top + Inner 1 (1 and 2) are the closest pair; a larger spacing between the "
                         f"two coil layers weakens and distorts the signal", level="warning")
    _check_tx_layout(P, v, rep, has, lay)

    # ------------------------------------------------------------ RX sub-coils / profile
    n_sub = v.get("RX_SUBCOILS")
    n_sub = None if n_sub is None else int(n_sub)              # (2.0 is accepted as 2)
    if n_sub in (2, 3) and has("RX_SUBCOIL_SPLIT_ELEC_DEG"):
        sp = v["RX_SUBCOIL_SPLIT_ELEC_DEG"]
        # the receiver curves sit at (sub-coil offset + k * 90) electrical degrees: two of them on the same angle
        # are the same curve twice, and no layout exists (the generator would search for a long time and fail)
        even = 90.0 / n_sub                                         # the split that spaces all curves evenly
        offs = [(s - (n_sub - 1) / 2.0) * sp for s in range(n_sub)]
        angs = sorted((o + 90.0 * k) % 360.0 for o in offs for k in range(4))
        spacing = min((angs[(i + 1) % len(angs)] - angs[i]) % 360.0 for i in range(len(angs)))
        sub_names = ("RX_SUBCOILS", "RX_SUBCOIL_SPLIT_ELEC_DEG")
        if (n_sub - 1) * sp >= 180.0:
            rep.conflict(sub_names, f"the split ({sp:g} electrical degrees) is too large for {n_sub} sub-coils: "
                                    f"(RX_SUBCOILS - 1) x split must stay below 180")
        elif spacing < 1e-6:
            rep.conflict(sub_names, f"a split of {sp:g} with {n_sub} sub-coils puts two receiver curves on top of each "
                                    f"other (within a sub-coil the curves are 90 electrical degrees apart), so no "
                                    f"layout exists.\nUse {even:g}: it spaces all the curves evenly.")
        elif n_sub == 2 and not (35.0 <= sp <= 55.0):
            a = sp % 90.0
            rep.conflict(sub_names, f"with a split of {sp:g} the tip vias of the sin and cos coils end up {a:g} and "
                                    f"{90 - a:g} electrical degrees apart; far from 45 they crowd each other (about "
                                    f"35 ... 55 is workable)", level="warning")
        elif n_sub == 2 and has("RX_VIA_ELECTRICAL_DEG") and not (
                57.0 + sp / 2.0 <= v["RX_VIA_ELECTRICAL_DEG"] <= 123.0 - sp / 2.0):
            # the junction between the two sub-coils needs a stub that ends before the tip via of its lobe and keeps
            # clear of the other phases: it fits only for vias near the tip (measured: split 45 -> 80 ... 100,
            # split 36 -> 75 ... 105, with LOOPS = 1 and the default band)
            rep.conflict(("RX_VIA_ELECTRICAL_DEG", "RX_SUBCOIL_SPLIT_ELEC_DEG", "RX_SUBCOILS"),
                         f"with 2 sub-coils and a split of {sp:g} the via that joins the sub-coils only fits for "
                         f"RX_VIA_ELECTRICAL_DEG of about {57.0 + sp / 2.0:g} ... {123.0 - sp / 2.0:g} (it is "
                         f"{v['RX_VIA_ELECTRICAL_DEG']:g}); the generator will probably stop. Bring it closer to 90 or "
                         f"lower the split (a wider RX band does not help)", level="warning")
        elif n_sub == 3 and spacing < 0.8 * even:
            rep.conflict(sub_names, f"with a split of {sp:g} and 3 sub-coils some receiver curves are only "
                                    f"{spacing:.0f} electrical degrees apart, which crowds their vias; {even:g} spaces "
                                    f"them evenly", level="warning")
    if n_sub in (2, 3) and has("LOOPS", "INSIDE_RADIUS_MM", "VIA_DIAMETER_MM", "MIN_CLEARANCE_MM", "RX_TRACE_WIDTH_MM"):
        # the junction vias that join the sub-coils sit between neighbouring curves; near the inner radius every
        # curve has about circumference / (4 x loops x sub-coils) of arc, which must hold a via, a trace and two gaps
        per_curve = 2 * math.pi * v["INSIDE_RADIUS_MM"] / (4 * v["LOOPS"] * n_sub)
        need = 2 * (v["VIA_DIAMETER_MM"] + v["RX_TRACE_WIDTH_MM"] + 2 * v["MIN_CLEARANCE_MM"])   # (an empirical margin of 2)
        if per_curve < need:
            rep.conflict(("RX_SUBCOILS", "LOOPS", "INSIDE_RADIUS_MM", "VIA_DIAMETER_MM"),
                         f"near the inner radius every receiver curve has only {per_curve:.2f} mm of arc for {v['LOOPS']} "
                         f"loops x {n_sub} sub-coils (less than {need:g} mm, twice a via + a trace + two clearances): the "
                         f"junction vias between the sub-coils may not fit; the generator stops with a message if they do "
                         f"not. Fewer loops or sub-coils, a wider RX band or smaller vias give them room", level="warning")
        if n_sub == 3:
            rep.conflict(("RX_SUBCOILS", "VIA_DIAMETER_MM"), "3 sub-coils put 12 receiver curves into one loop: their tip "
                         "and junction vias are crowded, and only a wide RX band with small vias has been seen to pass "
                         "the clearance checks", level="warning")

    # ------------------------------------------------------------ RX resolution
    if has("STEPS_PER_LOOP", "LOOPS", "INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM", "RX_PROFILE") \
            and v["STEPS_PER_LOOP"] != "auto" and 0 < v["INSIDE_RADIUS_MM"] < v["OUTSIDE_RADIUS_MM"]:
        # the real chord error of the RX curves (the same measure RX_Coils.pick_steps uses): set mostly by the
        # radial swing of the curve, not by the circle it runs around
        probe = types.SimpleNamespace(P=types.SimpleNamespace(RX_PROFILE=v["RX_PROFILE"]), ri=v["INSIDE_RADIUS_MM"],
                                      ro=v["OUTSIDE_RADIUS_MM"], L=2.0 * math.pi / v["LOOPS"])
        RX_Profiles.radius_law(probe)
        sag = RX_Coils.chord_error(probe, int(v["STEPS_PER_LOOP"]))
        if sag > 0.01:
            rep.conflict(("STEPS_PER_LOOP", "LOOPS", "OUTSIDE_RADIUS_MM"), f"{v['STEPS_PER_LOOP']} chords per loop give "
                         f"about {sag:.3f} mm chord error on the RX curves for {v['LOOPS']} loops; use \"auto\" or a "
                         f"larger value", level="warning")

    # ------------------------------------------------------------ fingers
    if v.get("RX_TABS") in ("all", "single") and has("RX_TAB_WIDTH_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM"):
        gap = v["RX_TAB_WIDTH_MM"] - v["RX_TRACE_WIDTH_MM"]
        if gap < v["MIN_CLEARANCE_MM"]:
            rep.conflict(("RX_TAB_WIDTH_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM"), f"the two legs of a bridging finger "
                         f"are only {gap:.3f} mm apart (finger width - trace width); they need at least the clearance, "
                         f"{v['MIN_CLEARANCE_MM']:g} mm. Raise RX_TAB_WIDTH_MM")
    if (v.get("RX_TABS") in ("all", "single") and has("OUTSIDE_RADIUS_MM", "RX_TAB_LENGTH_MM", "TX_OFFSET_MM", "TX_PITCH_MM",
                                           "TX_TURNS", "TX_TRACE_WIDTH_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM")):
        ro = v["OUTSIDE_RADIUS_MM"]
        # the outermost TX copper (centre line): a spiral's last turn reaches one pitch farther out
        tx_outer = ro + v["TX_OFFSET_MM"] + (v["TX_TURNS"] if _shape(P) == "spiral" else v["TX_TURNS"] - 1) \
            * v["TX_PITCH_MM"]
        need = tx_outer + v["TX_TRACE_WIDTH_MM"] / 2 + v["RX_TRACE_WIDTH_MM"] / 2 + v["MIN_CLEARANCE_MM"] + 0.2
        if ro + v["RX_TAB_LENGTH_MM"] < need - 1e-9:
            rep.conflict(("RX_TAB_LENGTH_MM", "TX_OFFSET_MM", "TX_TURNS", "TX_PITCH_MM"), f"the fingers end at r = "
                         f"{ro + v['RX_TAB_LENGTH_MM']:.2f} mm, too close to the outermost TX copper (r = {tx_outer:g} mm): "
                         f"they must reach {need:.2f} mm (that copper, half a TX and half an RX trace, the clearance and "
                         f"0.2 mm). "
                         f"Set RX_TAB_LENGTH_MM to at least {need - ro:.2f}, or bring the TX in (TX_OFFSET_MM, TX_TURNS, "
                         f"TX_PITCH_MM)")
        elif lay is not None and lay["goaround"]:
            d = _go_dims(v)
            if d is not None and v["RX_TAB_LENGTH_MM"] < d["tip_off"] - 1e-9:
                rep.conflict(("RX_TAB_LENGTH_MM", "RX_TAB_LAYER", "TX_TURNS"), f"the TX goes around the fingers on "
                             f"{lay['tab_layer']}, so the fingers must run out past the outermost bracket, to the RX "
                             f"outside radius + {d['tip_off']:.2f} mm (RX_TAB_LENGTH_MM = {v['RX_TAB_LENGTH_MM']:g}). Set "
                             f"RX_TAB_LENGTH_MM to at least {d['tip_off']:.2f}, put the fingers on a layer without TX "
                             f"turns (RX_TAB_LAYER), or use fewer TX_TURNS")

    # ------------------------------------------------------------ TX
    if has("TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM"):
        gap = v["TX_PITCH_MM"] - v["TX_TRACE_WIDTH_MM"]
        # (also with one turn: the outer tail / step runs one pitch outside the turn, next to the terminal via)
        tx_names = ("TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM")
        if gap < v["MIN_CLEARANCE_MM"]:
            rep.conflict(tx_names, f"the TX turns (and the outer tail, one pitch outside the last turn) are only "
                                   f"{gap:.3f} mm apart (pitch - trace width); they need at "
                                   f"least the clearance, {v['MIN_CLEARANCE_MM']:g} mm. Raise TX_PITCH_MM")
        elif gap < v["MIN_CLEARANCE_MM"] + 0.02:
            rep.conflict(tx_names, f"the TX turns are {gap:.3f} mm apart, practically equal to the clearance "
                                   f"({v['MIN_CLEARANCE_MM']:g} mm): the polyline chords make the real gap a hair "
                                   f"smaller (a 0.4 mm pitch with 0.2 mm traces and 0.2 mm clearance was measured to "
                                   f"fail). Raise TX_PITCH_MM a little", level="warning")
    if has("OUTSIDE_RADIUS_MM", "TX_OFFSET_MM", "TX_TRACE_WIDTH_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM") \
            and rx_l and tx_l and (rx_l & tx_l):
        room = v["TX_OFFSET_MM"] - (v["RX_TRACE_WIDTH_MM"] + v["TX_TRACE_WIDTH_MM"]) / 2
        if room < v["MIN_CLEARANCE_MM"]:
            rep.conflict(("TX_OFFSET_MM", "MIN_CLEARANCE_MM"), f"the first TX turn is only {room:.3f} mm from the outer "
                         f"RX copper on the same layer ({', '.join(sorted(rx_l & tx_l))}); it needs the clearance, "
                         f"{v['MIN_CLEARANCE_MM']:g} mm. Raise TX_OFFSET_MM to at least "
                         f"{v['MIN_CLEARANCE_MM'] + (v['RX_TRACE_WIDTH_MM'] + v['TX_TRACE_WIDTH_MM']) / 2:.2f}")
    if has("TX_OFFSET_MM", "VIA_DIAMETER_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM") \
            and (_shape(P) == "arc" or has("TX_INSIDE_VIA_DISTANCE_MM")):
        # the TX terminal via against the RX band ("stepped_arc": the via sits on the first turn, no shift)
        arc = _shape(P) == "arc"
        dv = 0.0 if arc else v["TX_INSIDE_VIA_DISTANCE_MM"]
        room = v["TX_OFFSET_MM"] - v["VIA_DIAMETER_MM"] / 2 - v["RX_TRACE_WIDTH_MM"] / 2 - v["MIN_CLEARANCE_MM"]
        need_off = v["VIA_DIAMETER_MM"] / 2 + v["RX_TRACE_WIDTH_MM"] / 2 + v["MIN_CLEARANCE_MM"] + max(dv, 0.0)
        if arc and room < -1e-9:
            rep.conflict(("TX_OFFSET_MM", "VIA_DIAMETER_MM", "MIN_CLEARANCE_MM"), f"the TX terminal via of a stepped_arc "
                         f"TX sits on the first turn, within the clearance of the RX band (its outer tips reach the RX "
                         f"outside radius): raise TX_OFFSET_MM to at least {need_off:.2f}", level="warning")
        elif not arc and dv > room + 1e-9:
            if room >= 0:
                fix = f"at most {room:.2f} mm with these settings, or raise TX_OFFSET_MM to at least {need_off:.2f}"
            else:
                fix = f"raise TX_OFFSET_MM to at least {need_off:.2f}"
            rep.conflict(("TX_INSIDE_VIA_DISTANCE_MM", "TX_OFFSET_MM"), f"a via shift of {dv:g} mm puts the TX terminal via "
                         f"within the clearance of the RX band (its outer tips reach the RX outside radius): {fix}",
                         level="warning")
        elif not arc and dv < 0:
            rep.warn(f"TX_INSIDE_VIA_DISTANCE_MM = {dv:g} moves the TX terminal via outwards, onto the next TX turns; "
                     f"use 0 or a positive value")
    if _shape(P) == "arc" and has("TX_STEPPED_ARC_RADIUS_MM", "TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "VIA_DIAMETER_MM",
                                  "MIN_CLEARANCE_MM", "TX_TAIL_EXTRA_MM") and v["TX_STEPPED_ARC_RADIUS_MM"] != "auto":
        rho0 = v["TX_STEPPED_ARC_RADIUS_MM"]
        lim = TX_Shapes.arc_radius_limits(types.SimpleNamespace(**{n: v[n] for n in (
            "TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "VIA_DIAMETER_MM", "MIN_CLEARANCE_MM", "TX_TAIL_EXTRA_MM")}))
        if rho0 <= lim["corner"]:
            auto = max(lim["corner"], lim["via"]) + TX_Shapes.ARC_MARGIN_MM
            if has("OUTSIDE_RADIUS_MM", "TX_OFFSET_MM", "TX_TURNS"):
                # "auto" adds the chord sag of the outermost turn (TX_Shapes.arc_plan)
                r_top = v["OUTSIDE_RADIUS_MM"] + v["TX_OFFSET_MM"] + v["TX_TURNS"] * v["TX_PITCH_MM"]
                steps = v.get("TX_STEPS", "auto")
                if steps == "auto":
                    steps = TX_Shapes.points_per_turn(types.SimpleNamespace(
                        TX_STEPS="auto", TX_CHORD_TOLERANCE_MM=v.get("TX_CHORD_TOLERANCE_MM")),
                        r_top - v["TX_PITCH_MM"])
                auto += r_top * (1 - math.cos(math.pi / float(steps)))
                auto_txt = f"\"auto\" = {auto:.2f} mm"
            else:
                auto_txt = f"\"auto\" = at least {auto:.2f} mm"
            rep.conflict(("TX_STEPPED_ARC_RADIUS_MM", "TX_PITCH_MM"), f"the innermost arc radius ({rho0:g} mm) must be "
                         f"larger than the pitch ({lim['corner']:g} mm): the arcs are one pitch apart and each must reach "
                         f"the next turn ({auto_txt})")
        elif rho0 >= lim["top"]:
            rep.conflict(("TX_STEPPED_ARC_RADIUS_MM", "TX_PITCH_MM", "TX_TAIL_EXTRA_MM"), f"the innermost arc radius "
                         f"({rho0:g} mm) must be smaller than pitch + tail length ({lim['top']:g} mm): the last arc would "
                         f"reach past the end of the TX tail")
        elif rho0 < lim["via"]:
            rep.conflict(("TX_STEPPED_ARC_RADIUS_MM", "VIA_DIAMETER_MM", "MIN_CLEARANCE_MM"), f"an innermost arc radius of "
                         f"{rho0:g} mm brings the arc within the clearance of the TX terminal via (via radius + half a TX "
                         f"trace + clearance = {lim['via']:.2f} mm): all TX turns are one net, so KiCad's DRC will not "
                         f"flag it; closer than the clearance (a short if the gap reaches 0)", level="warning")
    if has("TX_STEPS", "OUTSIDE_RADIUS_MM", "TX_OFFSET_MM", "TX_TURNS", "TX_PITCH_MM") and v["TX_STEPS"] != "auto":
        # at the outermost turn, where the sag is largest (a spiral's last turn reaches one pitch farther out)
        r = v["OUTSIDE_RADIUS_MM"] + v["TX_OFFSET_MM"] + (v["TX_TURNS"] - 1 + (1 if _shape(P) == "spiral" else 0)) \
            * v["TX_PITCH_MM"]
        sag = r * (1 - math.cos(math.pi / v["TX_STEPS"]))
        if sag > 0.01:
            rep.conflict(("TX_STEPS", "OUTSIDE_RADIUS_MM"), f"{v['TX_STEPS']} points per turn give about {sag:.3f} mm chord "
                         f"error on the outermost TX turn (r = {r:.2f} mm); raise TX_STEPS", level="warning")

    # ------------------------------------------------------------ nets
    if has("RX_NET_PHASE_0_2", "RX_NET_PHASE_1_3", "TX_NET"):
        names = [v["RX_NET_PHASE_0_2"], v["RX_NET_PHASE_1_3"], v["TX_NET"]]
        if len(set(names)) != 3:
            rep.conflict(("RX_NET_PHASE_0_2", "RX_NET_PHASE_1_3", "TX_NET"), f"the three net names must all be different; "
                         f"they are {names[0]!r}, {names[1]!r} and {names[2]!r}")

    # ------------------------------------------------------------ board outline
    if (not outer_derived and has("OUTER_EDGE_RADIUS_MM", "OUTSIDE_RADIUS_MM")
            and v["OUTER_EDGE_RADIUS_MM"] <= v["OUTSIDE_RADIUS_MM"]):
        rep.conflict(("OUTER_EDGE_RADIUS_MM", "OUTSIDE_RADIUS_MM"), f"the outer board edge ({v['OUTER_EDGE_RADIUS_MM']:g} "
                     f"mm) lies inside the RX band, which ends at {v['OUTSIDE_RADIUS_MM']:g} mm")

    # ------------------------------------------------------------ output files
    if has("STATOR_FILE", "ROTOR_FILE"):
        if v["STATOR_FILE"] == v["ROTOR_FILE"]:
            rep.conflict(("STATOR_FILE", "ROTOR_FILE"), "both boards have the same file name: the rotor would overwrite "
                                                        "the stator")

    # ------------------------------------------------------------ rotor
    mode = v.get("ROTOR_MODE")
    duty = v.get("ROTOR_AUTO_DUTY") if mode == "according_to_stator" else v.get("ROTOR_CUSTOM_DUTY")
    if duty is not None:
        factor = math.sin(math.pi * duty)
        # a metal fraction k/h removes the h-th harmonic of the rotor pattern (sin(h*pi*duty) = 0)
        nulled = [h for h in (3, 5, 7) if abs(duty * h - round(duty * h)) < 0.005 * h]
        extra = f"; it removes harmonic {nulled[0]} of the rotor pattern" if nulled else ""
        if factor < 0.7:
            rep.warn(f"rotor metal fraction {duty:g}: the fundamental signal is only {100 * factor:.0f} % of the "
                     f"maximum (reached at 0.5){extra}")
        elif nulled:
            rep.info(f"rotor metal fraction {duty:g} removes harmonic {nulled[0]} of the rotor pattern; "
                     f"the fundamental signal is {100 * factor:.0f} % of the maximum (reached at 0.5)")
        elif factor < 0.9:
            rep.info(f"rotor metal fraction {duty:g}: the fundamental signal is {100 * factor:.0f} % of the "
                     f"maximum (reached at 0.5)")
    if mode == "according_to_stator":
        e_all = v.get("ROTOR_AUTO_EXTENSION_MM")
        e_in, e_out = v.get("ROTOR_AUTO_EXTENSION_INNER_MM"), v.get("ROTOR_AUTO_EXTENSION_OUTER_MM")
        cover = v.get("ROTOR_AUTO_COVER_TX") is not False
        # (with the TX covered ROTOR_AUTO_EXTENSION_OUTER_MM is not checked, so it is not in v: read the raw value)
        raw_out = getattr(P, "ROTOR_AUTO_EXTENSION_OUTER_MM", None)
        if cover:
            if raw_out is not None:
                rep.info("ROTOR_AUTO_COVER_TX = True: the outer edge of the rotor copper is set by "
                         "ROTOR_AUTO_TX_OVERHANG_MM (ROTOR_AUTO_EXTENSION_OUTER_MM is not used)")
            if e_all is not None and e_in is not None:
                rep.info("ROTOR_AUTO_EXTENSION_MM is not used: ROTOR_AUTO_EXTENSION_INNER_MM sets the inner edge and, "
                         "with ROTOR_AUTO_COVER_TX = True, ROTOR_AUTO_TX_OVERHANG_MM sets the outer edge")
        elif e_all is not None and e_in is not None and e_out is not None:
            rep.info("ROTOR_AUTO_EXTENSION_MM is not used: the inner and the outer edge each have their own value")
        over = v.get("ROTOR_AUTO_TX_OVERHANG_MM")
        if cover and over is not None and over < 0:
            rep.info(f"ROTOR_AUTO_TX_OVERHANG_MM = {over:g}: the rotor copper ends over the TX turns, {-over:g} mm "
                     f"inside the outer edge of the outermost one")
        if has("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM", "AIR_GAP_MM") and not cover:
            default = e_all if e_all is not None else v["AIR_GAP_MM"]
            w_in = default if e_in is None else e_in
            w_out = default if e_out is None else e_out
            band = v["OUTSIDE_RADIUS_MM"] - v["INSIDE_RADIUS_MM"]
            if band > 0 and band + w_in + w_out <= 0:        # (a band of no width is reported above)
                rep.conflict(("ROTOR_AUTO_EXTENSION_INNER_MM", "ROTOR_AUTO_EXTENSION_OUTER_MM", "INSIDE_RADIUS_MM",
                              "OUTSIDE_RADIUS_MM"),
                             f"the rotor copper would have no width: the RX band is {band:g} mm wide and the copper "
                             f"would reach {w_in:+g} mm (inner edge) and {w_out:+g} mm (outer edge) past it. Raise the "
                             f"extensions (or ROTOR_AUTO_EXTENSION_MM)")
    if mode == "custom":
        n = v.get("ROTOR_CUSTOM_SECTORS")
        if n is not None and has("LOOPS") and n != v["LOOPS"]:
            rep.conflict(("ROTOR_CUSTOM_SECTORS", "LOOPS"), f"the rotor has {n} sector(s) but the stator {v['LOOPS']} "
                         f"loop(s): the rotor needs one sector per loop, otherwise the sensor does not give a single "
                         f"clean sine period per sector", level="warning")
        ri_, ro_ = v.get("ROTOR_CUSTOM_INNER_RADIUS_MM"), v.get("ROTOR_CUSTOM_OUTER_RADIUS_MM")
        if ri_ is not None and ro_ is not None:
            if ri_ >= ro_:
                rep.conflict(("ROTOR_CUSTOM_INNER_RADIUS_MM", "ROTOR_CUSTOM_OUTER_RADIUS_MM"), f"the rotor copper's inner "
                             f"radius ({ri_:g} mm) must be smaller than its outer radius ({ro_:g} mm)")
            else:
                bore, outline = v.get("ROTOR_CUSTOM_BORE_RADIUS_MM"), v.get("ROTOR_CUSTOM_OUTLINE_RADIUS_MM")
                if bore is not None and bore >= ri_:
                    rep.conflict(("ROTOR_CUSTOM_BORE_RADIUS_MM", "ROTOR_CUSTOM_INNER_RADIUS_MM"), f"the rotor bore "
                                 f"({bore:g} mm) must be smaller than the inner copper radius ({ri_:g} mm)")
                if outline is not None and outline <= ro_:
                    rep.conflict(("ROTOR_CUSTOM_OUTLINE_RADIUS_MM", "ROTOR_CUSTOM_OUTER_RADIUS_MM"), f"the rotor outline "
                                 f"({outline:g} mm) must be larger than the outer copper radius ({ro_:g} mm)")
                # copper close to the board edge: KiCad's design-rule check flags it (measured to the edge line)
                if bore is not None and 0 < ri_ - bore < KICAD_EDGE_CLEARANCE_MM:
                    rep.conflict(("ROTOR_CUSTOM_INNER_RADIUS_MM", "ROTOR_CUSTOM_BORE_RADIUS_MM"), f"the rotor copper "
                                 f"starts only {ri_ - bore:.2f} mm outside the bore ({ri_:g} against {bore:g} mm): KiCad's "
                                 f"design-rule check asks for {KICAD_EDGE_CLEARANCE_MM:g} mm between copper and the board "
                                 f"edge by default. Raise the inner copper radius to {bore + KICAD_EDGE_CLEARANCE_MM:g} or "
                                 f"lower the bore", level="warning")
                # the outer polygon vertices sit at r / cos(half a chord) (RotorBuilder.sector_polygon); with "auto"
                # chords that is within ROTOR_CHORD_TOLERANCE_MM, with a fixed number it can be much farther out
                steps, ro_v = v.get("ROTOR_ARC_STEPS_PER_SECTOR"), ro_
                if isinstance(steps, (int, float)) and not isinstance(steps, bool) and steps > 0:
                    n_sec = v.get("ROTOR_CUSTOM_SECTORS") or 1
                    ro_v = ro_ / math.cos((duty or 0.5) * math.pi / n_sec / max(8, int(steps)))
                if outline is not None and ro_ < outline <= ro_v:
                    rep.conflict(("ROTOR_ARC_STEPS_PER_SECTOR", "ROTOR_CUSTOM_OUTER_RADIUS_MM",
                                  "ROTOR_CUSTOM_OUTLINE_RADIUS_MM"), f"with {steps} chords per arc the corners of the "
                                 f"rotor copper reach r = {ro_v:.3f} mm, past the rotor outline ({outline:g} mm): the "
                                 f"copper crosses the board edge. Raise ROTOR_ARC_STEPS_PER_SECTOR (or use \"auto\") or "
                                 f"lower the outer copper radius")
                elif outline is not None and 0 < outline - ro_v < KICAD_EDGE_CLEARANCE_MM:
                    corners = f" (the polygon corners, at r = {ro_v:.3f} mm)" if ro_v - ro_ > 0.0005 else ""
                    rep.conflict(("ROTOR_CUSTOM_OUTER_RADIUS_MM", "ROTOR_CUSTOM_OUTLINE_RADIUS_MM"), f"the rotor copper"
                                 f"{corners} ends only {outline - ro_v:.2f} mm inside the outline ({ro_:g} against "
                                 f"{outline:g} mm): KiCad's design-rule check asks for {KICAD_EDGE_CLEARANCE_MM:g} mm "
                                 f"between copper and the board edge by default. Lower the outer copper radius to "
                                 f"{(outline - KICAD_EDGE_CLEARANCE_MM) * ro_ / ro_v:.3f} or raise the outline",
                                 level="warning")
                if has("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM"):
                    if ri_ > v["INSIDE_RADIUS_MM"] or ro_ < v["OUTSIDE_RADIUS_MM"]:
                        rep.conflict(("ROTOR_CUSTOM_INNER_RADIUS_MM", "ROTOR_CUSTOM_OUTER_RADIUS_MM", "INSIDE_RADIUS_MM",
                                      "OUTSIDE_RADIUS_MM"),
                                     f"the rotor copper ({ri_:g} ... {ro_:g} mm) does not cover the whole RX band "
                                     f"({v['INSIDE_RADIUS_MM']:g} ... {v['OUTSIDE_RADIUS_MM']:g} mm): the signal drops and "
                                     f"distorts near the uncovered edge", level="warning")
                    if has("TX_OFFSET_MM", "TX_TRACE_WIDTH_MM"):
                        tx_in = v["OUTSIDE_RADIUS_MM"] + v["TX_OFFSET_MM"] - v["TX_TRACE_WIDTH_MM"] / 2
                        if ro_ > tx_in:
                            rep.info(f"the custom rotor copper reaches r = {ro_:g} mm, over the TX turns (first turn "
                                     f"at {tx_in:g} mm), as the automatic rotor does by default: more signal, and a "
                                     f"larger change of the TX inductance (see the electrical estimate)")
    e_mask = v.get("ROTOR_SOLDER_MASK_EXPANSION_MM")             # -1 = no mask opening
    if mode == "custom" and e_mask is not None and e_mask > 0 and has("ROTOR_CUSTOM_INNER_RADIUS_MM") \
            and e_mask >= v["ROTOR_CUSTOM_INNER_RADIUS_MM"]:
        rep.conflict(("ROTOR_SOLDER_MASK_EXPANSION_MM", "ROTOR_CUSTOM_INNER_RADIUS_MM"), f"the mask expansion ({e_mask:g} "
                     f"mm) must be smaller than the inner copper radius ({v['ROTOR_CUSTOM_INNER_RADIUS_MM']:g} mm): the "
                     f"mask opening would reach the rotor centre")
    if has("ROTOR_ARC_STEPS_PER_SECTOR", "OUTSIDE_RADIUS_MM") and v["ROTOR_ARC_STEPS_PER_SECTOR"] != "auto":
        n = (v.get("ROTOR_CUSTOM_SECTORS") if mode == "custom" else v.get("LOOPS")) or 1
        d = (duty or 0.5) * 2 * math.pi / n / v["ROTOR_ARC_STEPS_PER_SECTOR"]
        r = _rotor_outer_radius(P, v, mode)
        sag = r * (1 / math.cos(d / 2) - 1)              # the vertices sit outside r (RotorBuilder.sector_polygon)
        if sag > 0.05:
            rep.conflict(("ROTOR_ARC_STEPS_PER_SECTOR", "LOOPS" if mode != "custom" else "ROTOR_CUSTOM_SECTORS"),
                         f"{v['ROTOR_ARC_STEPS_PER_SECTOR']} chords per arc give about {sag:.3f} mm chord error on the "
                         f"rotor edge at this sector width; raise it", level="warning")


def _rotor_outer_radius(P, v, mode):
    """The outer radius of the rotor copper, as RotorBuilder.RotorDesign sets it (as far as the checked values tell)."""
    ro = v["OUTSIDE_RADIUS_MM"]
    if mode == "custom":
        return v.get("ROTOR_CUSTOM_OUTER_RADIUS_MM") or ro
    if mode != "according_to_stator" or any(v.get(n) is None for n in ("TX_OFFSET_MM", "TX_TURNS", "TX_PITCH_MM",
                                                                        "TX_TRACE_WIDTH_MM")):
        return ro
    tw = v["TX_TRACE_WIDTH_MM"]
    first = ro + v["TX_OFFSET_MM"]
    if v.get("ROTOR_AUTO_COVER_TX") is not False:
        spiral = _shape(P) == "spiral"
        tx_outer_edge = first + (v["TX_TURNS"] if spiral else v["TX_TURNS"] - 1) * v["TX_PITCH_MM"] + tw / 2
        over = v.get("ROTOR_AUTO_TX_OVERHANG_MM")
        r = tx_outer_edge + (0.5 if over is None else over)
        if v.get("OUTER_EDGE_RADIUS_MM") is not None and v.get("EDGE_LINE_WIDTH_MM") is not None \
                and v.get("ROTOR_AUTO_EDGE_CLEARANCE_MM") is not None:
            r = min(r, v["OUTER_EDGE_RADIUS_MM"] - v["EDGE_LINE_WIDTH_MM"] / 2 - v["ROTOR_AUTO_EDGE_CLEARANCE_MM"])
        return r
    e_all, e_out = v.get("ROTOR_AUTO_EXTENSION_MM"), v.get("ROTOR_AUTO_EXTENSION_OUTER_MM")
    ext = e_out if e_out is not None else (e_all if e_all is not None else v.get("AIR_GAP_MM", 0.0) or 0.0)
    r = ro + ext
    if v.get("ROTOR_AUTO_TX_CLEARANCE_MM") is not None:
        r = min(r, first - tw / 2 - v["ROTOR_AUTO_TX_CLEARANCE_MM"])
    return r
