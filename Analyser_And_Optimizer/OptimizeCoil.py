#!/usr/bin/env python3
"""
OptimizeCoil.py  -  OPTIONAL tool: looks for settings that make the sensor more accurate.

It is separate from the generator: RunCoilGenerator.py never calls it, and nothing here is
needed to make a board.  Run it when you want to know whether other settings would be better.
It never changes your parameter files - it prints the lines to change.

    python OptimizeCoil.py                     search, starting from the current parameter files

There are no command-line options.  Everything it does is set in OptimizerParameters.py (Parameters folder):
what is searched, the tolerances, the model, the number of worker processes and the RX base / amplitude finder.

What it searches (everything else stays as in your parameter files)
    RX_PROFILE                  equal_area | cosine_r | field_compensated
    RX_SUBCOILS and the split   1 sub-coil, or 2 sub-coils split by 36 ... 60 electrical degrees
    ROTOR_AUTO_DUTY             rotor metal fraction 0.25 ... 0.50
    outer edge of the rotor     where the rotor copper ends on the outside.  With the eddy-current rotor
                                model (the default, ROTOR_MODEL = "eddy") it is searched from 0.2 mm inside
                                the outer radius of the RX band, over the TX turns, out to the board
                                outline (ROTOR_AUTO_EDGE_CLEARANCE_MM), in 0.5 mm steps, and reported as
                                ROTOR_AUTO_COVER_TX = True with ROTOR_AUTO_TX_OVERHANG_MM (mm past the
                                outer edge of the outermost TX turn; negative = it ends over the TX turns).
                                With ROTOR_MODEL = "screen" (the older, idealised model, which cannot judge
                                copper over the TX) it is ROTOR_AUTO_EXTENSION_OUTER_MM, -0.2 ... +0.5 mm
                                past the RX band, inside the TX ring.
                                It is searched together with the metal fraction, because the best value
                                of one depends on the other.  (SEARCH_ROTOR_OUTER_EDGE = False leaves it as it is.)
    RX_R_BASE_MM / RX_A_MM      only when the RX band is not given (INSIDE_RADIUS_MM, OUTSIDE_RADIUS_MM, RX_R_BASE_MM and
                                RX_A_MM all None), both board edges are set and RX_BASE_AND_AMPLITUDE_FINDER = True:
                                everything above is optimized first, with the widest band the board and your TX
                                coil leave.  Then, for the best BAND_BOARDS boards and for your current layout, the
                                band is narrowed and moved (BAND_WIDTH_LIMIT_PERCENT, BAND_STEP_PERCENT) to find the
                                best RX_R_BASE_MM and RX_A_MM, keeping your TX coil (it moves with the band).
    TX_START_ANGLE_DEG          switched to "auto" automatically when a layout needs it
    RX_TABS                     only with COMPARE_FINGERS = True in OptimizerParameters.py: every layout
                                with fingers at every tip ("all"), one finger per coil ("single") and
                                none ("none"); the best of each is checked over the full window and
                                they are compared (about three times the run time).
                                Otherwise RX_TABS stays as in RX_Parameters.py.
  Not searched: loops, radii, air gap, TX turns - those are your design constraints - and the inner
  edge of the rotor copper (it matters little).

How candidates are judged
  * The model of AnalyzeCoil.py (read its notes: it is not checked against hardware).
  * Score = the worst peak angle error (after offset / gain / quadrature calibration, electrical
    degrees) over the tolerance window: air gap +/- GAP_TOLERANCE_MM and rotor metal fraction
    +/- ROTOR_DUTY_TOLERANCE for every candidate, plus rotor eccentricity and tilt, all together
    in the worst direction (AnalyzeCoil.py), for the finalists.  Lower is better.  The window
    includes the metal fraction tolerance, so the optimum it picks is not a knife edge.
  * The metal fraction and the outer edge of the rotor are chosen so that the result stays good
    when either is off by its tolerance (ROTOR_DUTY_TOLERANCE, OUTER_TOLERANCE_MM: etching and
    registration), not only at the exact value.
  * A candidate whose signal is below MIN_SIGNAL x the signal of your current design is not
    allowed (less signal means more noise in a real sensor).
  * A candidate that the generator warns about (for example a via closer to copper than
    MIN_CLEARANCE_MM) is shown but is not recommended unless ALLOW_WARNINGS = True.
  * Differences below about 20 % are ties: the model is a ranking tool, not a measurement.  Among
    ties the outer edge of the rotor with the most signal is taken (eddy model; the screen model takes
    the one closest to the outer radius of the RX band), and in the ranking the candidate with the smaller air gap / metal fraction part comes first.  The best
    layout with one sub-coil is always shown, to compare with.
  * Every candidate also gets the electrical estimate of CoilElectrics.py: the receiver voltage in mVpp
    (screening and ranking), and the receiver voltage and oscillator frequency over the whole tolerance
    window (finalists), checked against RECEIVER_IC.  A candidate that breaks a limit of the IC which
    your current design keeps is not recommended.

Run time: the eddy-current model solves the currents in the rotor copper, so a search takes several
minutes (about 40 s per layout for the first stage, about 30 s per finalist); ROTOR_MODEL = "screen" is
much faster but does not see what copper over the TX turns does.

Settings: OptimizerParameters.py (a missing file or a missing line means the value in DEFAULTS below).

Needs Python 3 and numpy.  Runs from any folder (project layout: README.txt in the project folder).
"""

import concurrent.futures as cf
from concurrent.futures.process import BrokenProcessPool
import math
import multiprocessing as mp
import os
import sys
import time
import traceback
import types

import numpy as np

# The project folders sit next to each other: Parameters, Generator, Analyser_And_Optimizer (and Output).
# Put all three on the import path, so every program runs from any folder.  (All files in one folder works too.)
_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ("Analyser_And_Optimizer", "Generator", "Parameters"):
    _p = os.path.join(_PROJECT, _sub)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import AnalyzeCoil as AC                                  # noqa: E402
import CoilElectrics as CE                                # noqa: E402
import RotorGenerator as RG                               # noqa: E402
from ParameterChecker import Colour                       # noqa: E402

# =============================================================================
# DEFAULTS  (used when OptimizerParameters.py or one of its lines is missing; the settings you change are there)
# =============================================================================
PROFILES            = ("equal_area", "cosine_r", "field_compensated")
SUBCOIL_COUNTS      = (1, 2)                       # 3 is possible but crowded
SUBCOIL_SPLITS_DEG  = (36.0, 40.0, 45.0, 50.0, 55.0, 60.0)
DUTY_RANGE          = (0.25, 0.50)                 # rotor metal fraction searched
DUTY_STEP           = 0.005
OUTER_RANGE_MM      = (-0.2, 0.5)                  # rotor outer edge searched: mm past the RX band's outer radius
OUTER_STEP_MM       = 0.05
OUTER_TOLERANCE_MM  = 0.05                         # the chosen outer edge must stay good within +/- this (0 = skip)
                                                   # (screen model; the eddy model is smooth in the outer edge)
# with the eddy-current rotor model (the default) the outer edge runs from the RX band to the board outline,
# over the TX turns, on a coarser grid that is refined around the best point
EDDY_OUTER_STEP_MM  = 0.5
EDDY_DUTY_STEP      = 0.025                        # coarse metal-fraction grid, refined to DUTY_STEP
MIN_SIGNAL          = 0.8                          # x the signal of the current design
FINALISTS           = 6                            # candidates re-checked with eccentricity and tilt
DIRECTIONS          = AC.ECC_DIRECTIONS            # eccentricity directions tried (all tilt directions are always tried)
JOBS                = 0                            # worker processes, 0 = automatic (at most 4)
TIE_FRACTION        = 0.20                         # differences below this are ties
# RX base and amplitude finder
BAND_FINDER         = True
BAND_LIMIT_PERCENT  = 70.0                         # narrowest band tried, % of the widest
BAND_STEP_PERCENT   = 10.0                         # step of the search, %
BAND_BOARDS         = 3                            # best boards (besides the current layout) that get the finder
BAND_COARSE_MAX     = 40                           # at most this many bands in the first (coarse) round per board


# =============================================================================
# building candidates (also runs inside the worker processes)
# =============================================================================
def _overlay(base_over, cand_over):
    import Parameters as P0
    over = dict(base_over)
    over.update(cand_over)
    return AC.Overlay(P0, **over) if over else P0


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def load_optimizer_parameters():
    """OptimizerParameters.py: (settings dict, None) or (None, error text).  A missing file or a missing line
    means the default (DEFAULTS above)."""
    out = dict(COMPARE_FINGERS=False, PROFILES=PROFILES, SUBCOIL_COUNTS=SUBCOIL_COUNTS,
               SUBCOIL_SPLITS_DEG=SUBCOIL_SPLITS_DEG, DUTY_RANGE=DUTY_RANGE, SEARCH_ROTOR_OUTER_EDGE=True,
               OUTER_RANGE_MM=OUTER_RANGE_MM, GAP_TOLERANCE_MM=AC.GAP_TOLERANCE_MM,
               DUTY_TOLERANCE=AC.ROTOR_DUTY_TOLERANCE, OUTER_TOLERANCE_MM=OUTER_TOLERANCE_MM,
               ECCENTRICITY_MM=AC.ECCENTRICITY_MM, TILT_DEG=AC.TILT_DEG, ECC_DIRECTIONS=DIRECTIONS,
               MIN_SIGNAL=MIN_SIGNAL, ALLOW_WARNINGS=False, FINALISTS=FINALISTS, ROTOR_MODEL=AC.ROTOR_MODEL,
               TRUE_3D_GEOMETRY=AC.TRUE_3D_GEOMETRY, SCREEN_SHARP_EDGES=False, JOBS=JOBS,
               RX_BASE_AND_AMPLITUDE_FINDER=BAND_FINDER, BAND_WIDTH_LIMIT_PERCENT=BAND_LIMIT_PERCENT,
               BAND_STEP_PERCENT=BAND_STEP_PERCENT, BAND_BOARDS=BAND_BOARDS)
    try:
        import OptimizerParameters as OP
    except ModuleNotFoundError as e:
        if getattr(e, "name", None) == "OptimizerParameters":
            return out, None
        return None, f"OptimizerParameters.py cannot be loaded: {type(e).__name__}: {e}"
    except Exception as e:                                  # syntax error ...
        return None, f"OptimizerParameters.py cannot be loaded: {type(e).__name__}: {e}"
    unknown = [n for n in dir(OP) if n.isupper() and n not in out]
    if unknown:
        return None, (f"OptimizerParameters.py: {', '.join(unknown)} is not an optimizer setting "
                      f"(check the spelling; the settings are listed in that file)")
    for name in out:
        if hasattr(OP, name):
            out[name] = getattr(OP, name)

    def bad(name, what):
        return None, f"{name} in OptimizerParameters.py must be {what}; it is {out[name]!r}"

    for name in ("COMPARE_FINGERS", "SEARCH_ROTOR_OUTER_EDGE", "ALLOW_WARNINGS", "TRUE_3D_GEOMETRY",
                 "SCREEN_SHARP_EDGES", "RX_BASE_AND_AMPLITUDE_FINDER"):
        if not isinstance(out[name], bool):
            return bad(name, "True or False")
    seq = lambda v: isinstance(v, (tuple, list))
    if not seq(out["PROFILES"]) or not out["PROFILES"] or any(p not in PROFILES for p in out["PROFILES"]):
        return bad("PROFILES", 'a list of "equal_area", "cosine_r", "field_compensated"')
    if not seq(out["SUBCOIL_COUNTS"]) or not out["SUBCOIL_COUNTS"] or any(
            not _is_int(n) or n not in (1, 2, 3) for n in out["SUBCOIL_COUNTS"]):
        return bad("SUBCOIL_COUNTS", "a list of 1, 2 and/or 3")
    if not seq(out["SUBCOIL_SPLITS_DEG"]) or any(not _is_num(v) or v <= 0 for v in out["SUBCOIL_SPLITS_DEG"]) or (
            not out["SUBCOIL_SPLITS_DEG"] and any(n > 1 for n in out["SUBCOIL_COUNTS"])):
        return bad("SUBCOIL_SPLITS_DEG", "a list of numbers above 0 (electrical degrees)")
    d = out["DUTY_RANGE"]
    if not seq(d) or len(d) != 2 or not all(_is_num(v) for v in d) or not 0.0 < d[0] < d[1] < 1.0:
        return bad("DUTY_RANGE", "two numbers 0 < lowest < highest < 1, for example (0.25, 0.5)")
    o = out["OUTER_RANGE_MM"]
    if not seq(o) or len(o) != 2 or not all(_is_num(v) for v in o) or o[0] > o[1]:
        return bad("OUTER_RANGE_MM", "two numbers lowest <= highest, for example (-0.2, 0.5)")
    for name in ("GAP_TOLERANCE_MM", "DUTY_TOLERANCE", "OUTER_TOLERANCE_MM", "ECCENTRICITY_MM", "TILT_DEG"):
        if not _is_num(out[name]) or out[name] < 0:
            return bad(name, "a number, 0 or more")
    if not _is_num(out["MIN_SIGNAL"]) or not 0.0 < out["MIN_SIGNAL"] <= 1.5:
        return bad("MIN_SIGNAL", "a fraction of the current signal above 0, at most 1.5, for example 0.8")
    for name, lo in (("ECC_DIRECTIONS", 1), ("FINALISTS", 1), ("JOBS", 0), ("BAND_BOARDS", 1)):
        if not _is_int(out[name]) or out[name] < lo:
            return bad(name, f"a whole number, {lo} or more")
    if not isinstance(out["ROTOR_MODEL"], str) or out["ROTOR_MODEL"].strip().lower() not in ("eddy", "screen"):
        return bad("ROTOR_MODEL", '"eddy" or "screen"')
    out["ROTOR_MODEL"] = out["ROTOR_MODEL"].strip().lower()
    b = out["BAND_WIDTH_LIMIT_PERCENT"]
    if not _is_num(b) or not 0.0 < b <= 100.0:
        return bad("BAND_WIDTH_LIMIT_PERCENT", "a number above 0, at most 100")
    b = out["BAND_STEP_PERCENT"]
    if not _is_num(b) or not 1.0 <= b <= 100.0:
        return bad("BAND_STEP_PERCENT", "a number from 1 to 100")
    return out, None


FINGER_MODES = ("all", "single", "none")
FINGER_LABELS = {"all": "fingers at every tip", "single": "one finger per coil", "none": "no fingers"}


def _finger_mode(cand, P):
    """RX_TABS of this candidate (or, without its own, of the parameter files): "all", "single" or "none"."""
    return str(cand.get("RX_TABS", getattr(P, "RX_TABS", "all"))).strip().lower()


def _fingers_text(cand, P):
    return _finger_mode(cand, P)


def _reasons(exc):
    errs = list(exc.report.errors) if getattr(exc, "report", None) is not None else []
    return errs or [str(exc)]


def _build(base_over, cand_over):
    """Check + build one design.  When the finished geometry fails its checks with the TX tail position
    of the parameter files (and that is not already "auto"), it is tried again with
    TX_START_ANGLE_DEG = "auto".  A design that cannot be built at all (for example the junction vias
    of the sub-coils find no place) fails the same way with any TX tail position, and that attempt can
    take a minute at 16 loops, so it is not repeated.
    Returns (stator, rotor, report, P, tx_auto).  Raises AC.DesignError with .reasons."""
    P = _overlay(base_over, cand_over)
    try:
        stator, rotor, rep = AC.prepare(P)
        return stator, rotor, rep, P, False
    except AC.DesignError as first:
        tx0 = str(getattr(P, "TX_START_ANGLE_DEG")).strip().lower()
        if first.kind != "design" or cand_over.get("TX_START_ANGLE_DEG") == "auto" or tx0 == "auto":
            first.reasons = _reasons(first)
            raise
        P2 = _overlay(base_over, dict(cand_over, TX_START_ANGLE_DEG="auto"))
        try:
            stator, rotor, rep = AC.prepare(P2)
            return stator, rotor, rep, P2, True
        except AC.DesignError as second:
            second.reasons = [f"{m}" for m in _reasons(first)] + \
                             [f"(also with TX_START_ANGLE_DEG = \"auto\":) {m}" for m in _reasons(second)]
            raise second


def band_from(ri, ro, w_pct, p_pct):
    """(RX_R_BASE_MM, RX_A_MM) of the band that is w_pct % as wide as the widest band ri ... ro (mm), placed at
    p_pct % of the free space (0 = at the inner end, 100 = at the outer end).  Rounded inwards to 0.001 mm, so the
    band never leaves the widest band."""
    width = ro - ri
    if w_pct >= 100.0 - 1e-9:
        start, end = ri, ro
    else:
        start = ri + (width - width * w_pct / 100.0) * p_pct / 100.0
        end = start + width * w_pct / 100.0
    start = math.ceil(round(start * 1000.0, 6)) / 1000.0
    end = math.floor(round(end * 1000.0, 6)) / 1000.0
    return round(0.5 * (start + end), 4), round(0.5 * (end - start), 4)


def band_grid(limit, step):
    """[(width %, position %), ...]: the widest band, and every narrower width (down to `limit`) at every position,
    in steps of `step` percent."""
    ws = sorted({round(100.0 - k * step, 4) for k in range(1, int((100.0 - limit) / step + 1e-9) + 1)}
                | ({round(limit, 4)} if limit < 100.0 - 1e-9 else set()), reverse=True)
    ps = sorted({round(i * step, 4) for i in range(int(100.0 / step + 1e-9) + 1)} | {100.0})
    return [(100.0, 0.0)] + [(w, p) for w in ws for p in ps]


def band_neighbours(best, h, limit):
    """The 3 x 3 bands around `best` (width %, position %) at distance h percent."""
    out = []
    for dw in (-h, 0.0, h):
        for dp in (-h, 0.0, h):
            w = round(min(100.0, max(limit, best[0] + dw)), 4)
            pos = 0.0 if w >= 100.0 - 1e-9 else round(min(100.0, max(0.0, best[1] + dp)), 4)
            if (w, pos) not in out:
                out.append((w, pos))
    return out


def search_bands(nboards, ri, ro, limit, step, make_task, run, score, log):
    """Looks for the best band on each of `nboards` boards.  The first round tries a coarse grid of bands (at most
    BAND_COARSE_MAX per board); each further round halves the step and tries the bands around the best one, down to
    `step`.  make_task(board, w, p, rb, a) -> task (its key must be (board, w, p)); run(tasks) -> results;
    score(result) -> number (smaller is better) or None (cannot be used); log(text).
    Returns, per board, dict(done={(w, p): result}, best=(w, p) or None, tried=n)."""
    state = [dict(done={}, best=None) for _ in range(nboards)]

    def best_of(done):
        sc = {k: score(r) for k, r in done.items()}
        sc = {k: v for k, v in sc.items() if v is not None}
        if not sc:
            return None
        lo = min(sc.values())
        near = [k for k, v in sc.items() if v <= lo * (1.0 + TIE_FRACTION / 4.0) + 1e-12]
        return max(near, key=lambda k: done[k].get("amp", 0.0))             # about equal: the most signal

    def evaluate(points):
        tasks = []
        for bi, pts in enumerate(points):
            for w, pos in pts:
                if (w, pos) not in state[bi]["done"]:
                    rb, a = band_from(ri, ro, w, pos)
                    tasks.append(make_task(bi, w, pos, rb, a))
        for r in run(tasks):
            bi, w, pos = r["key"]
            state[bi]["done"][(w, pos)] = r
        for st in state:
            st["best"] = best_of(st["done"])
        return len(tasks)

    s0 = step
    while len(band_grid(limit, s0)) > BAND_COARSE_MAX and s0 < 100.0:
        s0 = min(2.0 * s0, 100.0)
    n = evaluate([band_grid(limit, s0)] * nboards)
    log(f"step {s0:g} %: {n} bands", state)
    h = s0
    while h > step + 1e-9 and any(st["best"] is not None for st in state):
        h = max(h / 2.0, step)
        n = evaluate([band_neighbours(st["best"], h, limit) if st["best"] is not None else [] for st in state])
        log(f"step {h:g} %: {n} bands", state)
    for st in state:
        st["tried"] = len(st["done"])
    return state


def _band_text(cand):
    """'16.2-21.4' for a candidate with its own RX band (RX_R_BASE_MM / RX_A_MM), else ''."""
    if cand.get("RX_R_BASE_MM") is None:
        return ""
    rb, a = float(cand["RX_R_BASE_MM"]), float(cand["RX_A_MM"])
    return f"{rb - a:g}-{rb + a:g}"


def _cand_text(cand, P=None):
    prof = cand.get("RX_PROFILE", getattr(P, "RX_PROFILE", "?") if P is not None else "?")
    n = cand.get("RX_SUBCOILS", getattr(P, "RX_SUBCOILS", 1) if P is not None else 1)
    split = cand.get("RX_SUBCOIL_SPLIT_ELEC_DEG",
                     getattr(P, "RX_SUBCOIL_SPLIT_ELEC_DEG", 45.0) if P is not None else 45.0)
    sub = "1" if int(n) == 1 else f"{int(n)} @ {float(split):g} deg"
    if cand.get("RX_R_BASE_MM") is not None:
        sub += f", band {_band_text(cand)}"
    return prof, sub


# ---------------------------------------------------------------------------- electrical estimate
def _elec_screen(stator, P, model, duty, amp):
    """Electrical numbers of a screened candidate: nominal air gap, the rotor extent the model has now, this
    metal fraction and receiver amplitude (model units).  Plain data (it is sent back from a worker)."""
    try:
        rot = types.SimpleNamespace(r_in=model.r_in, r_out=model.r_out, duty=duty, sectors=model.Nrot)
        el = CE.Electrics(stator, rot, P, amp=amp, prepreg=model.prepreg, model=model)
        c = el.case(amp, el.gap)
        return dict(rx=c["rx"], k=c["k"], L=el.L_nom, C=el.C, codes=el.warning_codes)
    except Exception as e:                                    # an estimate must not stop the search
        return dict(error=f"{type(e).__name__}: {e}")


def _elec_window(stator, rotor, P, model, rows):
    """Electrical estimate of a finalist over its whole tolerance window (AnalyzeCoil rows).  Plain data."""
    try:
        el = CE.Electrics(stator, rotor, P, amp=rows[0].m["amp_s"], prepreg=model.prepreg, model=model)
        cases = AC.window_cases(el, rows)
        seen = {(l, c) for l, c, _m in el.findings}
        findings = list(el.findings) + [f for f in el.check_cases(cases, "over the tolerance window")
                                        if (f[0], f[1]) not in seen]
        rxs = [c["rx"] for c in cases if c["rx"] is not None]
        return dict(heading=el.heading(), lines=el.lines(title=False), summary=el.summary(), findings=findings,
                    codes=sorted({c for l, c, _m in findings if l == "warning"}), ic=el.ic,
                    tx_text=el.tx_text() if el.tx_vpp else None,
                    rx_nom=cases[0]["rx"], k_nom=cases[0]["k"],
                    rx_lo=min(r[0] for r in rxs) if rxs else None, rx_hi=max(r[1] for r in rxs) if rxs else None,
                    f_lo=min(c["f"] for c in cases), f_hi=max(c["f"] for c in cases),
                    rx_status=el.rx_status(cases) if (el.lim and rxs) else None,
                    f_ok=(el.lim["f_min"] <= min(c["f"] for c in cases) and max(c["f"] for c in cases) <= el.lim["f_max"])
                    if el.lim else None,
                    lim_rx=el.lim["rx_vpp"] if el.lim else None,
                    lim_f=(el.lim["f_min"], el.lim["f_max"]) if el.lim else None,
                    L_free=el.L_free, L_nom=el.L_nom, C=el.C)
    except Exception as e:
        return dict(error=f"{type(e).__name__}: {e}")


def _rx_short(rx):
    """'179-328' (mVpp) or '-'."""
    if not rx:
        return "-"
    return CE._mv(rx[1]) if rx[0] == rx[1] else f"{CE._mv(rx[0])}-{CE._mv(rx[1])}"


def _elec_row(e):
    """Short text of a stage-1 electrical result."""
    if not e or "error" in e:
        return ""
    if e.get("rx"):
        return f"RX {_rx_short(e['rx'])} mVpp"
    return f"M/L {e['k'] * 100:.2f} %" if e.get("k") is not None else ""


def _elec_window_row(e):
    """Short text of a stage-2 electrical result: receiver voltage and oscillator frequency over the window."""
    if not e or "error" in e:
        return ""
    rx = f"RX {_rx_short((e['rx_lo'], e['rx_hi']))} mVpp, " if e.get("rx_lo") is not None else ""
    return rx + f"f {CE._mhz(e['f_lo'], e['f_hi'])}"


def _code_text(codes):
    return ", ".join(CE.CODE_TEXT.get(c, c) for c in codes)


# ---------------------------------------------------------------------------- stage 1
def _outer_limit(stator, P):
    """Radius beyond which the generator never puts rotor copper (it stays inside the TX ring)."""
    return float(stator.tx_inner_edge) - float(P.ROTOR_AUTO_TX_CLEARANCE_MM)


def _outer_axis(outer, stator, P, tol):
    """The positions of the rotor's outer edge (mm past the RX band) that are tried for this layout, or None when
    the outer edge is not searched (SEARCH_ROTOR_OUTER_EDGE = False, ROTOR_MODE = "custom", or the TX ring leaves no room).
    `e` also holds `k` extra positions at both ends: the neighbours that the tolerance needs for the
    first and the last position that may be chosen (`n` positions)."""
    if outer is None or str(P.ROTOR_MODE).lower() != "according_to_stator":
        return None
    lo = float(outer[0])
    hi = min(float(outer[1]), _outer_limit(stator, P) - float(stator.ro))
    if hi < lo - 1e-9:
        return None
    n = int(math.floor((hi - lo) / OUTER_STEP_MM + 1e-9)) + 1
    k = int(round(tol / OUTER_STEP_MM)) if tol > 0 else 0
    e = np.round(lo + OUTER_STEP_MM * np.arange(-k, n + k), 4)
    return dict(e=e, k=k, n=n, reach=float(stator.ro) + float(e[-1]) + 0.5, clipped=hi < float(outer[1]) - 1e-9)


def _scan(model, th, x, duties, gaps, offsets, g0):
    """For every rotor metal fraction in `duties` (at the rotor extent the model has now): the worst peak
    error over the air-gap window and the metal-fraction tolerance, and the signal amplitude at the
    nominal air gap."""
    worst = np.zeros(len(duties))
    amp = np.zeros(len(duties))
    for off in offsets:
        dd = duties + off
        for g in gaps:
            Vs, Vc = model.signals_centred(th, gap=g, duty=dd)
            pk, am = AC.analyse_batch(Vs, Vc, x)
            worst = np.maximum(worst, np.where(np.isfinite(pk), pk, np.inf))
            if off == 0.0 and abs(g - g0) < 1e-12:
                amp = am
    return worst, amp


def _worst_neighbour(F, k):
    """For every row of F: the largest value in the rows up to k away (the outer edge may be off by k steps)."""
    R = F.copy()
    for s in range(1, min(k, F.shape[0] - 1) + 1):
        R[s:] = np.maximum(R[s:], F[:-s])
        R[:-s] = np.maximum(R[:-s], F[s:])
    return R


def stage1(task):
    """Build one structural candidate (profile, sub-coils) and scan the rotor metal fraction together with
    where the rotor copper ends on the outside."""
    t0 = time.time()
    res = dict(key=task["key"], cand=task["cand"], status="ok")
    try:
        try:
            stator, rotor, rep, P, tx_auto = _build(task["base"], task["cand"])
        except AC.DesignError as e:
            res.update(status="rejected", reasons=e.reasons, seconds=time.time() - t0)
            return res
        res["tx_auto"] = tx_auto
        res["warnings"] = list(rep.warnings)
        if task.get("rotor_model", "eddy") == "eddy":
            return _stage1_eddy(task, res, stator, rotor, P, t0)
        axis = _outer_axis(task["outer"], stator, P, task["outer_tol"])
        try:
            model = AC.make_model(stator, rotor, P, rotor_model="screen", blur=task["blur"],
                                  reach=None if axis is None else axis["reach"], true3d=task.get("true3d"))
        except AC.DesignError as e:
            res.update(status="rejected", reasons=[str(e)], seconds=time.time() - t0)
            return res
        res["grid_hi"] = float(model.r_edges[-1])
        g0 = float(P.AIR_GAP_MM)
        tol = task["gap_tol"]
        gaps = [max(g0 - tol, 0.1), g0, g0 + tol] if tol > 0 else [g0]
        th = model.theta_period(AC.SAMPLES_PER_PERIOD)
        x = model.N * th

        dt = task["duty_tol"]
        offsets = (-dt, 0.0, dt) if dt > 0 else (0.0,)

        def scan(duties):
            return _scan(model, th, x, duties, gaps, offsets, g0)

        ro = float(stator.ro)
        lo, hi = task["duty_range"]
        ds = np.arange(lo, hi + 1e-9, DUTY_STEP)
        if axis is None:                                      # the outer edge stays as it is
            k, n_main, e_axis = 0, 1, None
            f1, a1 = scan(ds)
            F, A = f1[None, :], a1[None, :]
        else:
            k, n_main, e_axis = axis["k"], axis["n"], axis["e"]
            F = np.empty((len(e_axis), len(ds)))
            A = np.empty_like(F)
            for i, e in enumerate(e_axis):
                model.set_rotor_extent(r_out=ro + float(e))
                F[i], A[i] = scan(ds)
        main = slice(k, k + n_main)                           # the positions that may be chosen
        ok = np.zeros(F.shape, dtype=bool)
        ok[main] = A[main] >= task["min_amp"]
        res["curve"] = (ds.tolist(), F[k].tolist(), (A[k] / task["amp_base"]).tolist())
        if not ok.any():
            res.update(status="no_duty", seconds=time.time() - t0,
                       reasons=[f"the signal stays below {task['min_signal']:g} x the current design "
                                f"for every rotor metal fraction in {lo:g} ... {hi:g}"
                                + ("" if axis is None else " and every position of the rotor's outer edge")])
            return res
        R = np.where(ok, _worst_neighbour(F, k), np.inf)
        i0, j0 = np.unravel_index(int(np.argmin(R)), F.shape)
        if axis is not None:                                  # about equally good positions (within TIE_FRACTION) at
            near = np.where(R[:, j0] <= R[i0, j0] * (1.0 + TIE_FRACTION))[0]       # this metal fraction: take the one
            i0 = int(near[np.argmin(np.abs(e_axis[near]))])                         # closest to the RX band's outer radius
        d0 = float(ds[j0])
        res["curve"] = (ds.tolist(), F[i0].tolist(), (A[i0] / task["amp_base"]).tolist())
        fine = np.round(np.arange(max(d0 - 0.006, lo), min(d0 + 0.006, hi) + 1e-9, 0.001), 3)
        if axis is None:
            ff, aa = scan(fine)
            robust = ff
            res["ext_out"] = float(rotor.r_out) - ro
        else:
            e0 = float(e_axis[i0])
            res.update(e_lo=float(e_axis[k]), e_hi=float(e_axis[k + n_main - 1]), e_clipped=bool(axis["clipped"]))
            rows = []
            for off in range(-k, k + 1):                      # the tolerance of the outer edge
                model.set_rotor_extent(r_out=ro + e0 + off * OUTER_STEP_MM)
                rows.append(scan(fine))
            ff, aa = rows[k]
            robust = np.max([r[0] for r in rows], axis=0)
            model.set_rotor_extent(r_out=ro + e0)
            res["ext_out"] = e0
        j = int(np.argmin(np.where(aa >= task["min_amp"], robust, np.inf)))
        res.update(duty=float(fine[j]), f_design=float(ff[j]), amp_ratio=float(aa[j] / task["amp_base"]),
                   searched=axis is not None)
        res["elec"] = _elec_screen(stator, P, model, float(fine[j]), float(aa[j]))
    except Exception:                                         # a crash must not stop the search
        res.update(status="crash", reasons=[traceback.format_exc(limit=3)])
    res["seconds"] = time.time() - t0
    return res


def _outer_positions_eddy(stator, P, rotor):
    """Outer radii of the rotor copper tried with the eddy model: from 0.2 mm inside the RX band's outer radius to
    the limit set by the board outline (ROTOR_AUTO_EDGE_CLEARANCE_MM), always including the end of the outermost
    TX turn, 0.5 mm past it and the current rotor."""
    ro = float(stator.ro)
    tx_out = RG.tx_outer_edge(stator, P)
    r_max = float(stator.outer_edge_radius) - float(P.EDGE_LINE_WIDTH_MM) / 2.0 - float(P.ROTOR_AUTO_EDGE_CLEARANCE_MM)
    pts = set(np.round(np.arange(ro - 0.2, r_max + 1e-9, EDDY_OUTER_STEP_MM), 3).tolist())
    pts |= {round(r_max, 3), round(tx_out, 3), round(min(tx_out + 0.5, r_max), 3), round(float(rotor.r_out), 3)}
    return sorted(p for p in pts if ro - 0.2 - 1e-9 <= p <= r_max + 1e-9), tx_out, r_max


def _scan_eddy(model, th, x, duties, gaps, g0):
    """Worst peak error over the air gaps and the amplitude at the nominal gap, for every metal fraction."""
    worst, amp = np.zeros(len(duties)), np.zeros(len(duties))
    for i, d in enumerate(duties):
        V = [model.signals_centred(th, gap=g, duty=float(d)) for g in gaps]
        pk, am = AC.analyse_batch(np.array([v[0] for v in V]), np.array([v[1] for v in V]), x)
        worst[i] = float(np.max(np.where(np.isfinite(pk), pk, np.inf)))
        amp[i] = float(am[[abs(g - g0) < 1e-12 for g in gaps].index(True)])
    return worst, amp


def _stage1_eddy(task, res, stator, rotor, P, t0):
    """Stage 1 with the eddy-current rotor model: the metal fraction and the outer radius of the rotor copper
    (from the RX band to the board outline, over the TX turns) on a coarse grid, then refined around the best
    point, with the metal-fraction tolerance."""
    search = task["outer"] is not None and str(P.ROTOR_MODE).lower() == "according_to_stator"
    if search:
        positions, tx_out, r_max = _outer_positions_eddy(stator, P, rotor)
    else:
        positions, tx_out, r_max = [float(rotor.r_out)], RG.tx_outer_edge(stator, P), float(rotor.r_out)
    try:
        model = AC.make_model(stator, rotor, P, rotor_model="eddy", reach=max(positions) + 0.5,
                              true3d=task.get("true3d"))
    except AC.DesignError as e:
        res.update(status="rejected", reasons=[str(e)], seconds=time.time() - t0)
        return res
    res["grid_hi"] = float(model.r_edges[-1])
    g0 = float(P.AIR_GAP_MM)
    tol = task["gap_tol"]
    gaps = [max(g0 - tol, 0.1), g0, g0 + tol] if tol > 0 else [g0]
    th = model.theta_period(AC.SAMPLES_PER_PERIOD)
    x = model.N * th
    lo, hi = task["duty_range"]
    dt = task["duty_tol"]
    ro = float(stator.ro)
    coarse = np.round(np.arange(lo, hi + 1e-9, EDDY_DUTY_STEP), 4)
    F = np.empty((len(positions), len(coarse)))
    A = np.empty_like(F)
    for i, r in enumerate(positions):
        model.set_rotor_extent(r_out=r)
        F[i], A[i] = _scan_eddy(model, th, x, coarse, gaps, g0)
    i_now = int(np.argmin(np.abs(np.array(positions) - float(rotor.r_out))))
    res["curve"] = (coarse.tolist(), F[i_now].tolist(), (A[i_now] / task["amp_base"]).tolist())
    ok = A >= task["min_amp"]
    if not ok.any():
        res.update(status="no_duty", seconds=time.time() - t0,
                   reasons=[f"the signal stays below {task['min_signal']:g} x the current design for every rotor "
                            f"metal fraction in {lo:g} ... {hi:g}" + (" and every outer edge" if search else "")])
        return res
    Fm = np.where(ok, F, np.inf)
    best = float(Fm.min())
    # about equally good points (within TIE_FRACTION): the one with the most signal
    near = np.argwhere(Fm <= best * (1.0 + TIE_FRACTION))
    i0, j0 = max(near.tolist(), key=lambda ij: A[ij[0], ij[1]])
    d0, r0 = float(coarse[j0]), float(positions[i0])
    # refine: the metal fraction on the fine grid (with its tolerance), the outer edge +- half a coarse step
    fine = np.round(np.arange(max(d0 - EDDY_DUTY_STEP, lo), min(d0 + EDDY_DUTY_STEP, hi) + 1e-9, DUTY_STEP), 4)
    offs = (-dt, 0.0, dt) if dt > 0 else (0.0,)
    allds = np.unique(np.round(np.concatenate([fine + o for o in offs]), 6))
    allds = allds[(allds > 0.01) & (allds < 0.99)]
    r_try = [r0] + ([r for r in (r0 - 0.5 * EDDY_OUTER_STEP_MM, r0 + 0.5 * EDDY_OUTER_STEP_MM)
                     if ro - 0.2 - 1e-9 <= r <= r_max + 1e-9] if search else [])
    cand = []
    for r in r_try:
        model.set_rotor_extent(r_out=r)
        w, a = _scan_eddy(model, th, x, allds, gaps, g0)
        look = {round(float(d), 6): (wi, ai) for d, wi, ai in zip(allds, w, a)}
        for d in fine:
            vals = [look.get(round(float(d + o), 6)) for o in offs]
            if any(v is None for v in vals):
                continue
            cand.append((max(v[0] for v in vals), look[round(float(d), 6)][1], float(d), r))
    cand = [c for c in cand if c[1] >= task["min_amp"]] or cand
    best = min(c[0] for c in cand)
    f_design, a_best, duty, r_best = max((c for c in cand if c[0] <= best * (1.0 + TIE_FRACTION / 4.0)),
                                         key=lambda c: c[1])
    model.set_rotor_extent(r_out=r_best)
    res.update(duty=duty, f_design=float(f_design), amp_ratio=float(a_best / task["amp_base"]), searched=search,
               ext_out=r_best - ro, r_out=r_best, tx_over=r_best - tx_out, e_lo=positions[0] - ro,
               e_hi=positions[-1] - ro, e_clipped=True)
    res["elec"] = _elec_screen(stator, P, model, duty, float(a_best))
    res["seconds"] = time.time() - t0
    return res


# ---------------------------------------------------------------------------- stage 2
def stage2(task):
    """Full tolerance window for one complete candidate (duty included)."""
    t0 = time.time()
    res = dict(key=task["key"], cand=task["cand"], status="ok")
    try:
        try:
            stator, rotor, rep, P, tx_auto = _build(task["base"], task["cand"])
        except AC.DesignError as e:
            res.update(status="rejected", reasons=e.reasons, seconds=time.time() - t0)
            return res
        model = AC.make_model(stator, rotor, P, rotor_model=task.get("rotor_model", "eddy"), blur=task["blur"],
                              reach=task.get("grid_hi"), true3d=task.get("true3d"))
        rows = AC.tolerance_window(model, task["gap_tol"], task["ecc"], task["tilt"], task["ndir"],
                                   duty_tol=task["duty_tol"])
        # the same candidate if the rotor edges were perfectly sharp (no smoothing across the air gap):
        # pessimistic, shows how much the result depends on the smoothing assumption
        sharp_worst = None
        if model.kind == "screen" and model.blur and not task.get("lite"):
            m_sharp = AC.SensorModel(stator, rotor, P, blur=False, reach=task.get("grid_hi"), true3d=task.get("true3d"))
            g0 = float(P.AIR_GAP_MM)
            tol = task["gap_tol"]
            gaps = [g0] + ([max(g0 - tol, 0.1), g0 + tol] if tol > 0 else [])
            dt, d0 = task["duty_tol"], float(rotor.duty)
            duties = [d0] + ([d0 - dt, d0 + dt] if dt > 0 else [])
            sharp_worst = max(AC.evaluate(m_sharp, gap=g, duty=d).peak for g in gaps for d in duties)
        res["elec"] = None if task.get("lite") else _elec_window(stator, rotor, P, model, rows)
        res.update(sharp_worst=sharp_worst, tx_auto=tx_auto, warnings=list(rep.warnings), duty=float(rotor.duty),
                   ext_out=float(rotor.r_out) - float(stator.ro), N=model.N, amp=rows[0].m["amp_s"], hd=list(rows[0].m["hd"]),
                   nominal=rows[0].peak, worst=max(a.peak for a in rows),
                   gd=max(a.peak for a in rows if a.kind in ("nominal", "gap", "duty")),
                   rows=[(a.label, a.kind, a.peak, a.m["amp_s"]) for a in rows],
                   sens=AC.sensitivity(rows))
    except Exception:
        res.update(status="crash", reasons=[traceback.format_exc(limit=3)])
    res["seconds"] = time.time() - t0
    return res


# ---------------------------------------------------------------------------- running tasks
def _worker_init():
    """The workers leave Ctrl-C to the main process (which stops them), so that they neither print a traceback
    each nor go on with the jobs that are already queued."""
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def _stop_workers(pool):
    """Stop the worker processes at once (Ctrl-C)."""
    try:
        for proc in list(getattr(pool, "_processes", {}).values()):
            proc.terminate()
    except Exception:
        pass


def run_tasks(fn, tasks, jobs, on_result):
    """Run fn over tasks, in worker processes when jobs > 1.  If worker processes cannot be used on this
    machine, the tasks that are not finished yet are run in this process."""
    results, done = [], set()
    if jobs > 1 and len(tasks) > 1:
        for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ[var] = "1"                             # the workers inherit this: no thread fights
        pool = None
        try:
            pool = cf.ProcessPoolExecutor(max_workers=jobs, mp_context=mp.get_context("spawn"),
                                          initializer=_worker_init)
            futs = {pool.submit(fn, t): i for i, t in enumerate(tasks)}
            for fut in cf.as_completed(futs):
                r = fut.result()
                done.add(futs[fut])
                results.append(r)
                on_result(r, len(results), len(tasks))
            pool.shutdown()
            return results
        except (BrokenProcessPool, OSError, RuntimeError, ImportError, NotImplementedError) as e:
            print(Colour.yellow(f"  worker processes are not available here ({type(e).__name__}); "
                                f"continuing in one process"))
        except KeyboardInterrupt:
            if pool is not None:
                _stop_workers(pool)
            raise
        finally:
            if pool is not None:
                pool.shutdown(wait=False, cancel_futures=True)   # also on Ctrl-C: do not wait for a long build
    for i, t in enumerate(tasks):
        if i in done:
            continue
        r = fn(t)
        results.append(r)
        on_result(r, len(results), len(tasks))
    return results


# =============================================================================
# the search
# =============================================================================
def candidate_list(profiles, counts, splits, duty_name, compare_fingers=False):
    """Coil layouts to try.  With compare_fingers every layout comes three times: RX_TABS = "all", "single", "none"."""
    out = []
    for prof in profiles:
        for n in counts:
            if n == 1:
                out.append(dict(RX_PROFILE=prof, RX_SUBCOILS=1))
            else:
                for sp in splits:
                    out.append(dict(RX_PROFILE=prof, RX_SUBCOILS=int(n), RX_SUBCOIL_SPLIT_ELEC_DEG=float(sp)))
    if compare_fingers:
        out = [dict(c, RX_TABS=t) for c in out for t in FINGER_MODES]
    return out


def fmt_pair(deg_el, N):
    return f"{deg_el:.3f} ({deg_el / N:.4f})"


def short(text, n=120):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 3] + "..."


def main(argv=None):
    extra = list(sys.argv[1:] if argv is None else argv)
    if extra:
        print("OptimizeCoil.py has no command-line options: everything it does is set in OptimizerParameters.py "
              "(Parameters folder). Edit that file and run  python OptimizeCoil.py  again.")
        return 2
    Colour.setup(None)
    t_start = time.time()
    if AC.load_parameters() is None:
        return 1
    opt, err = load_optimizer_parameters()
    if err:
        print(Colour.red("ERROR   " + err))
        return 1
    args = types.SimpleNamespace(
        profiles=list(opt["PROFILES"]), subcoils=sorted(set(opt["SUBCOIL_COUNTS"])), splits=list(opt["SUBCOIL_SPLITS_DEG"]),
        duty_range=tuple(float(v) for v in opt["DUTY_RANGE"]), outer_range=tuple(float(v) for v in opt["OUTER_RANGE_MM"]),
        keep_outer=not opt["SEARCH_ROTOR_OUTER_EDGE"], outer_tol=float(opt["OUTER_TOLERANCE_MM"]),
        min_signal=float(opt["MIN_SIGNAL"]), top=int(opt["FINALISTS"]), gap_tol=float(opt["GAP_TOLERANCE_MM"]),
        duty_tol=float(opt["DUTY_TOLERANCE"]), ecc=float(opt["ECCENTRICITY_MM"]), tilt=float(opt["TILT_DEG"]),
        directions=int(opt["ECC_DIRECTIONS"]), allow_warnings=opt["ALLOW_WARNINGS"], rotor_model=opt["ROTOR_MODEL"],
        no_blur=opt["SCREEN_SHARP_EDGES"], ideal_geometry=not opt["TRUE_3D_GEOMETRY"], jobs=int(opt["JOBS"]))
    args.quick = args.ecc <= 0 and args.tilt <= 0             # (air gap and metal fraction tolerances only)
    lo, hi = args.duty_range
    jobs = args.jobs if args.jobs > 0 else max(1, min(4, os.cpu_count() or 1))
    compare_fingers = opt["COMPARE_FINGERS"]
    base_over = {}
    blur = False if args.no_blur else None
    true3d = False if args.ideal_geometry else None                  # (None: AnalyzeCoil.TRUE_3D_GEOMETRY)
    rotor_model = args.rotor_model
    eddy = rotor_model == "eddy"
    # the RX base / amplitude finder works when the RX band is not given at all (it comes from the board edges)
    import Parameters as _P0
    band_given = any(getattr(_P0, n, None) is not None for n in
                     ("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM", "RX_R_BASE_MM", "RX_A_MM"))
    finder = bool(opt["RX_BASE_AND_AMPLITUDE_FINDER"]) and not band_given
    T = 5 if finder else 4                                    # number of stages

    # ------------------------------------------------------------------ 1. the current design
    print(Colour.bold(f"[1/{T}] The current design"))
    try:
        stator, rotor, rep, Pnow, _ = _build(base_over, {})
    except AC.DesignError as e:
        print(Colour.red("ERROR   the current parameters cannot be built - fix them first "
                         "(python ParameterChecker.py):"))
        for m in getattr(e, "reasons", [str(e)]):
            print("  " + Colour.red(m))
        return 1
    try:
        model0 = AC.make_model(stator, rotor, Pnow, rotor_model=rotor_model, blur=blur, true3d=true3d)
    except AC.DesignError as e:
        print(Colour.red(f"ERROR   {e}"))
        return 1
    N = model0.N
    # (ROTOR_MODE may be written in any letter case, like everywhere else)
    duty_name = "ROTOR_AUTO_DUTY" if str(Pnow.ROTOR_MODE).lower() == "according_to_stator" else "ROTOR_CUSTOM_DUTY"
    nom0 = AC.evaluate(model0)
    amp_base = nom0.m["amp_s"]
    prof0, sub0 = _cand_text({}, Pnow)
    print(f"  {N} loop(s), profile {prof0}, sub-coils {sub0}, rotor metal fraction {rotor.duty:.4g}, "
          f"gap {float(Pnow.AIR_GAP_MM):g} mm +/- {args.gap_tol:g}"
          + ("" if args.quick else f", eccentricity {args.ecc:g} mm, tilt {args.tilt:g} deg"))
    print(f"  nominal peak error {nom0.peak:.3f} deg el, signal {amp_base:.4g} (relative units)")
    base_codes = set()
    try:
        el0 = CE.Electrics(stator, rotor, Pnow, amp=amp_base, prepreg=model0.prepreg, model=model0)
        base_codes = set(el0.warning_codes)
        print(f"  electrical (estimate): {el0.summary()}")
        for w in el0.warnings:
            print("  " + Colour.yellow(f"WARNING {short(w, 160)}"))
        if base_codes:
            print("  " + Colour.dim("  (the candidates are not held responsible for what the current design already "
                                    "breaks; see AnalyzeCoil.py for the full electrical estimate)"))
    except Exception as e:
        print("  " + Colour.yellow(f"the electrical estimate could not be made: {type(e).__name__}: {e}"))
    custom_rotor = str(Pnow.ROTOR_MODE).lower() != "according_to_stator"
    outer = None if (args.keep_outer or custom_rotor) else (float(args.outer_range[0]), float(args.outer_range[1]))
    e_now = float(rotor.r_out) - float(stator.ro)
    tx_out = RG.tx_outer_edge(stator, Pnow)
    # the 'outer' column: eddy model - mm past the outer edge of the outermost TX turn; screen - past the RX band
    shift = float(stator.ro) - tx_out if eddy else 0.0
    if eddy:
        rel = float(rotor.r_out) - tx_out
        print(f"  the rotor copper ends {rel:+.2f} mm past the outermost TX turn (r = {tx_out:.2f} mm); "
              f"rotor model: eddy currents" + ("" if outer is None else
                                               " - the outer edge is searched from the RX band to the board outline"))
    if not eddy:
        print(f"  the rotor copper ends {e_now:+.2f} mm past the outer radius of the RX band "
              f"({float(stator.ri) - float(rotor.r_in):+.2f} mm at the inner edge)")
    if custom_rotor and not args.keep_outer:
        print(Colour.dim("  (ROTOR_MODE is custom: the rotor's outer edge is not searched)"))
    base_warn = set(rep.warnings)
    if base_warn:
        print("  " + Colour.yellow(f"{len(base_warn)} warning(s) already in the current design (not held against the candidates)"))
    if compare_fingers:
        print(f"  COMPARE_FINGERS = True (OptimizerParameters.py): every layout is tried with RX_TABS = "
              f"\"all\", \"single\" and \"none\" (now: \"{_fingers_text({}, Pnow)}\")")
    if jobs > 1:
        print(f"  using {jobs} worker processes")

    # ------------------------------------------------------------------ 2. stage 1
    cands = candidate_list(args.profiles, args.subcoils, args.splits, duty_name, compare_fingers)
    if finder:
        print(f"  RX band: only the board edges are given, so the widest band they and your TX coil leave is used for "
              f"the search (r = {float(stator.ri):g} ... {float(stator.ro):g} mm); the best RX_R_BASE_MM / RX_A_MM "
              f"are looked for at the end (RX_BASE_AND_AMPLITUDE_FINDER)")
    elif bool(opt["RX_BASE_AND_AMPLITUDE_FINDER"]):
        print(Colour.dim("  (RX_BASE_AND_AMPLITUDE_FINDER is True, but the RX band is given in RX_Parameters.py: it is "
                         "used as it is. Set INSIDE_RADIUS_MM, OUTSIDE_RADIUS_MM, RX_R_BASE_MM and RX_A_MM to None to "
                         "let the finder choose it from the board edges)"))
    fing = (lambda c: f"{_fingers_text(c, Pnow):<8s}") if compare_fingers else (lambda c: "")
    lo, hi = args.duty_range
    ds_n = int(round((hi - lo) / (EDDY_DUTY_STEP if eddy else DUTY_STEP))) + 1
    out_txt = "" if outer is None else (" x rotor outer edge (RX band ... board outline)" if eddy else
                                        f" x rotor outer edge {outer[0]:+g} ... {outer[1]:+g} mm")
    print(Colour.bold(f"[2/{T}] Screening {len(cands)} coil layouts x {ds_n} rotor metal fractions"
                      + (" (then refined)" if eddy else "") + f"{out_txt} "
                      f"(air gap {args.gap_tol:g} mm tolerance)"))
    common1 = dict(base=base_over, blur=blur, true3d=true3d, rotor_model=rotor_model, gap_tol=args.gap_tol,
                   duty_range=(lo, hi), min_signal=args.min_signal, min_amp=args.min_signal * amp_base,
                   amp_base=amp_base, duty_tol=args.duty_tol, outer=outer, outer_tol=args.outer_tol)

    def show1(r, k, n):
        prof, sub = _cand_text(r["cand"])
        head = f"  [{k:2d}/{n}] {prof:<18s} sub-coils {sub:<11s}{fing(r['cand'])}"
        if r["status"] == "ok":
            el = r.get("elec") or {}
            new_ic = sorted(set(el.get("codes", [])) - base_codes)
            el_txt = _elec_row(el)
            print(head + f" -> duty {r['duty']:.3f}" + (f"  outer {r['ext_out'] + shift:+.2f}" if r.get("searched") else "")
                  + f"   error {r['f_design']:.3f} deg el   "
                  f"signal {r['amp_ratio']:.2f}x" + (f" = {el_txt}" if el_txt else "") + f"   ({r['seconds']:.1f} s)"
                  + (Colour.yellow("   [needs TX_START_ANGLE_DEG = \"auto\"]") if r.get("tx_auto") else "")
                  + (Colour.yellow(f"   [{len(set(r['warnings']) - base_warn)} warning(s)]")
                     if set(r["warnings"]) - base_warn else "")
                  + (Colour.yellow(f"   [IC: {_code_text(new_ic)}]") if new_ic else ""))
        else:
            print(head + " -> " + Colour.dim(f"not possible: {short(r['reasons'][-1], 90)}   "
                                                 f"({r.get('seconds', 0.0):.1f} s)"))

    key = 0
    tasks1 = []
    for c in cands:
        tasks1.append(dict(common1, key=key, cand=c))
        key += 1
    res1 = run_tasks(stage1, tasks1, jobs, show1)
    res1.sort(key=lambda r: r["key"])
    good = [r for r in res1 if r["status"] == "ok"]
    bad = [r for r in res1 if r["status"] != "ok"]
    for r in good:
        r["new_warn"] = [w for w in r["warnings"] if w not in base_warn]
    if not good:
        print(Colour.red("No layout can be used:"))
        for msg in dict.fromkeys(short(r["reasons"][-1], 150) for r in bad):
            print("  " + msg)
        return 1

    # ------------------------------------------------------------------ 3. stage 2
    def clean_stage1(r):
        return args.allow_warnings or not r["new_warn"]
    order = sorted(good, key=lambda r: r["f_design"])
    finalists = order[:max(1, args.top)]
    best_clean = next((r for r in order if clean_stage1(r)), None)
    if best_clean is not None and best_clean not in finalists:
        finalists.append(best_clean)
    simplest = next((r for r in order if int(r["cand"]["RX_SUBCOILS"]) == 1 and clean_stage1(r)), None)
    if simplest is not None and simplest not in finalists:     # the layout with one sub-coil, to compare with
        finalists.append(simplest)
    if compare_fingers:                                        # the best of each finger setting
        for want in FINGER_MODES:
            b = next((r for r in order if _finger_mode(r["cand"], Pnow) == want and clean_stage1(r)), None) \
                or next((r for r in order if _finger_mode(r["cand"], Pnow) == want), None)
            if b is not None and b not in finalists:
                finalists.append(b)
    window_txt = "air gap" + ("" if args.quick else ", eccentricity, tilt")
    print(Colour.bold(f"[3/{T}] Full tolerance window ({window_txt}) for the current design and "
                      f"{len(finalists)} finalists"))
    common = dict(base=base_over, blur=blur, true3d=true3d, rotor_model=rotor_model, gap_tol=args.gap_tol, ecc=args.ecc,
                  tilt=args.tilt,
                  ndir=args.directions, duty_tol=args.duty_tol)
    def window_cand(r):
        """The complete candidate of a stage-1 result: layout, rotor metal fraction and outer edge, TX start."""
        c = dict(r["cand"])
        c[duty_name] = r["duty"]
        if r.get("searched") and eddy:
            c["ROTOR_AUTO_COVER_TX"] = True
            c["ROTOR_AUTO_TX_OVERHANG_MM"] = round(float(r["tx_over"]), 4)
        elif r.get("searched"):
            c["ROTOR_AUTO_COVER_TX"] = False
            c["ROTOR_AUTO_EXTENSION_OUTER_MM"] = r["ext_out"]
        if r.get("tx_auto"):
            c["TX_START_ANGLE_DEG"] = "auto"
        return c

    tasks2 = [dict(common, key="now", cand={})]
    for r in finalists:
        tasks2.append(dict(common, key=r["key"], cand=window_cand(r), grid_hi=r["grid_hi"]))

    def show2(r, k, n):
        who = "current design" if r["key"] == "now" else "{} sub-coils {}".format(*_cand_text(r["cand"]))
        if compare_fingers:
            who += ", fingers " + _fingers_text(r["cand"] if r["key"] != "now" else {}, Pnow)
        if r["status"] == "ok":
            el_txt = _elec_window_row(r.get("elec"))
            print(f"  [{k}/{n}] {who:<{57 if compare_fingers else 44}s} worst case {r['worst']:.3f} deg el"
                  + (f"   {el_txt}" if el_txt else "") + f"   ({r['seconds']:.0f} s)")
        else:
            print(f"  [{k}/{n}] {who}: " + Colour.red(short(r["reasons"][-1])))

    res2 = {r["key"]: r for r in run_tasks(stage2, tasks2, jobs, show2)}
    now = res2["now"]
    if now["status"] != "ok":
        print(Colour.red("The current design could not be evaluated."))
        return 1
    fin = []
    for r in finalists:
        s2 = res2.get(r["key"])
        if s2 is None or s2["status"] != "ok":
            continue
        # consistency: the screening number must equal the nominal / air-gap rows of the full window
        rows_g = [row[2] for row in s2["rows"] if row[1] in ("nominal", "gap", "duty")]
        if abs(max(rows_g) - r["f_design"]) > 1e-6 + 1e-3 * r["f_design"]:
            print(Colour.yellow(f"  note: the quick and the full evaluation differ for one candidate "
                                f"({max(rows_g):.4f} vs {r['f_design']:.4f})"))
        fin.append((r, s2))

    def rank(lst):
        """Best first; ties (within TIE_FRACTION of the best): the one with the smallest air gap / rotor fraction
        part comes first."""
        lst = sorted(lst, key=lambda t: t[1]["worst"])
        if lst:
            cut = lst[0][1]["worst"] * (1.0 + TIE_FRACTION)
            tied = sorted([t for t in lst if t[1]["worst"] <= cut], key=lambda t: (t[1]["gd"], t[1]["worst"]))
            lst = tied + [t for t in lst if t[1]["worst"] > cut]
        return lst

    fin = rank(fin)
    sharp_now = now.get("sharp_worst")
    now_codes = set((now.get("elec") or {}).get("codes", []))

    def new_ic_codes(s2):
        """IC limits that this candidate breaks and the current design keeps."""
        return sorted(set((s2.get("elec") or {}).get("codes", [])) - now_codes)

    def problems(r, s2):
        """Why a candidate is not recommended (empty list = it may be recommended)."""
        out = []
        if r["new_warn"] and not args.allow_warnings:
            out.append("generator warnings")
        if new_ic_codes(s2):
            out.append(f"{(s2.get('elec') or {}).get('ic') or 'IC'}: {_code_text(new_ic_codes(s2))}")
        if sharp_now is not None and s2.get("sharp_worst") is not None and s2["sharp_worst"] > 1.10 * sharp_now:
            out.append("worse than now if the rotor edges are sharp")
        return out


    # ------------------------------------------------------------------ 4. RX base and amplitude finder
    if finder:
        ri_w, ro_w = float(stator.ri), float(stator.ro)
        limit, step = float(opt["BAND_WIDTH_LIMIT_PERCENT"]), float(opt["BAND_STEP_PERCENT"])
        layout_now = dict(RX_PROFILE=str(Pnow.RX_PROFILE), RX_SUBCOILS=int(Pnow.RX_SUBCOILS))
        if int(Pnow.RX_SUBCOILS) > 1:
            layout_now["RX_SUBCOIL_SPLIT_ELEC_DEG"] = float(Pnow.RX_SUBCOIL_SPLIT_ELEC_DEG)
        if compare_fingers:
            layout_now["RX_TABS"] = _fingers_text({}, Pnow)
        boards = [dict(name="current layout", layout=layout_now, cand=dict(layout_now), grid_hi=None)]
        n_top = int(opt["BAND_BOARDS"])
        picked = [(r, s2) for r, s2 in fin if not problems(r, s2)][:n_top]
        for k, (r, s2) in enumerate(picked, 1):
            boards.append(dict(name=f"board {k}", layout={x: v for x, v in r["cand"].items()
                                                         if x in ("RX_PROFILE", "RX_SUBCOILS", "RX_SUBCOIL_SPLIT_ELEC_DEG", "RX_TABS")},
                               cand=window_cand(r), grid_hi=r["grid_hi"]))
        for b in boards:
            pr, sb = _cand_text(b["layout"], Pnow)
            b["text"] = f"{b['name']} ({pr}, sub-coils {sb.split(',')[0]})"
        n_grid = len(band_grid(limit, step))
        print(Colour.bold(f"[4/{T}] RX base and amplitude finder: the best RX_R_BASE_MM and RX_A_MM for "
                          f"{len(boards)} boards (your current layout and the best {len(boards) - 1})"))
        print(f"  the widest band is r = {ri_w:g} ... {ro_w:g} mm; bands from 100 % down to {limit:g} % of its width, "
              f"step {step:g} % ({n_grid} bands in all per board; the search starts coarse and refines around the best)")
        print(f"  each band is judged with the board's own rotor settings over the air gap and metal fraction "
              f"tolerances; a band whose signal is below {args.min_signal:g} x the current design is not allowed; "
              f"the TX coil moves with the band")
        common_lite = dict(common, ecc=0.0, tilt=0.0, lite=True)

        def make_task(bi, w, pos, rb, a):
            c = dict(boards[bi]["cand"], INSIDE_RADIUS_MM=None, OUTSIDE_RADIUS_MM=None, RX_R_BASE_MM=rb, RX_A_MM=a)
            t = dict(common_lite, key=(bi, w, pos), cand=c)
            if boards[bi]["grid_hi"] is not None:
                t["grid_hi"] = boards[bi]["grid_hi"]
            return t

        def run_lite(tasks):
            if not tasks:
                return []
            marks = {max(1, len(tasks) * q // 4) for q in (1, 2, 3, 4)} if len(tasks) >= 40 else set()

            def tick(r, k, n):
                if k in marks:
                    print(Colour.dim(f"    {k}/{n} bands checked"))
            return run_tasks(stage2, tasks, jobs, tick)

        def band_score(r):
            if r["status"] != "ok" or r["amp"] < args.min_signal * amp_base:
                return None
            if not args.allow_warnings and set(r["warnings"]) - base_warn:
                return None
            return r["worst"]

        def log(text, state):
            line = "  " + text + ";  best so far: " + ",  ".join(
                (f"{st['done'][st['best']]['worst']:.3f}" if st["best"] else "-") for st in state) + " deg el"
            print(line)

        found = search_bands(len(boards), ri_w, ro_w, limit, step, make_task, run_lite, band_score, log)
        print()
        print(Colour.dim(f"  {'board':<44s}{'widest band':>14s} {'error':>7s}   {'best band':>14s} {'error':>7s} {'signal':>7s}"
                         f"   {'RX_R_BASE_MM':>12s} {'RX_A_MM':>8s}   bands tried"))
        refit = []
        for bi, (b, st) in enumerate(zip(boards, found)):
            wide = st["done"].get((100.0, 0.0))
            wtxt = f"{ri_w:g}-{ro_w:g}"
            werr = f"{wide['worst']:.3f}" if wide and wide["status"] == "ok" else "-"
            if st["best"] is None:
                print(f"  {b['text']:<44s}{wtxt:>14s} {werr:>7s}   " + Colour.yellow("no band can be used") + f"   {st['tried']}")
                continue
            w, pos = st["best"]
            rb, a = band_from(ri_w, ro_w, w, pos)
            br = st["done"][st["best"]]
            print(f"  {b['text']:<44s}{wtxt:>14s} {werr:>7s}   {f'{rb - a:g}-{rb + a:g}':>14s} {br['worst']:>7.3f} "
                  f"{br['amp'] / amp_base:>6.2f}x   {rb:>12g} {a:>8g}   {st['tried']}")
            b.update(rb=rb, a=a)
            if st["best"] == (100.0, 0.0):                    # the widest band is the best: the board is already in the list
                print(Colour.dim(f"  {'':<44s}-> the widest band is the best for this board"))
            else:
                refit.append(bi)
        print(Colour.dim("  (errors: worst peak error over the air gap and metal fraction tolerances, electrical degrees, "
                         "with the board's rotor settings; the rotor is refitted to a narrower best band next)"))
        # the rotor metal fraction and outer edge are fitted again to the best band, then the full tolerance window
        tasks_f = []
        for bi in refit:
            b = boards[bi]
            c1 = dict(b["layout"], INSIDE_RADIUS_MM=None, OUTSIDE_RADIUS_MM=None, RX_R_BASE_MM=b["rb"], RX_A_MM=b["a"])
            tasks_f.append(dict(common1, key=10000 + bi, cand=c1))
        if tasks_f:
            print(Colour.bold(f"  refitting the rotor to the {len(tasks_f)} best bands"))
        fit_res = run_tasks(stage1, tasks_f, jobs, show1) if tasks_f else []
        fit_ok = []
        for r in sorted(fit_res, key=lambda r: r["key"]):
            if r["status"] == "ok":
                r["new_warn"] = [w for w in r["warnings"] if w not in base_warn]
                r["board"] = boards[r["key"] - 10000]["name"]
                fit_ok.append(r)
        if fit_ok:
            print(Colour.bold(f"  full tolerance window ({window_txt}) for {len(fit_ok)} boards with their best band"))
        tasks_w = [dict(common, key=r["key"], cand=window_cand(r), grid_hi=r["grid_hi"]) for r in fit_ok]
        res_w = {r["key"]: r for r in run_tasks(stage2, tasks_w, jobs, show2)} if tasks_w else {}
        for r in fit_ok:
            s2 = res_w.get(r["key"])
            if s2 is not None and s2["status"] == "ok":
                res2[r["key"]] = s2
                fin.append((r, s2))
        fin = rank(fin)
        res1.extend(fit_ok)
        print()

    # ------------------------------------------------------------------ report
    print(Colour.bold(f"[{T}/{T}] Results"))
    print()
    print(Colour.bold("RANKING  (worst peak angle error over the tolerance window after calibration; "
                      "electrical degrees, mechanical in brackets)"))
    subw = max([12] + [len(_cand_text(r["cand"])[1]) for r, _ in fin])        # (the sub-coil column grows with a band text)
    show_sharp = sharp_now is not None                        # (no such column when the whole model is sharp)
    show_gd = args.ecc > 0 or args.tilt > 0                   # (otherwise it is the same as the worst case)
    print(Colour.dim(f"  {'rank':>4s}  {'profile':<18s} {'sub-coils':<{subw}s} " + (f"{'fingers':<8s}" if compare_fingers else "") + f"{'duty':>5s} {'outer':>6s}  {'worst case':>16s}  "
                     + (f"{'no ecc/tilt':>11s}  " if show_gd else "")
                     + f"{'nominal':>8s}  {'signal':>6s}  {'RX mVpp':>9s}  " + (f"{'if sharp':>8s}  " if show_sharp else "")
                     + "notes"))
    rec = None
    for k, (r, s2) in enumerate(fin, 1):
        prof, sub = _cand_text(r["cand"])
        notes = []
        if r.get("tx_auto"):
            notes.append("TX start auto")
        if r["new_warn"]:
            notes.append(f"{len(r['new_warn'])} warning(s)")
        probs = problems(r, s2)
        if "worse than now if the rotor edges are sharp" in probs:
            notes.append("not robust")
        if new_ic_codes(s2):
            notes.append(f"IC: {_code_text(new_ic_codes(s2))}")
        is_rec = rec is None and not probs
        if is_rec:
            rec = (r, s2)
        sharp_txt = (f"{s2['sharp_worst']:>8.3f}  " if s2.get("sharp_worst") is not None else f"{'-':>8s}  ") \
            if show_sharp else ""
        gd_txt = f"{s2['gd']:>11.3f}  " if show_gd else ""
        line = (f"  {k:>4d}  {prof:<18s} {sub:<{subw}s} {fing(r['cand'])}{r['duty']:>5.3f} {s2['ext_out'] + shift:>+6.2f}  {fmt_pair(s2['worst'], N):>16s}  "
                f"{gd_txt}{s2['nominal']:>8.3f}  {s2['amp'] / now['amp']:>5.2f}x  "
                f"{_rx_short((s2.get('elec') or {}).get('rx_nom')):>9s}  {sharp_txt}{', '.join(notes)}")
        print(Colour.green(line + ("   <- best" if is_rec else "")) if is_rec else line)
    sharp_now_txt = f"{sharp_now:>8.3f}  " if show_sharp else ""
    gd_now = f"{now['gd']:>11.3f}  " if show_gd else ""
    print(Colour.yellow(f"  {'now':>4s}  {prof0:<18s} {sub0:<{subw}s} {fing({})}{rotor.duty:>5.3f} {e_now + shift:>+6.2f}  {fmt_pair(now['worst'], N):>16s}  "
                        f"{gd_now}{now['nominal']:>8.3f}  {1.0:>5.2f}x  "
                        f"{_rx_short((now.get('elec') or {}).get('rx_nom')):>9s}  {sharp_now_txt}your current parameters"))
    if eddy:
        print(Colour.dim("  'outer' = where the rotor copper ends on the outside, mm past the outer edge of the outermost TX "
                         "turn (negative = inside it)."))
    elif outer is not None:
        print(Colour.dim("  'outer' = where the rotor copper ends on the outside, mm past the outer radius of the RX band."))
    tx_txt = (now.get("elec") or {}).get("tx_text")
    print(Colour.dim("  'RX mVpp' = receiver voltage at the nominal air gap" + (f", at {tx_txt}" if tx_txt else "")
                     + " (electrical estimate, CoilElectrics.py)."))
    if show_gd:
        print(Colour.dim("  'no ecc/tilt' = the same without eccentricity and tilt (air gap and rotor fraction tolerances only): "
                         "the part that the coil and the rotor design decide."))
    if show_sharp:
        print(Colour.dim("  'if sharp' = the worst case if the rotor edges were perfectly sharp (no smoothing across the "
                         "air gap): a pessimistic check on the model."))
    print()
    if compare_fingers:
        print_fingers_comparison(fin, now, Pnow, N, shift, problems)

    # ---------------------------------------------------------------- verdict
    if rec is None:
        if fin and fin[0][1]["worst"] > 1.01 * now["worst"]:
            print(Colour.green("Your current settings are already better than anything found here")
                  + f" (best alternative {fin[0][1]['worst']:.3f} deg el, now {now['worst']:.3f} deg el).")
        elif fin and fin[0][1]["worst"] > (1.0 - TIE_FRACTION) * now["worst"]:
            print(Colour.green("Your current settings are already about as good as anything found here")
                  + f" (best alternative {fin[0][1]['worst']:.3f} vs {now['worst']:.3f} deg el).")
        elif fin:
            print(Colour.yellow("None of the finalists can be recommended (see the notes in the ranking)."))
    else:
        r, s2 = rec
        if s2["worst"] > 1.01 * now["worst"]:
            print(Colour.green("Your current settings are already better than anything found here")
                  + f" (best alternative {s2['worst']:.3f} deg el, now {now['worst']:.3f} deg el).")
            rec = None
        elif s2["worst"] > (1.0 - TIE_FRACTION) * now["worst"]:
            print(Colour.green("Your current settings are already about as good as anything found here")
                  + f" (best alternative {s2['worst']:.3f} vs {now['worst']:.3f} deg el: a difference of "
                  f"{(1 - s2['worst'] / now['worst']) * 100:.0f} % is inside the model's uncertainty).")
            rec = None
        else:
            gain = now["worst"] / max(s2["worst"], 1e-9)
            gain_sharp = None
            if sharp_now is not None and s2.get("sharp_worst") is not None:
                gain_sharp = sharp_now / max(s2["sharp_worst"], 1e-9)
            shown = gain if gain_sharp is None else min(gain, gain_sharp)
            print(Colour.green(f"The best alternative has a lower worst-case error by a factor of at least "
                               f"{shown:.1f} in the model")
                  + f" ({now['worst']:.3f} -> {s2['worst']:.3f} deg el = {now['worst'] / N:.4f} -> "
                  f"{s2['worst'] / N:.4f} deg mech), with {s2['amp'] / now['amp']:.2f}x the signal.")
            if gain_sharp is not None:
                print(f"  if the rotor edges were perfectly sharp (pessimistic) it is still "
                      f"{sharp_now:.3f} -> {s2['sharp_worst']:.3f} deg el (factor {gain_sharp:.1f})")
            if s2["worst"] / N < 0.01:
                print(Colour.dim("  (errors below about 0.01 deg mechanical are far smaller than the other error sources "
                                 "of a real sensor: do not read the exact ratio, read 'much lower')"))
            if args.ecc > 0 and args.tilt > 0 and s2["gd"] < 0.6 * s2["worst"]:
                print(Colour.dim(f"  {s2['gd']:.3f} deg el of that comes from the air gap and rotor fraction tolerances; the rest "
                                 f"comes from the rotor being off-centre and tilted at the same time."))
            odd = lambda hd: "  ".join(f"HD{h} {v:.2f}%" for h, v in zip(range(2, 2 + len(hd)), hd) if h % 2 == 1)
            print("  odd harmonics now:   " + odd(now["hd"]))
            print("  odd harmonics then:  " + odd(s2["hd"]) + "   (even harmonics are zero for antiphase coils)")
    # the best result overall when something kept it from being recommended
    if fin and (rec is None or fin[0][0] is not rec[0]) and problems(*fin[0]) \
            and fin[0][1]["worst"] < (now["worst"] if rec is None else rec[1]["worst"]):
        r, s2 = fin[0]
        prof, sub = _cand_text(r["cand"])
        print()
        print(Colour.yellow(f"The best-ranked layout ({prof}, sub-coils {sub}, "
                            + (f"{_fingers_text(r['cand'], Pnow)}, " if compare_fingers else "") + f"duty {r['duty']:.3f}, outer {r['ext_out'] + shift:+.2f}: "
                            f"{s2['worst']:.3f} deg el) is not recommended: " + "; ".join(problems(r, s2))))
        for w in r["new_warn"][:4]:
            print("    " + Colour.yellow(short(w, 150)))
        if r["new_warn"]:
            print("  (relax the clearance, use smaller vias or a wider RX band and run this again; "
                  "or set ALLOW_WARNINGS = True in OptimizerParameters.py)")

    # ---------------------------------------------------------------- what to change
    if rec is not None:
        r, s2 = rec
        changes = []                                          # (file, name, value text)
        if r["cand"].get("RX_R_BASE_MM") is not None and getattr(Pnow, "RX_R_BASE_MM", None) is None:
            changes.append(("RX_Parameters.py", "RX_R_BASE_MM", repr(round(float(r["cand"]["RX_R_BASE_MM"]), 4))))
            changes.append(("RX_Parameters.py", "RX_A_MM", repr(round(float(r["cand"]["RX_A_MM"]), 4))))
        if r["cand"]["RX_PROFILE"] != Pnow.RX_PROFILE:
            changes.append(("RX_Parameters.py", "RX_PROFILE", f'"{r["cand"]["RX_PROFILE"]}"'))
        n_new = int(r["cand"]["RX_SUBCOILS"])
        if n_new != int(Pnow.RX_SUBCOILS):
            changes.append(("RX_Parameters.py", "RX_SUBCOILS", str(n_new)))
        if n_new > 1 and (n_new != int(Pnow.RX_SUBCOILS) or abs(
                float(r["cand"]["RX_SUBCOIL_SPLIT_ELEC_DEG"]) - float(Pnow.RX_SUBCOIL_SPLIT_ELEC_DEG)) > 1e-9):
            changes.append(("RX_Parameters.py", "RX_SUBCOIL_SPLIT_ELEC_DEG",
                            repr(float(r["cand"]["RX_SUBCOIL_SPLIT_ELEC_DEG"]))))
        if abs(r["duty"] - float(rotor.duty)) > 1e-9:
            changes.append(("Rotor_Parameters.py", duty_name, f"{r['duty']:.3f}"))
        if r.get("searched") and eddy and abs(r["ext_out"] - e_now) > 1e-9:
            if getattr(Pnow, "ROTOR_AUTO_COVER_TX", True) is not True:
                changes.append(("Rotor_Parameters.py", "ROTOR_AUTO_COVER_TX", "True"))
            changes.append(("Rotor_Parameters.py", "ROTOR_AUTO_TX_OVERHANG_MM", repr(round(float(r["tx_over"]), 4))))
        elif r.get("searched") and abs(r["ext_out"] - e_now) > 1e-9:
            if getattr(Pnow, "ROTOR_AUTO_COVER_TX", True) is not False:
                changes.append(("Rotor_Parameters.py", "ROTOR_AUTO_COVER_TX", "False"))
            changes.append(("Rotor_Parameters.py", "ROTOR_AUTO_EXTENSION_OUTER_MM", repr(round(r["ext_out"], 4))))
        if "RX_TABS" in r["cand"] and _finger_mode(r["cand"], Pnow) != _finger_mode({}, Pnow):
            n_rx = sum(1 for f, _n, _v in changes if f == "RX_Parameters.py")        # next to the other RX lines
            changes.insert(n_rx, ("RX_Parameters.py", "RX_TABS", f'"{r["cand"]["RX_TABS"]}"'))
        if r.get("tx_auto"):
            changes.append(("TX_Parameters.py", "TX_START_ANGLE_DEG", '"auto"'))
        print()
        print(Colour.bold("CHANGE THESE LINES  (everything else stays as it is)"))
        shown = None
        for f, name, val in changes:
            print(f"  {f if f != shown else '':<22s}{name} = {val}")
            shown = f
        arc = float(0.5 * (rotor.r_in + rotor.r_out)) * 2.0 * math.pi / N        # sector pitch at mid radius, mm
        print(Colour.dim(f"  the rotor metal fraction was chosen to stay good within +/- {args.duty_tol:g} "
                         f"(= +/- {args.duty_tol * arc / 2:.2f} mm at each copper edge, mid radius)"))
        if r.get("searched") and args.outer_tol > 0 and not eddy:
            print(Colour.dim(f"  the outer edge of the rotor copper was chosen to stay good within +/- {args.outer_tol:g} mm"))
        if r.get("searched") and eddy:
            print(Colour.dim(f"  the rotor copper then ends {r['tx_over']:+.2f} mm past the outermost TX turn "
                             f"(r = {r['r_out']:.2f} mm)"))
        if r.get("searched") and "e_lo" in r and not eddy:
            if r["ext_out"] <= r["e_lo"] + 1e-9:
                print(Colour.yellow(f"  the best outer edge ({r['ext_out']:+.2f} mm) is at the end of the range searched: "
                                    f"try  OUTER_RANGE_MM = ({r['e_lo'] - 0.3:g}, {outer[1]:g})"))
            elif r["ext_out"] >= r["e_hi"] - 1e-9:
                if r["e_clipped"]:
                    print(Colour.dim("  the outer edge is as far out as the TX ring allows (ROTOR_AUTO_TX_CLEARANCE_MM)"))
                else:
                    print(Colour.yellow(f"  the best outer edge ({r['ext_out']:+.2f} mm) is at the end of the range searched: "
                                        f"try  OUTER_RANGE_MM = ({outer[0]:g}, {r['e_hi'] + 0.3:g})"))
        if r["new_warn"]:                                     # only possible with ALLOW_WARNINGS = True
            print()
            print(Colour.yellow(f"The generator gives {len(r['new_warn'])} warning(s) for this layout "
                                f"(accepted because ALLOW_WARNINGS = True):"))
            for w in r["new_warn"][:5]:
                print("    " + Colour.yellow(short(w, 150)))
        if finder and r["cand"].get("RX_R_BASE_MM") is None:
            rb_w, a_w = band_from(ri_w, ro_w, 100.0, 0.0)
            print(Colour.dim(f"  the widest RX band is the best one here (RX_R_BASE_MM {rb_w:g}, RX_A_MM {a_w:g}): leave "
                             f"INSIDE_RADIUS_MM, OUTSIDE_RADIUS_MM, RX_R_BASE_MM and RX_A_MM at None"))
        cmd = ["python AnalyzeCoil.py"]
        sets = [f"{n}={v.strip(chr(34))}" for _, n, v in changes]
        if sets:
            cmd.append("--set " + " ".join(sets))
        for flag, value, default in (("--gap-tol", args.gap_tol, AC.GAP_TOLERANCE_MM),
                                     ("--duty-tol", args.duty_tol, AC.ROTOR_DUTY_TOLERANCE),
                                     ("--ecc", args.ecc, AC.ECCENTRICITY_MM), ("--tilt", args.tilt, AC.TILT_DEG),
                                     ("--directions", args.directions, AC.ECC_DIRECTIONS)):
            if value != default:                              # the same assumptions as this run
                cmd.append(f"{flag} {value:g}")
        if args.no_blur and not eddy:
            cmd.append("--no-blur")
        if args.ideal_geometry:
            cmd.append("--ideal-geometry")
        if args.rotor_model != AC.ROTOR_MODEL:
            cmd.append(f"--rotor-model {args.rotor_model}")
        print()
        print("Check it first:   " + " ".join(cmd))
        print("Then generate:    python RunCoilGenerator.py")

    # ---------------------------------------------------------------- electrical estimate
    print_electrical(now, rec[1] if rec else None)

    # ---------------------------------------------------------------- what could not be built
    if bad:
        print()
        print(Colour.bold(f"{len(bad)} layout(s) could not be used (they are not in the ranking)"))
        seen = {}
        for r in bad:
            seen.setdefault(short(r["reasons"][-1], 140), []).append(r)
        for msg, lst in list(seen.items())[:6]:
            names = ", ".join("{} / {}".format(*_cand_text(r["cand"])) + (f" / {_fingers_text(r['cand'], Pnow)}"
                                                                     if compare_fingers else "")
                              for r in lst[:3]) + (" ..." if len(lst) > 3 else "")
            print(f"  {Colour.dim(msg)}\n      ({names})")

    print()
    print(Colour.dim("Model: not checked against hardware.  The ranking says which settings are better in the "
                     "model and how sensitive they are; differences below about 20 % are ties.  Eccentricity "
                     "alone and tilt alone mostly cancel in this kind of sensor; together (tilt turning with the "
                     "rotor) they leave a small error that repeats once per turn, which is in the worst case."))
    print(Colour.dim(f"Total time {time.time() - t_start:.0f} s."))

    return 0


def print_fingers_comparison(fin, now, P, N, shift, problems):
    """COMPARE_FINGERS: the best finalist of each finger setting (RX_TABS), full tolerance window."""
    print(Colour.bold("FINGERS  (best finalist of each RX_TABS setting, full tolerance window)"))
    best = {}
    for r, s2 in fin:                                         # fin is in ranking order
        mode = _finger_mode(r["cand"], P)
        if mode not in best and not problems(r, s2):
            best[mode] = (r, s2)
    for r, s2 in fin:                                         # (a not-recommendable one only if there is no other)
        best.setdefault(_finger_mode(r["cand"], P), (r, s2))
    for mode in FINGER_MODES:
        label = f'"{mode}"'
        if mode not in best:
            print(f"  {label:<9s} " + Colour.dim(f"({FINGER_LABELS[mode]}) no layout could be built or checked"))
            continue
        r, s2 = best[mode]
        prof, sub = _cand_text(r["cand"])
        probs = problems(r, s2)
        print(f"  {label:<9s} {prof}, sub-coils {sub}, duty {r['duty']:.3f}, outer {s2['ext_out'] + shift:+.2f}:  "
              f"worst case {fmt_pair(s2['worst'], N)} deg el, signal {s2['amp'] / now['amp']:.2f}x, "
              f"RX {_rx_short((s2.get('elec') or {}).get('rx_nom'))} mVpp"
              + (Colour.yellow(f"   (not recommendable: {'; '.join(probs)})") if probs else ""))
    if len(best) > 1:
        ranked = sorted(best, key=lambda m: best[m][1]["worst"])
        w0 = best[ranked[0]][1]["worst"]
        tied = [m for m in ranked if best[m][1]["worst"] <= w0 * (1.0 + TIE_FRACTION)]
        if len(tied) > 1:
            print(Colour.dim(f"  -> {', '.join(chr(34) + m + chr(34) for m in tied)} about equal in the model (within "
                             f"the {TIE_FRACTION * 100:.0f} % it cannot tell apart)"
                             + "".join(f"; \"{m}\" worse by a factor of {best[m][1]['worst'] / max(w0, 1e-9):.1f}"
                                       for m in ranked if m not in tied)))
        else:
            print(f"  -> \"{ranked[0]}\" is the best in the model"
                  + "".join(f"; \"{m}\" is worse by a factor of {best[m][1]['worst'] / max(w0, 1e-9):.1f}"
                            for m in ranked[1:]))
        if "single" in best:
            print(Colour.dim("  (\"single\": the model treats the TX as perfect rings; the one finger next to the TX tail "
                             "picks up a constant offset that the model does not fully see - measure it with the "
                             "rotor removed)"))
    print()


def _window_text(e):
    """'receiver 165 ... 355 mVpp (IPS2550 accepts 15 ... 920: OK), oscillator 3.487 ... 3.514 MHz (...: OK)'."""
    parts = []
    if e.get("rx_lo") is not None:
        txt = f"receiver {CE._mv_range(e['rx_lo'], e['rx_hi'])} mVpp"
        if e.get("lim_rx"):
            txt += f" ({e['ic']} accepts {CE._lim(e['lim_rx'][0])} ... {CE._lim(e['lim_rx'][1])}: {e['rx_status']})"
        parts.append(txt)
    txt = f"oscillator {CE._mhz(e['f_lo'], e['f_hi'])}"
    if e.get("lim_f"):
        txt += (f" ({e['ic']} range {e['lim_f'][0] / 1e6:g} ... {e['lim_f'][1] / 1e6:g} MHz: "
                + ("OK)" if e["f_ok"] else "OUTSIDE)"))
    parts.append(txt)
    return ", ".join(parts)


def print_electrical(now, rec):
    """The electrical estimate of the current design and of the recommended one (CoilElectrics.py)."""
    e_now = now.get("elec") or {}
    e_rec = (rec or {}).get("elec") or {}
    if not e_now and not e_rec:
        return
    print()
    head = e_now.get("heading") or e_rec.get("heading") or "model only, not checked on hardware"
    print(Colour.bold(f"ELECTRICAL ESTIMATE  ({head})"))
    for who, e in (("now", e_now), ("recommended", e_rec)):
        if not e:
            continue
        if "error" in e:
            print(f"  {who + ':':<13s}" + Colour.yellow(f"not available ({e['error']})"))
            continue
        print(f"  {who + ':':<13s}{e['summary']}")
        print(f"  {'':<13s}over the tolerance window: {_window_text(e)}")
    if e_rec and "error" not in e_rec:
        print(Colour.dim("  recommended layout in detail:"))
        for line in e_rec["lines"]:
            print(line)
    shown = e_rec if (e_rec and "error" not in e_rec) else e_now
    for level, _code, msg in shown.get("findings", []):
        if level == "warning":
            print("  " + Colour.yellow("WARNING " + msg))
        else:
            print("  " + Colour.dim("info    ") + msg)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(130)
