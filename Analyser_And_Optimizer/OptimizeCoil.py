#!/usr/bin/env python3
"""
OptimizeCoil.py  -  OPTIONAL tool: looks for settings that make the sensor more accurate.

It is separate from the generator: RunCoilGenerator.py never calls it, and nothing here is
needed to make a board.  Run it when you want to know whether other settings would be better.
It never changes your parameter files - it prints the lines to change.

    python OptimizeCoil.py                     search, starting from the current parameter files
    python OptimizeCoil.py --loops 8           the same for another loop count
    python OptimizeCoil.py --quick             faster: air-gap tolerance only (no eccentricity / tilt)
    python OptimizeCoil.py --csv all.csv --plot all.png
    python OptimizeCoil.py --help              every option

What it searches (everything else stays as in your parameter files)
    RX_PROFILE                  equal_area | cosine_r | field_compensated
    RX_SUBCOILS and the split   1 sub-coil, or 2 sub-coils split by 36 ... 60 electrical degrees
    ROTOR_AUTO_DUTY             rotor metal fraction 0.25 ... 0.50
    outer edge of the rotor     where the rotor copper ends on the outside.  With the eddy-current rotor
                                model (the default, --rotor-model eddy) it is searched from 0.2 mm inside
                                the outer radius of the RX band, over the TX turns, out to the board
                                outline (ROTOR_AUTO_EDGE_CLEARANCE_MM), in 0.5 mm steps, and reported as
                                ROTOR_AUTO_COVER_TX = True with ROTOR_AUTO_TX_OVERHANG_MM (mm past the
                                outer edge of the outermost TX turn; negative = it ends over the TX turns).
                                With --rotor-model screen (the older, idealised model, which cannot judge
                                copper over the TX) it is ROTOR_AUTO_EXTENSION_OUTER_MM, -0.2 ... +0.5 mm
                                past the RX band, inside the TX ring.
                                It is searched together with the metal fraction, because the best value
                                of one depends on the other.  (--keep-outer leaves it as it is.)
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
    MIN_CLEARANCE_MM) is shown but is not recommended unless you pass --allow-warnings.
  * Differences below about 20 % are ties: the model is a ranking tool, not a measurement.  Among
    ties the outer edge of the rotor with the most signal is taken (eddy model; the screen model takes
    the one closest to the outer radius of the RX band), and in the ranking the candidate with the smaller air gap / metal fraction part comes first.  The best
    layout with one sub-coil is always shown, to compare with.
  * Every candidate also gets the electrical estimate of CoilElectrics.py: the receiver voltage in mVpp
    (screening and ranking), and the receiver voltage and oscillator frequency over the whole tolerance
    window (finalists), checked against RECEIVER_IC.  A candidate that breaks a limit of the IC which
    your current design keeps is not recommended.

Run time: the eddy-current model solves the currents in the rotor copper, so a search takes several
minutes (about 40 s per layout for the first stage, about 30 s per finalist); --rotor-model screen is
much faster but does not see what copper over the TX turns does.

Settings: at the top of this file (search ranges, tolerances) and OptimizerParameters.py (what else to
compare; a missing OptimizerParameters.py means COMPARE_FINGERS = False).

Needs Python 3 and numpy (matplotlib only for --plot).  Runs from any folder (project layout: README.txt in the project folder).
"""

import argparse
import concurrent.futures as cf
from concurrent.futures.process import BrokenProcessPool
import csv
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
# SETTINGS  (edit values; most can also be changed on the command line)
# =============================================================================
PROFILES            = ("equal_area", "cosine_r", "field_compensated")
SUBCOIL_COUNTS      = (1, 2)                       # 3 is possible (--subcoils 1 2 3) but crowded
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


# =============================================================================
# building candidates (also runs inside the worker processes)
# =============================================================================
def _overlay(base_over, cand_over):
    import Parameters as P0
    over = dict(base_over)
    over.update(cand_over)
    return AC.Overlay(P0, **over) if over else P0


def load_optimizer_parameters():
    """OptimizerParameters.py: (settings dict, None) or (None, error text).  A missing file or a missing line
    means the old behaviour (COMPARE_FINGERS = False)."""
    out = dict(COMPARE_FINGERS=False)
    try:
        import OptimizerParameters as OP
    except ModuleNotFoundError as e:
        if getattr(e, "name", None) == "OptimizerParameters":
            return out, None
        return None, f"OptimizerParameters.py cannot be loaded: {type(e).__name__}: {e}"
    except Exception as e:                                  # syntax error ...
        return None, f"OptimizerParameters.py cannot be loaded: {type(e).__name__}: {e}"
    val = getattr(OP, "COMPARE_FINGERS", False)
    if not isinstance(val, bool):
        return None, f"COMPARE_FINGERS in OptimizerParameters.py must be True or False; it is {val!r}"
    out["COMPARE_FINGERS"] = val
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


def _cand_text(cand, P=None):
    prof = cand.get("RX_PROFILE", getattr(P, "RX_PROFILE", "?") if P is not None else "?")
    n = cand.get("RX_SUBCOILS", getattr(P, "RX_SUBCOILS", 1) if P is not None else 1)
    split = cand.get("RX_SUBCOIL_SPLIT_ELEC_DEG",
                     getattr(P, "RX_SUBCOIL_SPLIT_ELEC_DEG", 45.0) if P is not None else 45.0)
    sub = "1" if int(n) == 1 else f"{int(n)} @ {float(split):g} deg"
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
    the outer edge is not searched (--keep-outer, ROTOR_MODE = "custom", or the TX ring leaves no room).
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
        if model.kind == "screen" and model.blur:
            m_sharp = AC.SensorModel(stator, rotor, P, blur=False, reach=task.get("grid_hi"), true3d=task.get("true3d"))
            g0 = float(P.AIR_GAP_MM)
            tol = task["gap_tol"]
            gaps = [g0] + ([max(g0 - tol, 0.1), g0 + tol] if tol > 0 else [])
            dt, d0 = task["duty_tol"], float(rotor.duty)
            duties = [d0] + ([d0 - dt, d0 + dt] if dt > 0 else [])
            sharp_worst = max(AC.evaluate(m_sharp, gap=g, duty=d).peak for g in gaps for d in duties)
        res["elec"] = _elec_window(stator, rotor, P, model, rows)
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
    ap = argparse.ArgumentParser(description="Search the coil settings that matter most and rank them "
                                             "(optional tool; changes no file).")
    ap.add_argument("--set", nargs="+", metavar="NAME=VALUE", help="override parameters for the whole run")
    ap.add_argument("--loops", type=int, help="shortcut for --set LOOPS=N")
    ap.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES), help="profiles to try")
    ap.add_argument("--subcoils", nargs="+", type=int, choices=(1, 2, 3), default=list(SUBCOIL_COUNTS),
                    help="sub-coil counts to try")
    ap.add_argument("--splits", nargs="+", type=float, default=list(SUBCOIL_SPLITS_DEG),
                    help="sub-coil splits to try (electrical degrees)")
    ap.add_argument("--duty-range", nargs=2, type=float, default=list(DUTY_RANGE), metavar=("LO", "HI"),
                    help="rotor metal fraction searched")
    ap.add_argument("--outer-range", nargs=2, type=float, default=list(OUTER_RANGE_MM), metavar=("LO", "HI"),
                    help="--rotor-model screen only: where the rotor copper ends on the outside, mm past the outer radius of the RX band (the eddy model searches from the RX band over the TX turns to the board outline)")
    ap.add_argument("--keep-outer", action="store_true",
                    help="do not search the rotor's outer edge (keep it as in the parameter files)")
    ap.add_argument("--outer-tol", type=float, default=OUTER_TOLERANCE_MM,
                    help="tolerance of the rotor's outer edge (mm), 0 = skip")
    ap.add_argument("--min-signal", type=float, default=MIN_SIGNAL,
                    help="smallest allowed signal, as a fraction of the current design's")
    ap.add_argument("--top", type=int, default=FINALISTS, help="finalists re-checked with ecc/tilt")
    ap.add_argument("--gap-tol", type=float, default=AC.GAP_TOLERANCE_MM, help="air gap tolerance (mm)")
    ap.add_argument("--duty-tol", type=float, default=AC.ROTOR_DUTY_TOLERANCE,
                    help="rotor metal fraction tolerance")
    ap.add_argument("--ecc", type=float, default=AC.ECCENTRICITY_MM, help="rotor eccentricity (mm)")
    ap.add_argument("--tilt", type=float, default=AC.TILT_DEG, help="rotor tilt (deg)")
    ap.add_argument("--directions", type=int, default=DIRECTIONS,
                    help="eccentricity directions tried (over one loop pitch)")
    ap.add_argument("--quick", action="store_true", help="air-gap tolerance only (no eccentricity / tilt)")
    ap.add_argument("--allow-warnings", action="store_true",
                    help="candidates with generator warnings may be recommended")
    ap.add_argument("--rotor-model", choices=("eddy", "screen"), default=None,
                    help=f"rotor model (default {AC.ROTOR_MODEL}, see AnalyzeCoil.py); the older 'screen' model is "
                         f"faster but cannot judge copper edges or copper over the TX turns")
    ap.add_argument("--no-blur", action="store_true", help="screen model only: sharp rotor edges (see AnalyzeCoil.py)")
    ap.add_argument("--ideal-geometry", action="store_true",
                    help="the older geometry: TX as rings, receiver copper half on each RX layer (see AnalyzeCoil.py)")
    ap.add_argument("--jobs", type=int, default=JOBS, help="worker processes (0 = automatic)")
    ap.add_argument("--csv", metavar="FILE.csv", help="write every candidate to a csv file")
    ap.add_argument("--plot", metavar="FILE.png", help="write a plot of the search (needs matplotlib)")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)
    Colour.setup(False if args.no_color else None)
    lo, hi = args.duty_range
    if not (0.0 < lo < hi < 1.0):
        ap.error("--duty-range needs two numbers 0 < LO < HI < 1 (for example 0.25 0.5)")
    if args.outer_range[0] > args.outer_range[1]:
        ap.error("--outer-range needs two numbers LO <= HI (for example -0.2 0.5)")
    if not 0.0 < args.min_signal <= 1.5:
        ap.error("--min-signal is a fraction of the current signal, for example 0.8")
    if args.top < 1 or args.directions < 1:
        ap.error("--top and --directions must be at least 1")
    if min(args.gap_tol, args.duty_tol, args.ecc, args.tilt, args.outer_tol) < 0 or any(s <= 0 for s in args.splits):
        ap.error("tolerances must be >= 0 and the splits > 0")
    if args.quick:
        args.ecc = args.tilt = 0.0
    jobs = args.jobs if args.jobs > 0 else max(1, min(4, os.cpu_count() or 1))
    t_start = time.time()

    if AC.load_parameters() is None:
        return 1
    opt, err = load_optimizer_parameters()
    if err:
        print(Colour.red("ERROR   " + err))
        return 1
    compare_fingers = opt["COMPARE_FINGERS"]
    base_over = AC.parse_overrides(args.set)
    if args.loops is not None:
        base_over["LOOPS"] = args.loops
    blur = False if args.no_blur else None
    true3d = False if args.ideal_geometry else None                  # (None: AnalyzeCoil.TRUE_3D_GEOMETRY)
    rotor_model = str(args.rotor_model or AC.ROTOR_MODEL).lower()
    eddy = rotor_model == "eddy"

    # ------------------------------------------------------------------ 1. the current design
    print(Colour.bold("[1/4] The current design"))
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
    fing = (lambda c: f"{_fingers_text(c, Pnow):<8s}") if compare_fingers else (lambda c: "")
    lo, hi = args.duty_range
    ds_n = int(round((hi - lo) / (EDDY_DUTY_STEP if eddy else DUTY_STEP))) + 1
    out_txt = "" if outer is None else (" x rotor outer edge (RX band ... board outline)" if eddy else
                                        f" x rotor outer edge {outer[0]:+g} ... {outer[1]:+g} mm")
    print(Colour.bold(f"[2/4] Screening {len(cands)} coil layouts x {ds_n} rotor metal fractions"
                      + (" (then refined)" if eddy else "") + f"{out_txt} "
                      f"(air gap {args.gap_tol:g} mm tolerance)"))
    tasks1 = [dict(key=i, cand=c, base=base_over, blur=blur, true3d=true3d, rotor_model=rotor_model, gap_tol=args.gap_tol,
                   duty_range=(lo, hi), min_signal=args.min_signal, min_amp=args.min_signal * amp_base,
                   amp_base=amp_base, duty_tol=args.duty_tol, outer=outer, outer_tol=args.outer_tol)
              for i, c in enumerate(cands)]

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
    print(Colour.bold(f"[3/4] Full tolerance window ({window_txt}) for the current design and "
                      f"{len(finalists)} finalists"))
    common = dict(base=base_over, blur=blur, true3d=true3d, rotor_model=rotor_model, gap_tol=args.gap_tol, ecc=args.ecc,
                  tilt=args.tilt,
                  ndir=args.directions, duty_tol=args.duty_tol)
    tasks2 = [dict(common, key="now", cand={})]
    for r in finalists:
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
        tasks2.append(dict(common, key=r["key"], cand=c, grid_hi=r["grid_hi"]))

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
    fin.sort(key=lambda t: t[1]["worst"])
    if fin:                                                   # ties (within TIE_FRACTION of the best): the one with the
        cut = fin[0][1]["worst"] * (1.0 + TIE_FRACTION)       # smallest air gap / rotor fraction part comes first
        tied = sorted([t for t in fin if t[1]["worst"] <= cut], key=lambda t: (t[1]["gd"], t[1]["worst"]))
        fin = tied + [t for t in fin if t[1]["worst"] > cut]
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

    # ------------------------------------------------------------------ 4. report
    print(Colour.bold("[4/4] Results"))
    print()
    print(Colour.bold("RANKING  (worst peak angle error over the tolerance window after calibration; "
                      "electrical degrees, mechanical in brackets)"))
    show_sharp = sharp_now is not None                        # (no such column when the whole model is sharp)
    show_gd = args.ecc > 0 or args.tilt > 0                   # (otherwise it is the same as the worst case)
    print(Colour.dim(f"  {'rank':>4s}  {'profile':<18s} {'sub-coils':<12s} " + (f"{'fingers':<8s}" if compare_fingers else "") + f"{'duty':>5s} {'outer':>6s}  {'worst case':>16s}  "
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
        line = (f"  {k:>4d}  {prof:<18s} {sub:<12s} {fing(r['cand'])}{r['duty']:>5.3f} {s2['ext_out'] + shift:>+6.2f}  {fmt_pair(s2['worst'], N):>16s}  "
                f"{gd_txt}{s2['nominal']:>8.3f}  {s2['amp'] / now['amp']:>5.2f}x  "
                f"{_rx_short((s2.get('elec') or {}).get('rx_nom')):>9s}  {sharp_txt}{', '.join(notes)}")
        print(Colour.green(line + ("   <- best" if is_rec else "")) if is_rec else line)
    sharp_now_txt = f"{sharp_now:>8.3f}  " if show_sharp else ""
    gd_now = f"{now['gd']:>11.3f}  " if show_gd else ""
    print(Colour.yellow(f"  {'now':>4s}  {prof0:<18s} {sub0:<12s} {fing({})}{rotor.duty:>5.3f} {e_now + shift:>+6.2f}  {fmt_pair(now['worst'], N):>16s}  "
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
                  "or pass --allow-warnings)")

    # ---------------------------------------------------------------- what to change
    if rec is not None:
        r, s2 = rec
        changes = []                                          # (file, name, value text)
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
                                    f"try  --outer-range {r['e_lo'] - 0.3:g} {outer[1]:g}"))
            elif r["ext_out"] >= r["e_hi"] - 1e-9:
                if r["e_clipped"]:
                    print(Colour.dim("  the outer edge is as far out as the TX ring allows (ROTOR_AUTO_TX_CLEARANCE_MM)"))
                else:
                    print(Colour.yellow(f"  the best outer edge ({r['ext_out']:+.2f} mm) is at the end of the range searched: "
                                        f"try  --outer-range {outer[0]:g} {r['e_hi'] + 0.3:g}"))
        if r["new_warn"]:                                     # only possible with --allow-warnings
            print()
            print(Colour.yellow(f"The generator gives {len(r['new_warn'])} warning(s) for this layout "
                                f"(accepted because of --allow-warnings):"))
            for w in r["new_warn"][:5]:
                print("    " + Colour.yellow(short(w, 150)))
        if args.set or args.loops is not None:
            print(Colour.dim("  (the values you gave with --set / --loops are used for this run only: "
                             "they are not in your parameter files)"))
        cmd = ["python AnalyzeCoil.py"]
        if args.loops is not None:
            cmd.append(f"--loops {args.loops}")
        sets = [f"{n}={v.strip(chr(34))}" for _, n, v in changes]
        if args.set:
            sets = list(args.set) + sets
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
        if args.rotor_model:
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

    # ---------------------------------------------------------------- csv / plot
    if args.csv:
        write_csv(args.csv, res1, res2, N, now, Pnow if compare_fingers else None)
        print(f"  csv written: {args.csv}")
    if args.plot:
        make_plot(args.plot, res1, res2, N, now, rotor, amp_base, rec[0] if rec else None, duty_name)
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


def write_csv(path, res1, res2, N, now, P_fingers=None):
    """P_fingers: the parameters, when fingers were compared (adds an 'rx_tabs' column at the end)."""
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["profile", "subcoils", "split_deg", "status", "duty", "outer_mm", "gap_window_peak_deg_el",
                    "signal_vs_current", "tx_start_auto", "warnings", "full_window_worst_deg_el",
                    "full_window_nominal_deg_el", "reason",
                    "rx_mvpp_low", "rx_mvpp_high", "tank_c_across_coil_pf", "tx_l_rotor_uh",
                    "window_rx_mvpp_low", "window_rx_mvpp_high", "window_osc_mhz_low", "window_osc_mhz_high",
                    "ic_warnings"] + (["rx_tabs"] if P_fingers is not None else []))
        tabs = (lambda c: [_finger_mode(c, P_fingers)]) if P_fingers is not None else (lambda c: [])

        def elec_cols(e1, e2):
            """Electrical columns: screening (e1, nominal air gap) and full window (e2)."""
            e1, e2 = e1 or {}, e2 or {}
            rx = e1.get("rx") or e2.get("rx_nom")
            src = e1 if "C" in e1 else e2
            return [f"{rx[0] * 1e3:.1f}" if rx else "", f"{rx[1] * 1e3:.1f}" if rx else "",
                    f"{src['C'] * 1e12:.1f}" if "C" in src else "", f"{src['L'] * 1e6:.4f}" if "L" in src else
                    (f"{src['L_nom'] * 1e6:.4f}" if "L_nom" in src else ""),
                    f"{e2['rx_lo'] * 1e3:.1f}" if e2.get("rx_lo") is not None else "",
                    f"{e2['rx_hi'] * 1e3:.1f}" if e2.get("rx_hi") is not None else "",
                    f"{e2['f_lo'] / 1e6:.4f}" if "f_lo" in e2 else "", f"{e2['f_hi'] / 1e6:.4f}" if "f_hi" in e2 else "",
                    " | ".join(e2.get("codes", e1.get("codes", [])))]

        for r in res1:
            c = r["cand"]
            s2 = res2.get(r["key"])
            ok2 = s2 is not None and s2["status"] == "ok"
            w.writerow([c["RX_PROFILE"], c["RX_SUBCOILS"], c.get("RX_SUBCOIL_SPLIT_ELEC_DEG", ""), r["status"],
                        f"{r.get('duty', ''):.3f}" if "duty" in r else "",
                        f"{r['ext_out']:.3f}" if "duty" in r else "",
                        f"{r['f_design']:.4f}" if "f_design" in r else "",
                        f"{r['amp_ratio']:.3f}" if "amp_ratio" in r else "",
                        r.get("tx_auto", ""), " | ".join(r.get("new_warn", [])),
                        f"{s2['worst']:.4f}" if ok2 else "",
                        f"{s2['nominal']:.4f}" if ok2 else "",
                        " | ".join(r.get("reasons", []))]
                       + elec_cols(r.get("elec") if r["status"] == "ok" else None, s2.get("elec") if ok2 else None)
                       + tabs(c))
        w.writerow([])
        w.writerow(["current design", "", "", "ok", "", f"{now['ext_out']:.3f}", "", "1.000", "", "", f"{now['worst']:.4f}",
                    f"{now['nominal']:.4f}", ""] + elec_cols(None, now.get("elec")) + tabs({}))


def make_plot(path, res1, res2, N, now, rotor, amp_base, rec, duty_name):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print(Colour.yellow("  matplotlib is not installed: no plot written (pip install matplotlib)"))
        return
    colours = {"equal_area": "tab:blue", "cosine_r": "tab:green", "field_compensated": "tab:red"}
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.2))
    seen = set()
    for r in res1:
        if r["status"] != "ok" or "curve" not in r:
            continue
        ds, f, amp = r["curve"]
        prof, sub = _cand_text(r["cand"])
        label = None if prof in seen else prof
        seen.add(prof)
        ls = ("-" if r["cand"]["RX_SUBCOILS"] == 1 else "--") if r["cand"].get("RX_TABS", "all") != "none" else \
            (":" if r["cand"]["RX_SUBCOILS"] == 1 else "-.")
        ax[0].plot(ds, f, ls, color=colours.get(prof, "gray"), alpha=0.55, lw=1.2, label=label)
        ax[0].plot([r["duty"]], [r["f_design"]], "o", color=colours.get(prof, "gray"), ms=4)
    ax[0].axhline(now["gd"], color="k", ls=":", lw=1)
    ax[0].text(ax[0].get_xlim()[0], now["gd"], "  current design (same window)", va="bottom", fontsize=8)
    ax[0].axvline(float(rotor.duty), color="gray", ls=":", lw=0.8)
    ax[0].set_yscale("log")
    ax[0].set_xlabel("rotor metal fraction")
    ax[0].set_ylabel("worst peak error over the air-gap window (deg el)")
    ax[0].set_title("every layout, at its chosen outer edge: error vs rotor metal fraction (dots = chosen)\n"
                    "solid = 1 sub-coil, dashed = 2 sub-coils (dotted / dash-dot: the same without fingers)", fontsize=9)
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3, which="both")
    items = [(r, res2[r["key"]]) for r in res1 if r["key"] in res2 and res2[r["key"]]["status"] == "ok"]
    items.sort(key=lambda t: t[1]["worst"])
    names = ["{}\n{} d={:.3f} e={:+.2f}".format(*_cand_text(r["cand"]), r["duty"], r["ext_out"])
             + (f" fingers {r['cand']['RX_TABS']}" if "RX_TABS" in r["cand"] else "") for r, _ in items][:8]
    vals = [s["worst"] for _, s in items][:8]
    ax[1].barh(range(len(vals)), vals, color="tab:gray", label="worst case, with the rotor off-centre and tilted")
    if any(s["gd"] < 0.99 * s["worst"] for _, s in items):
        ax[1].barh(range(len(vals)), [s["gd"] for _, s in items][:8], height=0.35, color="tab:blue",
                   label="air gap and rotor fraction tolerances only")
        ax[1].legend(fontsize=7, loc="lower right")
    ax[1].set_yticks(range(len(vals)))
    ax[1].set_yticklabels(names, fontsize=7)
    ax[1].invert_yaxis()
    ax[1].axvline(now["worst"], color="k", ls=":")
    ax[1].set_xlabel("worst case over the full tolerance window (deg el)")
    ax[1].set_title("finalists (dotted line = current design)", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    print(f"  plot written: {path}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(130)
