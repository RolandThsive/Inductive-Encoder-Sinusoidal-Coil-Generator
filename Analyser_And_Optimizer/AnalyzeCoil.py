#!/usr/bin/env python3
"""
AnalyzeCoil.py  -  predicts how the generated stator + rotor behave as an angle sensor.

It reads the same parameter files as the generator, builds the stator and rotor in memory
(nothing is written) and simulates the two receiver coils while the rotor turns:

    python AnalyzeCoil.py                        analysis of the current parameters
    python AnalyzeCoil.py --plot analysis.png    ... and a picture (needs matplotlib)
    python AnalyzeCoil.py --ecc 0.3 --tilt 0.5   change the tolerance window for this run
    python AnalyzeCoil.py --set RX_PROFILE=field_compensated RX_SUBCOILS=2 ROTOR_AUTO_DUTY=1/3
                                                 try other settings without editing any file
    python AnalyzeCoil.py --set ROTOR_AUTO_TX_OVERHANG_MM=1.5
                                                 rotor copper ending 1.5 mm past the outermost TX turn
    python AnalyzeCoil.py --set ROTOR_AUTO_COVER_TX=False ROTOR_AUTO_EXTENSION_OUTER_MM=0.05
                                                 rotor copper ending 0.05 mm past the RX band (inside the TX)
    python AnalyzeCoil.py --loops 8              shortcut for --set LOOPS=8
    python AnalyzeCoil.py --rotor-model screen   the older, faster "ideal screen" rotor model
    python AnalyzeCoil.py --ideal-geometry       the older geometry (TX rings, receiver copper half on each layer)

OptimizeCoil.py (optional) searches the settings that matter most and prints the --set line.

What it reports
  * signal amplitude, DC offset, sin/cos amplitude match, quadrature error, harmonics
  * angle error of the sin/cos pair, with and without offset/gain/quadrature calibration
  * the same for a TOLERANCE WINDOW: air gap +/- GAP_TOLERANCE_MM, rotor metal fraction
    +/- ROTOR_DUTY_TOLERANCE (etching), rotor eccentricity, rotor tilt - the tolerances that
    dominate real sensors
  * electrical estimates (CoilElectrics.py): TX inductance, tank capacitors, oscillator frequency
    and receiver voltage in mVpp, at the nominal air gap and for every case of the window, checked
    against the receiver IC (RECEIVER_IC in Board_Parameters.py)

Model (read this before trusting a number)
  * The rotor (ROTOR_MODEL = "eddy", the default; RotorEddyModel.py): every copper sector is a thin,
    perfect conductor carrying its own eddy current, solved on a grid of the copper (finest at its
    edges).  The current keeps the TX field off the copper and pushes it through the gaps and around
    the copper edges, crowded there - so the model judges copper edges, copper over or past the TX
    turns, and the metal fraction physically.  Checked against exact results (thin disc; long narrow
    sectors, the 2-D strip solution) and for convergence: signal within about 3 %, angle errors within
    about 10 % of a much finer grid.  An off-centre or tilted rotor is solved at every rotor angle
    (offset exact, tilt to first order).
  * The older model (--rotor-model screen, ROTOR_MODEL = "screen") is an ideal screen: where the copper
    covers the board the TX flux is simply removed, smoothed across the air gap.  It is faster, but it
    cannot see copper edges or copper over the TX turns (it gets the signal ratio between metal
    fractions and the best outer edge wrong); --no-blur only applies to it.
  * True 3-D geometry (TRUE_3D_GEOMETRY = True, the default; RealCopper.py), the way the Udine / Renesas tools
    work with the real traces:
      - every receiver trace at the real depth of its layer (fingers on their own layer included): each coil is
        split into closed loops per layer, each smoothed over its own distance to the rotor, and the small
        remainder of that split is computed exactly - the coil's field at the rotor matches a Biot-Savart sum
        over its real 3-D pieces within about 3 % (rms, the grid's own resolution).  Vias carry vertical
        current, which has no field normal to the board: they do not couple to the rotor.
      - the TX from its real copper: turns, radial steps, tails, go-around runs and brackets, every layer at its
        depth; a parallel TX with its DC current split.  Its azimuthal average drives the rotor exactly as the
        rings did; what the copper adds beyond that average (steps, tails, gaps, brackets) is added to first
        order (as if the rotor were an ideal screen for that small part).
      - the direct TX-to-receiver coupling without a rotor (Neumann double line integral over the real 3-D copper
        of both coils, vias included): an ideal sensor has none; the real copper leaves a little, which shows as
        an offset of the receiver signals and in "angle error, nothing removed".
    --ideal-geometry (or TRUE_3D_GEOMETRY = False) gives the older model: TX as concentric rings, receiver copper
    counted half on each RX layer, no direct coupling.  The electrical estimate (CoilElectrics.py) still uses the
    rings for the TX inductance.
  * Not modelled: the finite thickness and conductivity of the rotor copper (at 2-5 MHz the skin depth
    is about one copper thickness: close to a perfect conductor), the receiver IC, noise, the current split of
    a parallel TX at the operating frequency (the DC split is used).
  * Approximations: a tilt is first order in the tilt angle; the eddy model solves the parts of an
    off-centre / tilted rotor that change once or twice per turn (higher ones are of third order); the
    screen model averages the radial reach of an eccentric rotor between the shrunk and widened window.
  * The tolerance window tries every combination that matters: all tilt directions, a tilt that
    turns with the rotor and one fixed to the stator, and eccentricity, at the smallest and the
    largest air gap.  Each of the two alone hardly changes a well-built sensor, but together they
    leave an error that repeats once per turn.
  * Amplitudes are in model units (relative); compare variants with them.  The ELECTRICAL sections
    (CoilElectrics.py) turn them into the receiver voltage for the TX voltage of RECEIVER_IC, and give the
    TX inductance, the tank capacitors and the oscillator frequency for every case of the window.
  * It has not been checked against hardware.  Treat the numbers as a ranking tool: they say
    which design is better and how sensitive it is, not what a measurement will show.
  * Error = peak deviation of atan2(sin, cos) from the ideal line of exact slope (one electrical
    turn per period) after the best constant offset is trimmed, in electrical degrees (one
    electrical period = 360 deg; mechanical = electrical / LOOPS).

Needs only Python 3 and numpy (matplotlib only for --plot).  Runs from any folder (project layout: README.txt in the project folder).
"""

import argparse
import ast
import collections
import contextlib
import copy
import io
import math
import os
import sys

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

import ParameterChecker as PC                       # noqa: E402
from ParameterChecker import Colour, Report         # noqa: E402
import CoilElectrics as CE                          # noqa: E402
import RealCopper as RCU                            # noqa: E402  (the real copper in 3-D)
from CoilElectrics import loop_bz, layer_depth    # noqa: E402  (field of the TX turns, shared)

# =============================================================================
# SETTINGS  (edit values; every one can also be changed on the command line)
# =============================================================================
GAP_TOLERANCE_MM = 0.2      # air gap is analysed at  gap - tol, gap, gap + tol
ECCENTRICITY_MM  = 0.2      # rotor axis offset from the stator axis (0 = skip)
TILT_DEG         = 0.3      # rotor plane tilt (0 = skip); 0.3 deg is about 0.26 mm of gap
                            # change across a 50 mm radius
ECC_DIRECTIONS   = 3        # eccentricity directions tried (spread over one loop pitch: the result repeats after it)
TILT_DIRECTIONS  = 16       # tilt directions tried, in each of the two frames (costs almost nothing)
ROTOR_DUTY_TOLERANCE = 0.005  # rotor metal fraction analysed at duty +/- this (0 = skip): etching of the
                            # rotor copper, and the model's own uncertainty near sharp optima

ROTOR_MODEL = "eddy"        # "eddy": eddy currents in the rotor copper (RotorEddyModel.py, see "Model" above);
                            # "screen": the older ideal-screen model, faster but blind to copper edges and
                            # to copper over the TX turns (also: --rotor-model)
AIR_GAP_BLUR = True         # screen model only - True: the rotor pattern is smoothed across the air gap;
                            # False: sharp edges, overstates the higher harmonics (also: --no-blur)

TRUE_3D_GEOMETRY = True     # True: every receiver trace at the real depth of its layer, the TX from its real copper
                            # (steps, tails, vias, go-around, parallel current split) and the direct TX-to-receiver
                            # coupling (a real offset).  False: the older model (TX as ideal rings, the receiver
                            # copper half on each RX layer), for comparison (also: --ideal-geometry)

STACKUP_PREPREG_MM = 0.2    # 4-layer boards: spacing between an outer layer and its inner
                            # neighbour (only used to place TX turns that are on inner layers)

# numerical resolution
AZIMUTH_COLUMNS   = 5760    # polar grid: columns around the circle (360 per period at 16 loops)
RADIAL_STEP_MM    = 0.1     # polar grid: radial bin width
RIPPLE_STRIDE     = 8       # the field of the TX's real copper minus its azimuthal average: every 8th column
RIPPLE_REACH_MM   = 10.0    # ... summed over the copper within this distance of each point
CHORD_STRIDE      = (8, 3)  # the remainder of the per-layer split (RealCopper) is computed on every 8th column and
                            # 3rd row of the polar grid and interpolated
SAMPLES_PER_PERIOD = 180    # rotor positions per electrical period (centred rotor)
SAMPLES_PER_PERIOD_TOL = 48 # ... when the rotor is eccentric or tilted (the whole turn is swept)
HARMONICS         = 8       # harmonics listed


# =============================================================================
# parameter overlay: lets a tool try other settings without touching the files
# =============================================================================
class Overlay:
    """Read-only view of a parameter module with some names replaced."""

    def __init__(self, base, **over):
        object.__setattr__(self, "_base", base)
        object.__setattr__(self, "_over", dict(over))

    def __getattr__(self, name):
        over = object.__getattribute__(self, "_over")
        if name in over:
            return over[name]
        return getattr(object.__getattribute__(self, "_base"), name)

    def __dir__(self):
        return sorted(set(dir(object.__getattribute__(self, "_base"))) | set(object.__getattribute__(self, "_over")))


class DesignError(Exception):
    """The design cannot be built or has errors; .report holds the findings.
    .kind says where it failed: "parameters", "stator", "rotor" (could not be built at all)
    or "design" (built, but the checks of the finished geometry found errors)."""

    def __init__(self, message, report=None, kind="design"):
        super().__init__(message)
        self.report = report or Report()
        self.kind = kind


# =============================================================================
# design builder (parameters -> checked stator + rotor)
# =============================================================================
def load_parameters():
    """The aggregated parameter module (Parameters.py), or None after printing why it cannot be loaded."""
    try:
        import Parameters as P0
    except Exception as e:                                  # syntax error, missing file ...
        print(Colour.red(f"ERROR   the parameter files cannot be loaded: {type(e).__name__}: {e}"))
        return None
    return P0


def prepare(P):
    """Check the parameters, build stator and rotor.  Returns (stator, rotor, report).
    Raises DesignError when there is an error."""
    import StatorGenerator as SG
    import RotorGenerator as RG
    rep = PC.check_parameters(P)
    if rep.errors:
        raise DesignError("parameter errors", rep, kind="parameters")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            stator = SG.StatorDesign(P)
    except (ValueError, RuntimeError) as e:
        rep.error(f"the stator cannot be built: {e}")
        raise DesignError("stator cannot be built", rep, kind="stator")
    rep.extend(PC.classify_generator_output(buf.getvalue()))
    try:
        rotor = RG.RotorDesign(P, stator=stator)
    except (ValueError, RuntimeError) as e:
        rep.error(f"the rotor cannot be built: {e}")
        raise DesignError("rotor cannot be built", rep, kind="rotor")
    design = PC.check_design(P, stator, rotor)
    rep.extend(design)
    if rep.errors:
        raise DesignError("design errors", rep)
    return stator, rotor, rep


# =============================================================================
# field of the TX turns: loop_bz(radius, r, z) and layer_depth(layer, P, prepreg) are shared with
# CoilElectrics.py (imported at the top), so that both use the same numbers
# =============================================================================


# =============================================================================
# the receiver coils as winding-number fields
# =============================================================================
def trace_net(stator, net, with_layers=False):
    """Ordered closed polyline (array of x, y) of the copper of one RX net.
    The traversal follows the series connection, so the sign of every segment is right.
    with_layers: also the layer of every piece (a list one shorter than the polyline)."""
    R5 = lambda v: round(float(v), 4)
    viaset = {(R5(v[0][0]), R5(v[0][1])) for v in stator.rx_vias if v[1] == net}

    def key(p, layer):
        k = (R5(p[0]), R5(p[1]))
        return (k, "V") if k in viaset else (k, layer)

    adj = collections.defaultdict(list)
    used = 0
    for i, (p, q, layer, n, _) in enumerate(stator.rx_segments):
        if n != net:
            continue
        a, b = key(p, layer), key(q, layer)
        adj[a].append((b, i))
        adj[b].append((a, i))
        used += 1
    if not adj:
        raise DesignError(f"net {net!r} has no copper")
    bad = [k for k, l in adj.items() if len(l) != 2]
    if bad:
        raise DesignError(f"net {net!r} is not a clean loop ({len(bad)} nodes with a number of connections other than 2)")
    start = next(iter(adj))
    path, cur, pe, seen, layers = [start], start, None, set(), []
    while True:
        nxt = next(((b, e) for b, e in adj[cur] if e != pe and e not in seen), None)
        if nxt is None:
            break
        seen.add(nxt[1])
        cur, pe = nxt[0], nxt[1]
        path.append(cur)
        layers.append(stator.rx_segments[nxt[1]][2])
        if cur == start:
            break
    if cur != start or len(seen) != used:
        raise DesignError(f"net {net!r} is not ONE closed series loop (traced {len(seen)} of {used} segments)")
    pts = np.array([k[0] for k in path], dtype=float)
    return (pts, layers) if with_layers else pts


_ZK1 = None


def _zk1_table():
    """Table of g(z) = z * K1(z) (K1 = modified Bessel function of the second kind), z = 0 ... 60.
    It is the shape of the field smoothing kernel in the azimuth/radius plane (see WindingGrid.blurred)."""
    global _ZK1
    if _ZK1 is None:
        z = np.arange(0.0, 60.0 + 1e-9, 0.005)
        g = np.ones_like(z)
        t = np.arange(0.0, 15.0, 0.01)
        ch = np.cosh(t)
        w = np.full_like(t, 0.01)
        w[0] = 0.005
        big = z > 0.05
        zb = z[big]
        out = np.empty_like(zb)
        for s0 in range(0, len(zb), 1500):
            zz = zb[s0:s0 + 1500]
            out[s0:s0 + 1500] = zz * (np.exp(-zz[:, None] * ch[None, :]) * (ch * w)[None, :]).sum(axis=1)
        g[big] = out
        zs = z[~big][1:]
        g[1:len(zs) + 1] = 1.0 + 0.5 * zs ** 2 * (np.log(zs / 2.0) + 0.5772156649015329 - 0.5)
        _ZK1 = (z, g)
    return _ZK1


class WindingGrid:
    """Winding number n(r, phi) of one closed polyline on a polar grid (radial bins x azimuth
    columns), plus its running integral along phi (so that the integral over any azimuth interval
    is two look-ups).  The flux through the coil of a radial field B(r) is  sum n * B * r dr dphi."""

    def __init__(self, points, cx, cy, r_edges, ncol):
        """points: one closed polyline (k, 2), or a list of them (their winding numbers add up)."""
        nr = len(r_edges) - 1
        dr = r_edges[1] - r_edges[0]
        loops = points if isinstance(points, (list, tuple)) else [points]
        p1, p2, r1, r2 = [], [], [], []
        for pts in loops:
            X, Y = pts[:, 0] - cx, pts[:, 1] - cy
            phi, r = np.arctan2(Y, X), np.hypot(X, Y)
            p1.append(phi[:-1]); p2.append(phi[1:]); r1.append(r[:-1]); r2.append(r[1:])
        p1, p2, r1, r2 = (np.concatenate(x) for x in (p1, p2, r1, r2))
        d = (p2 - p1 + math.pi) % (2.0 * math.pi) - math.pi
        delta = 2.0 * math.pi / ncol
        off = 1.234e-6                                    # keeps vertices off the column centres
        u1 = (p1 + math.pi - off) / delta - 0.5
        u2 = u1 + d / delta
        pos = d > 0
        first = np.where(pos, np.floor(u1) + 1.0, np.ceil(u2))
        cnt = np.where(pos, np.floor(u2) - np.floor(u1), np.ceil(u1) - np.ceil(u2)).astype(np.int64)
        cnt = np.maximum(cnt, 0)
        total = int(cnt.sum())
        e_idx = np.repeat(np.arange(len(d)), cnt)
        within = np.arange(total) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        j = first[e_idx].astype(np.int64) + within
        t = (j - u1[e_idx]) / (u2[e_idx] - u1[e_idx])
        rho = r1[e_idx] + (r2[e_idx] - r1[e_idx]) * t
        sgn = np.sign(d)[e_idx]
        jm = j % ncol
        m = np.clip(np.floor((rho - r_edges[0]) / dr).astype(np.int64), 0, nr - 1)
        frac = np.clip((rho - (r_edges[0] + m * dr)) / dr, 0.0, 1.0)
        S = np.zeros((ncol, nr))
        F = np.zeros((ncol, nr))
        np.add.at(S, (jm, m), sgn)
        np.add.at(F, (jm, m), sgn * frac)
        self.closure = float(np.abs(S.sum(axis=1)).max())
        if self.closure > 1e-9:
            raise DesignError("the receiver loop is not closed: signed crossings do not cancel around the axis")
        suffix = np.cumsum(S[:, ::-1], axis=1)[:, ::-1]
        self.n = suffix - S + F                          # (ncol, nr)
        self.delta = delta
        self.ncol, self.nr = ncol, nr
        centres = -math.pi + (np.arange(ncol) + 0.5) * delta + off
        self._centres = centres
        self._cum = {}
        self.rc = 0.5 * (r_edges[1:] + r_edges[:-1])
        self.dr = dr
        self._nhat = None

    def cum(self, comps):
        """Running integral along phi of n (comps = 1) and of n*cos(phi), n*sin(phi) (comps = 3).
        Shape (ncol + 1, nr, comps)."""
        if comps not in self._cum:
            parts = [self.n]
            if comps == 3:
                parts += [self.n * np.cos(self._centres)[:, None], self.n * np.sin(self._centres)[:, None]]
            arr = np.zeros((self.ncol + 1, self.nr, comps))
            for c, part in enumerate(parts):
                arr[1:, :, c] = np.cumsum(part * self.delta, axis=0)
            self._cum[comps] = arr
        return self._cum[comps]


def blur_grids(grids, distances, step):
    """Copies of the winding grids whose winding number is smoothed the way the rotor's field is
    smoothed on its way across the air gap.  The field below a plane obeys Laplace's equation, so a
    screen pattern is smoothed by the kernel  d / (2 pi (x^2 + y^2 + d^2)^(3/2))  over the distance d
    between the rotor and the copper (planar approximation: x = radius, y = r * phi).
    `distances` = rotor-to-copper distances of the layers that carry the coils; the result is
    averaged over them (half of the copper on each).  A rotor that repeats `step` times around the
    circle only couples to the azimuthal harmonics that are multiples of `step`, so only those are
    computed.  The radial resolution is halved for the smoothing (the kernel is much wider)."""
    g0 = grids[0]
    nm = g0.ncol // 2 + 1
    step = max(1, int(step))
    nr, dr = g0.nr, g0.dr
    rc = g0.rc
    if nr % 2:                                                    # pad to an even number of rows
        rc = np.concatenate([rc, [rc[-1] + dr]])
    rcc = 0.5 * (rc[0::2] + rc[1::2])                             # coarse rows
    nc = len(rcc)
    d_min = min(float(d) for d in distances)
    hmax = min((nm - 1) // step, int(math.ceil(9.0 * float(rcc.max()) / (step * d_min))))
    m = step * np.arange(hmax + 1)
    srcs = []
    for g in grids:
        if g._nhat is None:
            g._nhat = np.fft.rfft(g.n, axis=0)
        nh = g._nhat[m, :]
        if nr % 2:
            nh = np.concatenate([nh, np.zeros((nh.shape[0], 1), dtype=nh.dtype)], axis=1)
        srcs.append(0.5 * (nh[:, 0::2] + nh[:, 1::2]))            # (modes, coarse rows)
    ztab, gtab = _zk1_table()
    dxc2 = (rcc[None, :] - rcc[:, None]) ** 2
    accs = [np.zeros((hmax + 1, nc), dtype=complex) for _ in grids]
    for d in distances:
        a2 = dxc2 + float(d) ** 2
        a_over_r = np.sqrt(a2) / rcc[:, None]
        pre = float(d) / (math.pi * a2) * (2.0 * dr)
        for h in range(hmax + 1):
            kern = pre * np.interp(a_over_r * m[h], ztab, gtab)
            for acc, src in zip(accs, srcs):
                acc[h] += kern @ src[h]
    # back to the fine rows (linear interpolation of the smooth result)
    interp = np.zeros((g0.nr, nc))
    for i, r in enumerate(g0.rc):
        j = int(np.clip(np.searchsorted(rcc, r) - 1, 0, nc - 2))
        t = float(np.clip((r - rcc[j]) / (rcc[j + 1] - rcc[j]), 0.0, 1.0))
        interp[i, j], interp[i, j + 1] = 1.0 - t, t
    out = []
    for acc, g in zip(accs, grids):
        full = np.zeros((nm, g.nr), dtype=complex)
        full[m, :] = (acc / len(distances)) @ interp.T
        b = copy.copy(g)
        b.n = np.fft.irfft(full, n=g.ncol, axis=0)
        b._cum = {}
        out.append(b)
    return out


# =============================================================================
# the sensor model
# =============================================================================
def make_model(stator, rotor, P, rotor_model=None, **kw):
    """The sensor model for ROTOR_MODEL ("eddy" or "screen"); keywords as SensorModel."""
    kind = str(ROTOR_MODEL if rotor_model is None else rotor_model).lower()
    if kind == "eddy":
        import RotorEddyModel                               # (here: it imports this module)
        kw.pop("blur", None)
        return RotorEddyModel.EddySensorModel(stator, rotor, P, **kw)
    if kind == "screen":
        return SensorModel(stator, rotor, P, **kw)
    raise ValueError(f"rotor model {rotor_model!r}: must be \"eddy\" or \"screen\"")


class SensorModel:
    kind = "screen"

    def __init__(self, stator, rotor, P, prepreg=None, ncol=None, dr=None, blur=None, reach=None, true3d=None):
        """`reach` (mm, optional): the polar grid extends at least to this radius, so that set_rotor_extent()
        can move the rotor's outer edge anywhere inside it without rebuilding the model (and two models
        built with the same `reach` have exactly the same grid).  true3d: TRUE_3D_GEOMETRY for this model."""
        self.stator, self.rotor, self.P = stator, rotor, P
        self.blur = AIR_GAP_BLUR if blur is None else bool(blur)
        self.N = int(stator.N)
        if int(rotor.sectors) != self.N:
            raise DesignError(f"the rotor has {rotor.sectors} sector(s) but the stator has {self.N} loop(s); "
                              f"the analysis needs one rotor sector per loop (ROTOR_MODE = \"according_to_stator\" "
                              f"does that, or set ROTOR_CUSTOM_SECTORS = {self.N})")
        self.cx, self.cy = float(stator.cx), float(stator.cy)
        self.prepreg = STACKUP_PREPREG_MM if prepreg is None else prepreg
        self.ncol = int(ncol or AZIMUTH_COLUMNS)
        self.delta = 2.0 * math.pi / self.ncol
        nets = (P.RX_NET_PHASE_0_2, P.RX_NET_PHASE_1_3)
        self.paths = [trace_net(stator, n) for n in nets]
        rad = [np.hypot(p[:, 0] - self.cx, p[:, 1] - self.cy) for p in self.paths]
        lo = min(float(r.min()) for r in rad) - 0.25
        hi = max(float(r.max()) for r in rad) + 0.25
        lo = max(0.5, min(lo, float(rotor.r_in) - 0.5))          # the smoothed field also reaches the
        hi = max(hi, float(rotor.r_out) + 0.5)                    # rotor copper outside the coil band
        if reach is not None:
            hi = max(hi, float(reach))
        nr = max(40, int(math.ceil((hi - lo) / float(dr or RADIAL_STEP_MM))))
        self.r_edges = np.linspace(lo, hi, nr + 1)
        self.rc = 0.5 * (self.r_edges[1:] + self.r_edges[:-1])
        self.nr = nr
        self._rows = np.arange(nr)
        self.grids = [WindingGrid(p, self.cx, self.cy, self.r_edges, self.ncol) for p in self.paths]
        # TX turns: ring radii and the layer(s) they are on
        # (radius, depth, share of the current): the layers of the TX turns (TX_SERIES; parallel = two halves)
        self.tx_loops = [(float(R), layer_depth(l, P, self.prepreg), float(w))
                         for l, w in CE.tx_layers(stator, P) for R in stator.tx_radii]
        self.true3d = TRUE_3D_GEOMETRY if true3d is None else bool(true3d)
        self.tx_copper, self.layer_split, self.layer_grids = None, None, None
        self._direct = None
        self._chord = {}
        self.geometry_note = "ideal: TX as rings, receiver copper half on each RX layer"
        if self.true3d:
            depth_of = lambda l: layer_depth(l, P, self.prepreg)
            # the receiver coils: closed loops per layer (RealCopper.LayerSplit), each at its own depth
            self.layer_split, self.layer_grids = [], []
            for net in nets:
                pts, lays = trace_net(stator, net, with_layers=True)
                ls = RCU.LayerSplit(pts, lays, depth_of, base=stator.rising_layer, centre=(self.cx, self.cy))
                self.layer_split.append(ls)
                self.layer_grids.append([(WindingGrid(lp, self.cx, self.cy, self.r_edges, self.ncol), ls.depths[l])
                                         for l, lp in ls.loops.items()])
            # the TX from its real copper: the azimuthal average drives the rotor
            tx = RCU.TXCopper(stator, P, depth_of)
            if tx.ok:
                self.tx_copper = tx
                self.tx_loops = tx.rings()
                self.geometry_note = ("true 3-D: receiver traces at their layer depths, TX from its real copper "
                                      "(azimuthal average), direct TX-to-receiver coupling")
            else:
                self.geometry_note = (f"receiver traces at their layer depths; TX as ideal rings (its copper could not "
                                      f"be traced: {tx.why})")
        self._rg = np.linspace(lo, hi, 3001)
        self._weights = {}
        self.rx_depths = [layer_depth(l, P, self.prepreg) for l in (stator.rising_layer, stator.falling_layer)]
        self._views = {}
        self._profiles = {}
        # rotor
        self.Nrot = int(rotor.sectors)
        self.duty = float(rotor.duty)
        self.start = float(rotor.start_angle)
        self.r_in, self.r_out = float(rotor.r_in), float(rotor.r_out)

    # ------------------------------------------------------------------ field
    def _bz(self, r, gap):
        tot = np.zeros_like(r)
        for R, depth, w in self.tx_loops:
            tot += w * loop_bz(R, r, gap + depth)
        return tot

    def weights(self, gap):
        """Radial flux weights of the polar bins for an air gap: (field, field gradient in z)."""
        key = round(float(gap), 5)
        if key not in self._weights:
            rg, h = self._rg, 0.02
            B = self._bz(rg, gap)
            dB = (self._bz(rg, gap + h) - self._bz(rg, max(gap - h, 1e-3))) / (gap + h - max(gap - h, 1e-3))
            def cumint(f):
                return np.concatenate([[0.0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(rg))])
            G0, G1 = cumint(B * rg), cumint(dB * rg * rg)
            self._weights[key] = (np.diff(np.interp(self.r_edges, rg, G0)),
                                  np.diff(np.interp(self.r_edges, rg, G1)))
        return self._weights[key]

    def grids_at(self, gap):
        """The receiver winding fields as seen from a rotor at this air gap."""
        if not self.blur:
            return self.grids
        key = round(float(gap), 5)
        if key not in self._views:
            if self.layer_grids is None:
                self._views[key] = blur_grids(self.grids, [float(gap) + d for d in self.rx_depths], self.Nrot)
            else:
                self._views[key] = self.layer_blur(float(gap), self.Nrot)
        return self._views[key]

    def layer_blur(self, height, step):
        """The receiver winding fields smoothed from the plane `height` above the top copper: every per-layer loop
        over its own distance (height + its depth), summed per coil."""
        groups = collections.defaultdict(list)                   # depth -> [(coil, grid)]: one kernel per depth
        for c, gl in enumerate(self.layer_grids):
            for g, z in gl:
                groups[round(float(z), 9)].append((c, g))
        out = [None] * len(self.layer_grids)
        for z, items in groups.items():
            for (c, _g), b in zip(items, blur_grids([g for _c, g in items], [height + z], step)):
                if out[c] is None:
                    out[c] = b
                else:
                    out[c].n = out[c].n + b.n
        for b in out:
            b._cum = {}
        return out

    # ------------------------------------------------------------ real copper extras
    def chord_field(self, coil, height):
        """RealCopper.LayerSplit remainder of a receiver coil (its chords at two depths) as a normal field at the plane
        `height` above the top copper, on the model's polar grid (B~ units: mu0 / 4 pi per ampere).  Computed on a
        grid of every CHORD_STRIDE[0]-th column and CHORD_STRIDE[1]-th row and interpolated (the remainder is smooth
        on that scale: it comes from copper at least the air gap away)."""
        key = (coil, round(float(height), 6))
        if key not in self._chord:
            ls = self.layer_split[coil]
            sc, sr = CHORD_STRIDE
            while self.ncol % sc:
                sc -= 1
            cols = self.grids[0]._centres[::sc]
            rows = np.concatenate([self.rc[::sr], self.rc[-1:]]) if (self.nr - 1) % sr else self.rc[::sr]
            PH, RR = np.meshgrid(cols, rows, indexing="ij")
            f = ls.chord_field((self.cx + RR * np.cos(PH)).ravel(), (self.cy + RR * np.sin(PH)).ravel(), float(height))
            D = f.reshape(PH.shape)
            Dr = np.empty((D.shape[0], self.nr))
            for j in range(D.shape[0]):
                Dr[j] = np.interp(self.rc, rows, D[j])
            # columns: periodic linear interpolation from every 4th column
            u = np.arange(self.ncol) / float(sc)
            j0 = np.floor(u).astype(np.int64) % D.shape[0]
            j1 = (j0 + 1) % D.shape[0]
            t = (u - np.floor(u))[:, None]
            full = Dr[j0] * (1.0 - t) + Dr[j1] * t
            if len(self._chord) > 24:
                self._chord.pop(next(iter(self._chord)))
            self._chord[key] = full
        return self._chord[key]

    def tx_ripple_field(self, gap):
        """What the TX's real copper adds to the field of its azimuthal average at the rotor plane (steps, tails, gaps,
        go-around runs and brackets), on the model's polar grid, in model units (mu0 / 2 pi per ampere).  Computed
        on a coarser grid (every RIPPLE_STRIDE-th column; rows every 0.3 mm near the TX, every 1 mm farther inside)
        and interpolated."""
        key = round(float(gap), 6)
        cache = self.__dict__.setdefault("_ripple_field", {})
        if key not in cache:
            sc = RIPPLE_STRIDE
            while self.ncol % sc:
                sc -= 1
            r_tx = float(self.stator.tx_first_radius)
            fine = self.rc >= r_tx - 3.5
            rows = np.unique(np.concatenate([self.rc[~fine][::10], self.rc[fine][::3], self.rc[-1:], self.rc[:1]]))
            cols = self.grids[0]._centres[::sc]
            PH, RR = np.meshgrid(cols, rows, indexing="ij")
            f = RCU.tx_deviation_bz(self.tx_copper, (self.cx, self.cy), (self.cx + RR * np.cos(PH)).ravel(),
                                    (self.cy + RR * np.sin(PH)).ravel(), float(gap), reach=RIPPLE_REACH_MM)
            D = 0.5 * f.reshape(PH.shape)                                   # B~ -> model units
            Dr = np.array([np.interp(self.rc, rows, d) for d in D])
            u = np.arange(self.ncol) / float(sc)
            j0 = np.floor(u).astype(np.int64) % D.shape[0]
            t = (u - np.floor(u))[:, None]
            cache[key] = Dr[j0] * (1.0 - t) + Dr[(j0 + 1) % D.shape[0]] * t
            if len(cache) > 8:
                cache.pop(next(iter(cache)))
        return cache[key]

    def ripple_profiles(self, gap, rotor_reach=True):
        """Running integrals along the azimuth (per coil, like _profile) of what the TX ripple field adds to the signal
        of a centred rotor, to first order: the rotor copper keeps that field off the receiver coils (ideal screen,
        the receiver winding smoothed from the rotor plane).  None without the real TX copper."""
        if self.tx_copper is None:
            return None
        key = (round(float(gap), 6), bool(rotor_reach), round(self.r_in, 9), round(self.r_out, 9))
        cache = self.__dict__.setdefault("_ripple_prof", {})
        if key not in cache:
            dB = self.tx_ripple_field(gap)
            wr = self._radial_window(0.0, rotor_reach) * self.rc * (self.r_edges[1] - self.r_edges[0])
            out = []
            for g in self.layer_blur(float(gap), 1):
                f = (g.n * dB) @ wr
                out.append(np.concatenate([[0.0], np.cumsum(f * self.delta)]))
            if len(cache) > 8:
                cache.pop(next(iter(cache)))
            cache[key] = out
        return cache[key]

    def profile_signals(self, profiles, theta, duty):
        """-(integral of a profile over the rotor copper) for the rotor angles theta: per coil an array (len(duty),
        len(theta)), or (len(theta),) for a single duty."""
        d = np.atleast_1d(np.asarray(duty, dtype=float))
        T = 2.0 * math.pi / self.Nrot
        theta = np.asarray(theta, dtype=float)
        alpha = theta[None, :, None] + self.start + (np.arange(self.Nrot) * T)[None, None, :]
        beta = alpha + d[:, None, None] * T
        twopi = 2.0 * math.pi
        ua = ((alpha + math.pi) % twopi) / self.delta
        ub = ((beta + math.pi) % twopi) / self.delta
        ja = np.minimum(ua.astype(np.int64), self.ncol - 1)
        jb = np.minimum(ub.astype(np.int64), self.ncol - 1)
        fa, fb = ua - ja, ub - jb
        wrap = (ub < ua)
        out = []
        for cw in profiles:
            Ca = cw[ja] * (1.0 - fa) + cw[ja + 1] * fa
            Cb = cw[jb] * (1.0 - fb) + cw[jb + 1] * fb
            v = -(Cb - Ca + wrap * cw[-1]).sum(axis=-1)
            out.append(v if np.ndim(duty) else v[0])
        return out

    def ripple(self, theta, gap, duty=None, rotor_reach=True):
        """The TX ripple part of the receiver signals (see ripple_profiles): two arrays, or zeros."""
        prof = self.ripple_profiles(gap, rotor_reach)
        duty = self.duty if duty is None else duty
        if prof is None:
            z = np.zeros(np.shape(np.atleast_1d(duty)) + np.shape(theta)) if np.ndim(duty) else np.zeros(np.shape(theta))
            return z, z
        v = self.profile_signals(prof, theta, duty)
        return v[0], v[1]

    def direct(self):
        """The direct TX-to-receiver coupling without a rotor, for each coil (model units): the Neumann double line
        integral over the real copper of the TX and of the receiver coil (vias included).  An ideal sensor has none;
        it adds a constant to the receiver signal (an offset).  0 with TRUE_3D_GEOMETRY = False."""
        if self._direct is None:
            if self.tx_copper is None:
                self._direct = (0.0, 0.0)
            else:
                At, Bt, It = self.tx_copper.pieces3()
                vals = []
                for ls in self.layer_split:
                    Ar, Br = ls.pieces3
                    vals.append(0.5 * RCU.neumann(Ar, Br, At, Bt, It))     # mu0 / 4 pi x mm -> model units
                self._direct = tuple(vals)
        return self._direct

    # ------------------------------------------------------------------ rotor
    def set_rotor_extent(self, r_in=None, r_out=None):
        """Move the radial edges of the rotor copper (mm) without rebuilding the model; used to scan the
        outer edge.  The polar grid must cover the new extent (see `reach`)."""
        r_in = self.r_in if r_in is None else float(r_in)
        r_out = self.r_out if r_out is None else float(r_out)
        if not 0.0 < r_in < r_out:
            raise ValueError("the rotor's inner radius must be smaller than its outer radius")
        if r_in - 0.25 < self.r_edges[0] or r_out + 0.25 > self.r_edges[-1]:
            raise ValueError(f"the rotor copper ({r_in:.2f} ... {r_out:.2f} mm) reaches outside the model's "
                             f"polar grid ({self.r_edges[0]:.2f} ... {self.r_edges[-1]:.2f} mm): build the "
                             f"model with reach=...")
        self.r_in, self.r_out = r_in, r_out
        self._profiles = {}                                       # they depend on the radial window

    def _radial_window(self, e, covered=True):
        """Fraction of every radial bin that the rotor copper reaches (eccentric: averaged)."""
        a, b = self.r_edges[:-1], self.r_edges[1:]

        def frac(lo, hi):
            return np.clip((np.minimum(b, hi) - np.maximum(a, lo)) / (b - a), 0.0, 1.0)
        if not covered:
            return np.ones(self.nr)
        if e <= 0.0:
            return frac(self.r_in, self.r_out)
        return 0.5 * (frac(self.r_in + e, self.r_out - e) + frac(self.r_in - e, self.r_out + e))

    @staticmethod
    def _azimuth(alpha, rc, ecc):
        """Azimuth (stator frame) of the rotor-frame ray `alpha` at stator radius rc, for a rotor
        whose axis is offset by ecc = (dx, dy)."""
        dx, dy = ecc
        if dx == 0.0 and dy == 0.0:
            return alpha[..., None]
        ux, uy = np.cos(alpha)[..., None], np.sin(alpha)[..., None]
        cu = dx * ux + dy * uy
        s = -cu + np.sqrt(np.maximum(cu * cu + rc * rc - (dx * dx + dy * dy), 0.0))
        return np.arctan2(dy + s * uy, dx + s * ux)

    def _cover(self, grid, pa, pb, comps):
        """Integral of n (and n cos, n sin) over the azimuth intervals [pa, pb] of all sectors
        -> (n_theta, n_r, comps), summed over the sectors."""
        cum = grid.cum(comps)
        tot = cum[-1]
        twopi = 2.0 * math.pi
        ua = ((pa + math.pi) % twopi) / self.delta
        ub = ((pb + math.pi) % twopi) / self.delta
        ja = np.minimum(ua.astype(np.int64), self.ncol - 1)
        jb = np.minimum(ub.astype(np.int64), self.ncol - 1)
        fa = (ua - ja)[..., None]
        fb = (ub - jb)[..., None]
        rows = self._rows
        Ca = cum[ja, rows] * (1.0 - fa) + cum[ja + 1, rows] * fa
        Cb = cum[jb, rows] * (1.0 - fb) + cum[jb + 1, rows] * fb
        wrap = (ub < ua)[..., None]
        cov = Cb - Ca + wrap * tot[rows]
        return cov.sum(axis=1)

    def signals(self, theta, gap=None, ecc=(0.0, 0.0), tilt=None, duty=None, rotor_reach=True):
        """Receiver voltages (relative units) at the rotor angles `theta` (rad, mechanical).
        ecc = (dx, dy) mm; tilt = (degrees, direction_deg, "stator" | "rotor") or None."""
        P = self.P
        gap = float(P.AIR_GAP_MM if gap is None else gap)
        duty = self.duty if duty is None else float(duty)
        Bw0, Bw1 = self.weights(gap)
        e = math.hypot(*ecc)
        w = self._radial_window(e, rotor_reach)
        use_tilt = tilt is not None and tilt[0] != 0.0
        comps = 3 if use_tilt else 1
        T = 2.0 * math.pi / self.Nrot
        ks = np.arange(self.Nrot) * T
        theta = np.asarray(theta, dtype=float)
        out = np.zeros((2, len(theta)))
        per = max(1, int(2.0e6 // (self.Nrot * self.nr * comps)))
        kappa = math.tan(math.radians(tilt[0])) if use_tilt else 0.0
        for s in range(0, len(theta), per):
            th = theta[s:s + per]
            alpha = th[:, None] + self.start + ks[None, :]
            beta = alpha + duty * T
            pa = self._azimuth(alpha, self.rc, ecc)
            pb = self._azimuth(beta, self.rc, ecc)
            for gi, grid in enumerate(self.grids_at(gap)):
                cov = self._cover(grid, pa, pb, comps)
                v = cov[:, :, 0] @ (w * Bw0)
                if use_tilt:
                    psi = math.radians(tilt[1]) + (th if tilt[2] == "rotor" else 0.0)
                    v = v + kappa * (np.cos(psi) * (cov[:, :, 1] @ (w * Bw1))
                                     + np.sin(psi) * (cov[:, :, 2] @ (w * Bw1)))
                out[gi, s:s + len(th)] = -v
        dc = self.direct()
        rs, rc_ = self.ripple(theta, gap, duty, rotor_reach)          # (first order, as for a centred rotor)
        return out[0] + dc[0] + rs, out[1] + dc[1] + rc_

    def signal_parts(self, theta, gap=None, ecc=(0.0, 0.0), duty=None, rotor_reach=True):
        """The receiver voltages of an eccentric rotor split into the part without tilt and the two tilt
        terms: an array (2 coils, 3, len(theta)).  A tilt of `a` degrees in the direction psi (rad, in the
        stator frame; for a tilt that turns with the rotor, psi = direction + rotor angle) gives
            V = part[:, 0] + tan(a) * (cos(psi) * part[:, 1] + sin(psi) * part[:, 2])
        which is exactly what signals() computes, but every tilt direction and both frames come from one
        simulation."""
        P = self.P
        gap = float(P.AIR_GAP_MM if gap is None else gap)
        duty = self.duty if duty is None else float(duty)
        Bw0, Bw1 = self.weights(gap)
        w = self._radial_window(math.hypot(*ecc), rotor_reach)
        T = 2.0 * math.pi / self.Nrot
        ks = np.arange(self.Nrot) * T
        theta = np.asarray(theta, dtype=float)
        out = np.zeros((2, 3, len(theta)))
        per = max(1, int(2.0e6 // (self.Nrot * self.nr * 3)))
        for s in range(0, len(theta), per):
            th = theta[s:s + per]
            alpha = th[:, None] + self.start + ks[None, :]
            beta = alpha + duty * T
            pa = self._azimuth(alpha, self.rc, ecc)
            pb = self._azimuth(beta, self.rc, ecc)
            for gi, grid in enumerate(self.grids_at(gap)):
                cov = self._cover(grid, pa, pb, 3)
                out[gi, 0, s:s + len(th)] = -(cov[:, :, 0] @ (w * Bw0))
                out[gi, 1, s:s + len(th)] = -(cov[:, :, 1] @ (w * Bw1))
                out[gi, 2, s:s + len(th)] = -(cov[:, :, 2] @ (w * Bw1))
        dc = self.direct()
        rs, rc_ = self.ripple(theta, gap, duty, rotor_reach)          # (first order, as for a centred rotor)
        out[0, 0] += dc[0] + rs
        out[1, 0] += dc[1] + rc_
        return out

    def _profile(self, gap, rotor_reach=True):
        """Running integral over the azimuth of the radially weighted winding field (centred rotor)."""
        key = (round(float(gap), 5), bool(rotor_reach))
        if key not in self._profiles:
            Bw0, _ = self.weights(gap)
            wt = self._radial_window(0.0, rotor_reach) * Bw0
            prof = [g.cum(1)[:, :, 0] @ wt for g in self.grids_at(gap)]
            rp = self.ripple_profiles(gap, rotor_reach)
            if rp is not None:
                prof = [p + q for p, q in zip(prof, rp)]
            self._profiles[key] = prof
        return self._profiles[key]

    def signals_centred(self, theta, gap=None, duty=None, rotor_reach=True):
        """Same result as signals() for a centred, untilted rotor, but much faster, and `duty` may be an
        array: the result then has the shape (len(duty), len(theta)) for each coil."""
        gap = float(self.P.AIR_GAP_MM if gap is None else gap)
        duty = self.duty if duty is None else duty
        d = np.atleast_1d(np.asarray(duty, dtype=float))
        T = 2.0 * math.pi / self.Nrot
        theta = np.asarray(theta, dtype=float)
        alpha = theta[None, :, None] + self.start + (np.arange(self.Nrot) * T)[None, None, :]
        beta = alpha + d[:, None, None] * T
        twopi = 2.0 * math.pi
        ua = ((alpha + math.pi) % twopi) / self.delta
        ub = ((beta + math.pi) % twopi) / self.delta
        ja = np.minimum(ua.astype(np.int64), self.ncol - 1)
        jb = np.minimum(ub.astype(np.int64), self.ncol - 1)
        fa, fb = ua - ja, ub - jb
        wrap = (ub < ua)
        out = []
        for cw in self._profile(gap, rotor_reach):
            Ca = cw[ja] * (1.0 - fa) + cw[ja + 1] * fa
            Cb = cw[jb] * (1.0 - fb) + cw[jb + 1] * fb
            v = -(Cb - Ca + wrap * cw[-1]).sum(axis=-1)
            out.append(v if np.ndim(duty) else v[0])
        dc = self.direct()
        return out[0] + dc[0], out[1] + dc[1]

    # ------------------------------------------------------------ conveniences
    def theta_period(self, n):
        return np.arange(n) * (2.0 * math.pi / self.N) / n

    def theta_turn(self, per_period):
        return np.arange(self.N * per_period) * (2.0 * math.pi / self.N) / per_period


# =============================================================================
# signal analysis
# =============================================================================
def _fit(V, x, H):
    cols = [np.ones_like(x)]
    for h in range(1, H + 1):
        cols += [np.cos(h * x), np.sin(h * x)]
    A = np.column_stack(cols)
    c, *_ = np.linalg.lstsq(A, V, rcond=None)
    resid = V - A @ c
    return c, resid


def _line_error(y, x):
    """Deviation (deg) of the unwrapped electrical angle y (rad) from the ideal line  +-x + offset.
    The slope of an N-fold periodic sensor is exactly one electrical turn per period, so it is NOT
    fitted (a fitted slope would hide part of the real error); only a constant offset is trimmed,
    chosen to make the peak as small as possible.  Returns (peak, rms, error curve, fitted slope)."""
    y = np.unwrap(y)
    A = np.column_stack([x, np.ones_like(x)])
    sol, *_ = np.linalg.lstsq(A, y, rcond=None)         # only used to learn the sign / sanity of the slope
    sgn = 1.0 if sol[0] >= 0 else -1.0
    d = np.degrees(y - sgn * x)
    err = d - 0.5 * (d.max() + d.min())
    return float(np.abs(err).max()), float(np.sqrt(np.mean((d - d.mean()) ** 2))), err, float(sol[0])


def analyse_signals(Vs, Vc, x, H=HARMONICS):
    """Metrics of a sin/cos pair sampled at electrical angles x (rad, may span many periods)."""
    cs, rs = _fit(Vs, x, H)
    cc, rc_ = _fit(Vc, x, H)
    As, Ac = math.hypot(cs[1], cs[2]), math.hypot(cc[1], cc[2])
    ps, pc = math.atan2(cs[2], cs[1]), math.atan2(cc[2], cc[1])
    hd = []
    for h in range(2, H + 1):
        hs = math.hypot(cs[2 * h - 1], cs[2 * h]) / As * 100.0
        hc = math.hypot(cc[2 * h - 1], cc[2 * h]) / Ac * 100.0
        hd.append(max(hs, hc))
    delta = (pc - ps + math.pi) % (2.0 * math.pi) - math.pi
    # nothing removed: what the receiver sees with no calibration at all (offsets included)
    pk_none, rms_none, _, _ = _line_error(np.arctan2(Vs, Vc), x)
    # raw: only the offsets removed
    y_raw = np.arctan2(Vs - Vs.mean(), Vc - Vc.mean())
    pk_raw, rms_raw, _, slope = _line_error(y_raw, x)
    # calibrated: offset, amplitude and quadrature removed (from the fundamentals)
    sc = (Vs - cs[0]) / As
    ccn = (Vc - cc[0]) / Ac
    sd = math.sin(delta)
    if abs(sd) < 1e-6:
        pk_cal, rms_cal, err_cal = float("nan"), float("nan"), np.zeros_like(x)
    else:
        y_cal = np.arctan2((ccn - sc * math.cos(delta)) / sd, sc)
        pk_cal, rms_cal, err_cal, _ = _line_error(y_cal, x)
    return dict(amp_s=As, amp_c=Ac, amp_ratio=Ac / As, dc_s=cs[0] / As * 100.0, dc_c=cc[0] / Ac * 100.0,
                quad=abs(math.degrees(delta)) - 90.0, hd=hd,
                none_peak=pk_none, none_rms=rms_none, raw_peak=pk_raw, raw_rms=rms_raw, cal_peak=pk_cal, cal_rms=rms_cal, slope=slope,
                err_curve=err_cal,
                nonharm_s=float(np.sqrt(np.mean(rs ** 2)) / As * 100.0))


def analyse_batch(Vs, Vc, x, H=HARMONICS):
    """The calibrated peak angle error (deg el) and the signal amplitude of many sin/cos pairs at once:
    Vs, Vc have the shape (n, len(x)).  Gives for every row the same numbers as
    analyse_signals(...)["cal_peak"] and ["amp_s"] (NaN where the two fundamentals are parallel), much
    faster; OptimizeCoil.py uses it to screen thousands of candidates."""
    x = np.asarray(x, dtype=float)
    cols = [np.ones_like(x)]
    for h in range(1, H + 1):
        cols += [np.cos(h * x), np.sin(h * x)]
    pinv_t = np.linalg.pinv(np.column_stack(cols)).T                       # (len(x), 1 + 2H)
    cs, cc = Vs @ pinv_t, Vc @ pinv_t                                       # fitted Fourier coefficients
    As, Ac = np.hypot(cs[:, 1], cs[:, 2]), np.hypot(cc[:, 1], cc[:, 2])
    delta = (np.arctan2(cc[:, 2], cc[:, 1]) - np.arctan2(cs[:, 2], cs[:, 1]) + math.pi) % (2.0 * math.pi) - math.pi
    sd = np.sin(delta)
    ok = np.abs(sd) >= 1e-6
    sc = (Vs - cs[:, :1]) / As[:, None]
    ccn = (Vc - cc[:, :1]) / Ac[:, None]
    y = np.arctan2((ccn - sc * np.cos(delta)[:, None]) / np.where(ok, sd, 1.0)[:, None], sc)
    y = np.unwrap(y, axis=1)
    sgn = np.where((y @ (x - x.mean())) >= 0.0, 1.0, -1.0)                 # sign of the fitted slope
    d = np.degrees(y - sgn[:, None] * x[None, :])
    err = d - 0.5 * (d.max(axis=1, keepdims=True) + d.min(axis=1, keepdims=True))
    peak = np.abs(err).max(axis=1)
    return np.where(ok, peak, np.nan), As


class Analysis:
    """One evaluated condition."""

    def __init__(self, label, metrics, x, Vs, Vc, theta):
        self.label, self.m, self.x, self.Vs, self.Vc, self.theta = label, metrics, x, Vs, Vc, theta

    @property
    def peak(self):
        return self.m["cal_peak"]


def evaluate(model, label="", gap=None, ecc=None, tilt=None, duty=None, per=None, rotor_reach=True):
    """Simulate one condition.  ecc = (e_mm, direction_deg); tilt = (deg, direction_deg, frame)."""
    e_vec = (0.0, 0.0)
    if ecc is not None and ecc[0] > 0.0:
        e_vec = (ecc[0] * math.cos(math.radians(ecc[1])), ecc[0] * math.sin(math.radians(ecc[1])))
    t_arg = tilt if (tilt is not None and tilt[0] > 0.0) else None
    whole_turn = e_vec != (0.0, 0.0) or t_arg is not None
    if whole_turn:
        theta = model.theta_turn(per or SAMPLES_PER_PERIOD_TOL)
    else:
        theta = model.theta_period(per or SAMPLES_PER_PERIOD)
    if whole_turn:
        Vs, Vc = model.signals(theta, gap=gap, ecc=e_vec, tilt=t_arg, duty=duty, rotor_reach=rotor_reach)
    else:
        Vs, Vc = model.signals_centred(theta, gap=gap, duty=duty, rotor_reach=rotor_reach)
    x = model.N * theta
    a = Analysis(label, analyse_signals(Vs, Vc, x), x, Vs, Vc, theta)
    a.gap = float(model.P.AIR_GAP_MM if gap is None else gap)
    a.duty = model.duty if duty is None else float(duty)
    return a


def _sweep(model, gap, ecc_mm, tilt_deg, ndir, duty, per):
    """The worst case of eccentricity and/or tilt at one air gap.  Every tilt direction (TILT_DIRECTIONS),
    both kinds of tilt (turning with the rotor, or fixed to the stator) and ndir eccentricity directions
    are tried.  The tilt acts linearly, so one simulation per eccentricity direction gives all the tilt
    cases.  (An eccentric rotor with a tilt that turns with it leaves an error that repeats once per
    turn although each one alone hardly changes anything, so the tolerances cannot be tried one at a
    time.)  Everything repeats after one loop pitch (360/N deg) when eccentricity and tilt are turned
    together, so the eccentricity directions are spread over one pitch only.  Returns (Analysis of the
    worst case, [(description, peak error), ...] of everything tried)."""
    theta = model.theta_turn(per)
    x = model.N * theta
    use_t = tilt_deg > 0
    edirs = [360.0 / model.N * i / ndir for i in range(ndir)] if ecc_mm > 0 else [None]
    tilts = ([(f, 360.0 * i / TILT_DIRECTIONS) for f in ("stator", "rotor") for i in range(TILT_DIRECTIONS)]
             if use_t else [None])
    kappa = math.tan(math.radians(tilt_deg)) if use_t else 0.0
    tried, best = [], None
    for ed in edirs:
        e_vec = (0.0, 0.0) if ed is None else (ecc_mm * math.cos(math.radians(ed)),
                                               ecc_mm * math.sin(math.radians(ed)))
        if use_t:
            parts = model.signal_parts(theta, gap=gap, ecc=e_vec, duty=duty)
            Vs = np.empty((len(tilts), len(theta)))
            Vc = np.empty_like(Vs)
            for r, (frame, d) in enumerate(tilts):
                psi = math.radians(d) + (theta if frame == "rotor" else 0.0)
                c, s = np.cos(psi), np.sin(psi)
                Vs[r] = parts[0, 0] + kappa * (c * parts[0, 1] + s * parts[0, 2])
                Vc[r] = parts[1, 0] + kappa * (c * parts[1, 1] + s * parts[1, 2])
        else:
            v0, v1 = model.signals(theta, gap=gap, ecc=e_vec, duty=duty)
            Vs, Vc = v0[None, :], v1[None, :]
        peaks, _ = analyse_batch(Vs, Vc, x)
        for r, p in enumerate(peaks):
            text = []
            if ed is not None:
                text.append(f"eccentricity {ecc_mm:g} mm, direction {ed:g} deg")
            if use_t:
                text.append(f"tilt {tilt_deg:g} deg ({tilts[r][0]}-fixed), direction {tilts[r][1]:g} deg")
            tried.append((", ".join(text), float(p)))
        r_best = int(np.argmax(np.where(np.isnan(peaks), -np.inf, peaks)))
        if best is None or peaks[r_best] > best[0]:
            best = (float(peaks[r_best]), tried[len(tried) - len(peaks) + r_best][0], Vs[r_best].copy(), Vc[r_best].copy())
    _, text, Vs, Vc = best
    a = Analysis(text, analyse_signals(Vs, Vc, x), x, Vs, Vc, theta)
    a.dirs = tried
    a.gap = float(gap)
    a.duty = model.duty if duty is None else float(duty)
    return a, tried


def tolerance_window(model, gap_tol, ecc_mm, tilt_deg, ndir, per=None, duty=None, whole_turn_per=None, duty_tol=None):
    """Evaluate the tolerance window.  Returns a list of Analysis (first = nominal); every row has
    .kind in {"nominal", "gap", "duty", "ecc", "tilt", "combo"}."""
    P = model.P
    g0 = float(P.AIR_GAP_MM)
    g_lo, g_hi = max(g0 - gap_tol, 0.1), g0 + gap_tol
    wt = whole_turn_per or SAMPLES_PER_PERIOD_TOL

    def tag(a, kind):
        a.kind = kind
        return a

    rows = [tag(evaluate(model, f"nominal (gap {g0:g} mm, rotor centred)", duty=duty, per=per), "nominal")]
    if gap_tol > 0:
        rows.append(tag(evaluate(model, f"gap {g_lo:g} mm", gap=g_lo, duty=duty, per=per), "gap"))
        rows.append(tag(evaluate(model, f"gap {g_hi:g} mm", gap=g_hi, duty=duty, per=per), "gap"))
    d0 = model.duty if duty is None else float(duty)
    dt = ROTOR_DUTY_TOLERANCE if duty_tol is None else float(duty_tol)
    if dt > 0:
        corners = []
        for g in ([g0] + ([g_lo, g_hi] if gap_tol > 0 else [])):
            for sgn in (-1.0, 1.0):
                if 0.01 < d0 + sgn * dt < 0.99:
                    corners.append((evaluate(model, "", gap=g, duty=d0 + sgn * dt, per=per), g, d0 + sgn * dt))
        if corners:
            a, g, dd = max(corners, key=lambda c: c[0].peak)
            a.label = f"rotor metal fraction {d0:.4g} +/- {dt:g}  (worst: {dd:.4g} at gap {g:g} mm)"
            rows.append(tag(a, "duty"))
    if ecc_mm > 0:
        a, _ = _sweep(model, g0, ecc_mm, 0.0, ndir, duty, wt)
        rows.append(tag(a, "ecc"))
    if tilt_deg > 0:
        a, _ = _sweep(model, g0, 0.0, tilt_deg, ndir, duty, wt)
        rows.append(tag(a, "tilt"))
    # eccentricity and tilt together (and at the extreme air gaps): the worst of all the combinations
    if ecc_mm > 0 or tilt_deg > 0:
        for g in ([g_lo, g_hi] if gap_tol > 0 else []):
            a, _ = _sweep(model, g, ecc_mm, tilt_deg, ndir, duty, wt)
            a.detail, a.label = a.label, f"worst eccentric/tilted case at gap {g:g} mm"
            rows.append(tag(a, "combo"))
        if ecc_mm > 0 and tilt_deg > 0:
            a, _ = _sweep(model, g0, ecc_mm, tilt_deg, ndir, duty, wt)
            a.detail, a.label = a.label, "worst eccentricity + tilt together"
            rows.append(tag(a, "combo"))
    return rows


# =============================================================================
# report
# =============================================================================
def hints(m, N, P):
    """Plain suggestions from the largest harmonic (theory only; OptimizeCoil.py tests them)."""
    hd = m["hd"]
    h_big = int(np.argmax(hd)) + 2
    if hd[h_big - 2] < 0.05 or h_big % 2 == 0:
        return []
    out = [f"the largest harmonic is HD{h_big} = {hd[h_big - 2]:.2f} %"]
    out.append("the rotor metal fraction moves it (a copper pattern of fraction k/h has no h-th harmonic, but "
               "the field the eddy currents leave does: the best fraction is found by searching)")
    splits = [d for d in ((180.0 + 360.0 * k) / h_big for k in range(h_big)) if 30.0 <= d <= 60.0]
    if splits:
        out.append(f"two sub-coils split {splits[0]:.0f} electrical degrees apart remove it; if that split does not "
                   f"fit the board (clearance), a few degrees less still removes most of it")
    out.append("python OptimizeCoil.py tries the metal fraction, the sub-coils, the coil profiles and where the "
               "rotor copper ends on the outside, together, and ranks them")
    return out


def print_nominal(model, a, P):
    m, N = a.m, model.N
    print(Colour.bold("NOMINAL  (air gap %g mm, rotor centred)" % float(P.AIR_GAP_MM)))
    print(f"  signal amplitude       {m['amp_s']:.4g} (relative units)   sin/cos match {m['amp_ratio']:.4f}")
    print(f"  DC offset              sin {m['dc_s']:+.3f} %   cos {m['dc_c']:+.3f} %")
    print(f"  quadrature error       {m['quad']:+.3f} deg")
    print("  harmonics              " + "  ".join(f"HD{h} {v:.2f}%" for h, v in zip(range(2, 2 + len(m['hd'])), m['hd'])))
    print(f"  angle error, nothing removed            peak {m['none_peak']:.3f} deg el   rms {m['none_rms']:.3f}")
    print(f"  angle error, offset removed only        peak {m['raw_peak']:.3f} deg el   rms {m['raw_rms']:.3f}")
    print(f"  angle error, offset+gain+quadrature     peak {m['cal_peak']:.3f} deg el   rms {m['cal_rms']:.3f}   "
          f"= {m['cal_peak'] / N:.4f} deg mech = {m['cal_peak'] / 360.0 * 100:.3f} % of the {360.0 / N:g} deg range")
    for h in hints(m, N, P):
        print("  " + Colour.dim("hint: " + h))


def sensitivity(rows):
    """Relative increase of the peak error caused by each kind of tolerance (max over its rows)."""
    base = rows[0].peak
    out = {}
    for kind in ("gap", "duty", "ecc", "tilt", "combo"):
        sel = [a.peak for a in rows if getattr(a, "kind", "") == kind]
        if sel and base > 0:
            out[kind] = max(sel) / base - 1.0
    return out


def print_window(rows, N, ecc_mm, tilt_deg, gap_tol, duty_tol=0.0):
    print()
    print(Colour.bold("TOLERANCE WINDOW  (peak angle error after offset/gain/quadrature calibration)"))
    print(f"  assumed: gap +/- {gap_tol:g} mm, rotor metal fraction +/- {duty_tol:g}, eccentricity {ecc_mm:g} mm, "
          f"tilt {tilt_deg:g} deg")
    print(Colour.dim("           (change with --gap-tol --duty-tol --ecc --tilt, or at the top of AnalyzeCoil.py)"))
    worst = max(rows, key=lambda a: a.peak)
    base = rows[0].peak
    for a in rows:
        mark = " <- worst" if a is worst and len(rows) > 1 else ""
        line = (f"  {a.label:<58s} {a.peak:7.3f} deg el   ({a.peak / N:.4f} deg mech)   "
                f"amp {a.m['amp_s'] / rows[0].m['amp_s']:.3f}x{mark}")
        print(Colour.yellow(line) if mark else line)
        if hasattr(a, "detail"):
            print(Colour.dim(f"      worst: {a.detail}"))
        if hasattr(a, "dirs") and len(a.dirs) > 1:
            ps = [p for _, p in a.dirs if p == p] or [float("nan")]
            what = {"ecc": "eccentricity directions", "tilt": "tilt directions (fixed to the stator, or turning with the rotor)",
                    "combo": "combinations of eccentricity direction, tilt direction and kind of tilt"}.get(a.kind, "cases")
            print(Colour.dim(f"      {len(ps)} {what}: {min(ps):.3f} ... {max(ps):.3f}"))
    print(f"  worst case {worst.peak:.3f} deg el = {worst.peak / base:.2f} x the nominal error")
    sens = sensitivity(rows)
    names = {"gap": "air gap", "duty": "rotor fraction", "ecc": "eccentricity", "tilt": "tilt",
             "combo": "all together"}
    parts = [f"{names[k]} {sens[k] * 100:+.0f} %" for k in ("gap", "duty", "ecc", "tilt", "combo") if k in sens]
    if parts:
        print("  sensitivity (change of the peak error): " + ", ".join(parts))
    singles = [k for k in ("ecc", "tilt") if k in sens]
    small = [k for k in singles if sens[k] < 0.10]
    others = [v for k, v in sens.items() if k != "combo"]
    if "combo" in sens and sens["combo"] >= 0.10 and sens["combo"] > max(others, default=0.0) and len(small) == len(singles):
        print(Colour.dim("  note: eccentricity alone and tilt alone change little (with identical sectors and two "
                         "antiphase coils their first-order effects cancel), but an off-centre rotor with a tilt that "
                         "turns with it leaves an error that repeats once per turn: here that is the largest effect."))
    elif len(small) == len(singles) and small and "gap" in sens and sens["gap"] >= 0.10:
        print(Colour.dim("  note: with identical sectors and two antiphase coils the first-order effects of "
                         "eccentricity and tilt cancel; the air gap is the tolerance that counts here."))
    elif small and "gap" not in sens and "combo" not in sens:
        print(Colour.dim("  note: with identical sectors and two antiphase coils the first-order effects of "
                         "eccentricity and tilt cancel."))
    if sens and max(sens.values()) < 0.10:
        print(Colour.dim("  note: the design is insensitive to the tolerances assumed above."))


def electrical_estimate(model, rows):
    """(CoilElectrics.Electrics of the analysed design - receiver amplitude from the nominal row -, None) or
    (None, why it could not be made)."""
    try:
        el = CE.Electrics(model.stator, model.rotor, model.P, amp=rows[0].m["amp_s"], prepreg=model.prepreg,
                          model=model)
        return el, None
    except Exception as e:                                    # the estimate must not stop the analysis
        return None, f"{type(e).__name__}: {e}"


def window_cases(el, rows):
    """The electrical numbers of every analysed case (its own air gap, metal fraction and receiver amplitude)."""
    return [el.case(a.m["amp_s"], getattr(a, "gap", el.gap), getattr(a, "duty", None)) for a in rows]


def print_findings(items, indent="  "):
    rep = Report()
    rep.items = [(level, msg) for level, _code, msg in items]
    rep.print(indent)


def print_electrical(el):
    """The electrical estimate at the nominal air gap (CoilElectrics.py)."""
    print()
    print(Colour.bold(el.title()))
    for line in el.lines(title=False):
        print(line)
    print_findings(el.findings)


def print_electrical_window(el, rows):
    """Receiver voltage and oscillator frequency for every case of the tolerance window, and the IC checks over
    all of them.  Returns the findings that were not already reported for the nominal air gap."""
    cases = window_cases(el, rows)
    with_v = el.tx_vpp is not None and el.amp is not None
    print()
    what = f"receiver voltage at {el.tx_text()}" if with_v else "receiver voltage / TX voltage"
    print(Colour.bold(f"ELECTRICAL OVER THE TOLERANCE WINDOW  ({what}; oscillator with the exact tank capacitors "
                      f"above)"))
    print(Colour.dim(f"  {'case':<58s} {'gap mm':>6s}   {'receiver mVpp' if with_v else 'M/L':<15s} {'oscillator':>10s}"))
    for a, c in zip(rows, cases):
        if c["rx"] is not None:
            rx = CE._mv_range(*c["rx"])
        elif c["k"] is not None:
            rx = f"{c['k'] * 100:.2f} %"
        else:
            rx = "-"
        print(f"  {a.label:<58s} {c['gap']:>6.2f}   {rx:<15s} {c['f'] / 1e6:>6.3f} MHz")
    f_lo, f_hi = min(c["f"] for c in cases), max(c["f"] for c in cases)
    parts = []
    if with_v:
        lo = min(c["rx"][0] for c in cases)
        hi = max(c["rx"][1] for c in cases)
        txt = f"receiver {CE._mv_range(lo, hi)} mVpp"
        if el.lim:
            rmin, rmax = el.lim["rx_vpp"]
            txt += f" ({el.ic} accepts {CE._lim(rmin)} ... {CE._lim(rmax)}: {el.rx_status(cases)})"
        parts.append(txt)
    txt = f"oscillator {CE._mhz(f_lo, f_hi)}"
    if el.lim:
        ok = "OK" if el.lim["f_min"] <= f_lo and f_hi <= el.lim["f_max"] else "OUTSIDE"
        txt += f" ({el.ic} range {el.lim['f_min'] / 1e6:g} ... {el.lim['f_max'] / 1e6:g} MHz: {ok})"
    parts.append(txt)
    print("  over the window: " + ", ".join(parts))
    seen = {(level, code) for level, code, _m in el.findings}
    new = [f for f in el.check_cases(cases, "over the tolerance window") if (f[0], f[1]) not in seen]
    print_findings(new)
    return new


def make_plot(path, model, nominal, rows, title=""):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print(Colour.yellow("  matplotlib is not installed: no plot written (pip install matplotlib)"))
        return
    import textwrap
    fig, ax = plt.subplots(2, 2, figsize=(12, 8.4))
    xd = np.degrees(nominal.x)
    ax[0, 0].plot(xd, nominal.Vs / nominal.m["amp_s"], label="sin coil")
    ax[0, 0].plot(xd, nominal.Vc / nominal.m["amp_s"], label="cos coil")
    ax[0, 0].set_title("receiver signals (nominal, relative)")
    ax[0, 0].set_xlabel("electrical angle (deg)")
    ax[0, 0].legend(loc="upper right", fontsize=8)
    ax[0, 1].bar(range(2, 2 + len(nominal.m["hd"])), nominal.m["hd"])
    ax[0, 1].set_title("harmonics of the signal (%)")
    ax[0, 1].set_xlabel("harmonic")
    for a in rows:
        if len(a.x) == len(nominal.x):
            ax[1, 0].plot(np.degrees(a.x), a.m["err_curve"], label=a.label[:40])
    ax[1, 0].set_title("angle error over one electrical period (deg el)")
    ax[1, 0].set_xlabel("electrical angle (deg)")
    ax[1, 0].legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, frameon=False)
    full = [a for a in rows if len(a.x) != len(nominal.x)]
    if full:
        worst = max(full, key=lambda a: a.peak)
        ax[1, 1].plot(np.degrees(worst.theta), worst.m["err_curve"], lw=0.8)
        ax[1, 1].set_title("worst tolerance case over the whole turn:\n" + "\n".join(textwrap.wrap(worst.label, 60)),
                           fontsize=8)
        ax[1, 1].set_xlabel("rotor angle (deg mechanical)")
        ax[1, 1].set_ylabel("deg el")
    else:
        ax[1, 1].axis("off")
    if title:
        fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    print(f"  plot written: {path}")


# =============================================================================
# command line
# =============================================================================
def _safe_value(text):
    """'0.5', '1/3', '"auto"', 'auto', 'None', '[...]' -> a Python value.  Only literals and plain
    arithmetic on numbers are accepted (nothing is executed)."""
    text = text.strip()
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        pass
    try:
        node = ast.parse(text, mode="eval").body

        def ev(n):
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                return n.value
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
                v = ev(n.operand)
                return v if isinstance(n.op, ast.UAdd) else -v
            if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                l, r = ev(n.left), ev(n.right)
                return {ast.Add: l + r, ast.Sub: l - r, ast.Mult: l * r, ast.Div: (l / r if r else float("nan"))}[type(n.op)]
            raise ValueError
        return ev(node)
    except (ValueError, SyntaxError):
        return text                                        # a bare word such as  field_compensated  or  auto


def parse_overrides(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"--set expects NAME=VALUE, got {it!r}")
        name, val = it.split("=", 1)
        name = name.strip()
        if name not in PC.KNOWN_NAMES:
            raise SystemExit(f"--set: {name} is not a parameter")
        out[name] = _safe_value(val)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Predict the behaviour of the generated sensor.")
    ap.add_argument("--set", nargs="+", metavar="NAME=VALUE", help="override parameters for this run only")
    ap.add_argument("--loops", type=int, help="shortcut for --set LOOPS=N")
    ap.add_argument("--gap-tol", type=float, default=GAP_TOLERANCE_MM, help="air gap tolerance (mm)")
    ap.add_argument("--duty-tol", type=float, default=ROTOR_DUTY_TOLERANCE,
                    help="rotor metal fraction tolerance, 0 = skip")
    ap.add_argument("--ecc", type=float, default=ECCENTRICITY_MM, help="rotor eccentricity (mm), 0 = skip")
    ap.add_argument("--tilt", type=float, default=TILT_DEG, help="rotor tilt (deg), 0 = skip")
    ap.add_argument("--directions", type=int, default=ECC_DIRECTIONS,
                    help="eccentricity directions tried (over one loop pitch)")
    ap.add_argument("--rotor-model", choices=("eddy", "screen"), default=None,
                    help=f"rotor model (default {ROTOR_MODEL}): eddy currents, or the older ideal screen")
    ap.add_argument("--no-blur", action="store_true",
                    help="screen model only: sharp rotor edges (no smoothing across the air gap)")
    ap.add_argument("--ideal-geometry", action="store_true",
                    help="the older geometry: TX as ideal rings, receiver copper half on each RX layer, no direct "
                         "TX-to-receiver coupling (TRUE_3D_GEOMETRY = False)")
    ap.add_argument("--plot", metavar="FILE.png", help="write a plot")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)
    Colour.setup(False if args.no_color else None)
    if min(args.gap_tol, args.duty_tol, args.ecc, args.tilt) < 0:
        ap.error("the tolerances (--gap-tol --duty-tol --ecc --tilt) must be 0 or more")
    if args.directions < 1:
        ap.error("--directions must be at least 1")

    P0 = load_parameters()
    if P0 is None:
        return 1
    over = parse_overrides(args.set)
    if args.loops is not None:
        over["LOOPS"] = args.loops
    P = Overlay(P0, **over) if over else P0

    print(Colour.bold("[1/3] Checking the parameters and building the design"))
    try:
        stator, rotor, rep = prepare(P)
    except DesignError as e:
        e.report.print()
        print(Colour.red(f"FAILED: {e}"))
        return 1
    rep.print()
    kind = str(args.rotor_model or ROTOR_MODEL).lower()
    if args.no_blur and kind != "screen":
        print("  " + Colour.yellow("--no-blur only applies to --rotor-model screen; ignored"))
    try:
        model = make_model(stator, rotor, P, rotor_model=kind, blur=False if args.no_blur else None,
                           true3d=False if args.ideal_geometry else None)
    except DesignError as e:
        print("  " + Colour.red(f"ERROR   {e}"))
        return 1
    print(f"  {stator.N} loop(s), profile {P.RX_PROFILE}, {stator.n_sub} sub-coil(s)"
          + (f" split {stator.split_deg:g} deg" if stator.n_sub > 1 else "")
          + f", rotor metal fraction {rotor.duty:.4g}, {P.PCB_LAYERS}-layer board, TX {P.TX_TURNS} turn(s) x "
          + f"{len(CE.tx_layers(stator, P))} layer(s)"
          + ("" if CE.tx_layers(stator, P) == [("B.Cu", 1.0)]
             else f" on {' + '.join(l for l, _w in CE.tx_layers(stator, P))}"
             + ((" in parallel" if getattr(stator, "tx_mode", "") == "parallel" else " in series")
                if len(CE.tx_layers(stator, P)) > 1 else "")))
    print(f"  rotor copper r = {rotor.r_in:.2f} ... {rotor.r_out:.2f} mm = {rotor.ext_in:+.2f} mm at the inner and "
          f"{rotor.ext_out:+.2f} mm at the outer edge of the RX band (+ = past the band)")
    tx_out = getattr(rotor, "tx_outer_edge", None)
    if tx_out is not None:
        rel = rotor.r_out - tx_out
        print(f"  outer TX turn ends at r = {tx_out:.2f} mm: the rotor copper ends {abs(rel):.2f} mm "
              + ("past it (it covers the TX turns)" if rel >= 0 else
                 ("inside it (over the TX turns)" if rotor.r_out > stator.tx_inner_edge else
                  "inside it, before the TX ring")))
    print(f"  geometry: {model.geometry_note}")
    if model.tx_copper is not None:
        dc = model.direct()
        print(f"  direct TX-to-receiver coupling (no rotor): {dc[0]:+.4g} / {dc[1]:+.4g} model units "
              f"(sin / cos coil; an offset of the receiver signals)")
    if model.kind == "eddy":
        print("  rotor model: eddy currents in the copper (RotorEddyModel.py)")
    elif model.blur:
        dist = ", ".join(f"{float(P.AIR_GAP_MM) + d:g}" for d in sorted(set(
            model.rx_depths if model.layer_grids is None else [z for gl in model.layer_grids for _g, z in gl])))
        print(f"  rotor model: ideal screen, smoothed across the air gap (rotor-to-copper distance {dist} mm)")
    else:
        print("  rotor model: ideal screen, sharp edges (overstates the harmonics)")
    print("  " + Colour.green("design built"))

    print(Colour.bold("[2/3] Simulating"))
    rows = tolerance_window(model, args.gap_tol, args.ecc, args.tilt, args.directions, duty_tol=args.duty_tol)
    print("  " + Colour.green("done"))
    print(Colour.bold("[3/3] Results"))
    print()
    print_nominal(model, rows[0], P)
    el, why = electrical_estimate(model, rows)
    if el is not None:
        print_electrical(el)
    else:
        print()
        print(Colour.yellow(f"ELECTRICAL ESTIMATE not available: {why}"))
    print_window(rows, model.N, args.ecc, args.tilt, args.gap_tol, args.duty_tol)
    if el is not None:
        print_electrical_window(el, rows)
    if args.plot:
        print()
        make_plot(args.plot, model, rows[0], rows,
                  title=f"{stator.N} loops, {P.RX_PROFILE}, {stator.n_sub} sub-coil(s), rotor metal fraction "
                        f"{rotor.duty:.4g}, gap {float(P.AIR_GAP_MM):g} mm")
    print()
    what = ("eddy currents in a thin, perfectly conducting rotor" if model.kind == "eddy" else
            "ideal-screen rotor (older model)")
    geo = ("true 3-D copper" if model.tx_copper is not None else
           "receiver traces at their depths, TX as rings" if model.layer_grids is not None else "TX as concentric rings")
    print(Colour.dim(f"Model: {what}, {geo}, not checked against hardware.  Use it to compare "
                     f"designs and to see sensitivities; the volts and megahertz are estimates (CoilElectrics.py) - "
                     f"keep a margin to the limits of the IC."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
