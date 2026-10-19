"""
TX_Electrics.py  -  electrical estimates of the TX coil for the generated stator + rotor.

RunCoilGenerator.py prints them for every generation (and writes them into Parameters.txt).  Nothing here
changes a board.  It gives

    the TX inductance (rotor away / rotor at the air gap), the TX resistance and Q,
    the tank capacitors for EXCITATION_FREQ_HZ and the oscillator frequency they give,
    the parallel resistance of the tank (what the oscillator has to drive),

and checks the oscillator frequency and the tank resistance against the datasheet limits of RECEIVER_IC
(Board_Parameters.py).  The receiver voltage needs a model of the whole sensor (rotor angle, coupling): that
is not part of the generator.

How the numbers are made  (read this before trusting them)
  * TX inductance: every TX turn is taken as a circular loop (radius from the generator, depth from the
    stack-up).  L = the turn self-inductances (a ring of a w x t trace) + the mutual inductances of every
    pair of turns (Maxwell's formula for coaxial circles).  The steps between the turns, the spiral pitch and
    the terminal tails are left out; against the full TX polyline (Neumann integral) that is within 2 %.
  * Resistance: DC resistance of all the TX copper.  At the TX frequency skin and proximity effects raise
    it; the checks allow for up to AC_FACTOR x the DC value.
  * Rotor: rotor_inductance_drop() below takes the rotor copper as an ideal screen of the TX field.  That is
    an upper estimate of the drop (a real rotor with gaps pushes the field through them instead of removing
    it), so the true frequency with the rotor lies between "rotor away" and the predicted one.
  * Not included: parasitic capacitance (IC pins, coil, wiring; typically some 10 pF - it lowers the
    frequency a little), the temperature (copper: +0.39 % resistance per K).
  * None of it has been checked against a measured board: keep a margin to every limit of the IC.

Needs only Python 3 and numpy.  Imported by RunCoilGenerator.py (step 4); not a script.  (Project layout: wiki
page "Project Output Organization", docs/wiki/Project-Output-Organization.md; overview in README.md in the top
folder.)
"""

import math

import numpy as np

from Generator.Core.BoardLayout import tx_shape
from Generator.Core import Layers
from Generator.Core.Layers import layer_depth, STACKUP_PREPREG_MM
from Generator.Core.Geometry import loop_bz, ellipk_ellipe

MU0 = 4.0e-7 * math.pi
RHO_CU = 1.0 / 5.8e7                 # copper resistivity at 20 C (ohm m)
AC_FACTOR = 2.0                      # at the TX frequency R can be up to this x the DC value (checks use it)
MODEL_TO_HENRY = MU0 / (2.0 * math.pi) * 1e-3   # flux per ampere (field in mu0 / 2 pi per mm, area in mm2) -> H
E12 = (1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2)   # C0G capacitor values per decade

DEFAULT_RECEIVER_IC = "IPS2550"      # used when Board_Parameters.py has no RECEIVER_IC line (as ParameterRules.py)
DEFAULT_COPPER_THICKNESS_UM = 35.0   # ... no COPPER_THICKNESS_UM line

# Datasheet limits of the receiver ICs that RECEIVER_IC can name (from the IC datasheets - check your revision).
# Both reference designs put the tank capacitance in two halves: 2 C from TX1 and 2 C from TX2 to ground.
IC_LIMITS = {
    "IPS2550": dict(
        f_min=2.0e6, f_max=5.6e6,           # LC oscillator frequency
        rp_min=250.0),                      # R_Peq: "the minimum loss resistance that the oscillator can drive
                                            # for safe operation"
    "IPS2200": dict(
        f_min=1.7e6, f_max=5.8e6,           # f_LC
        rp_min=100.0),                      # R_Peq
}


# =============================================================================
# inductance formulas (the loop field: Geometry.py)
# =============================================================================
def mutual_coaxial(a, b, z):
    """Mutual inductance (H) of two coaxial circular filaments, radii a, b and axial distance z (m); Maxwell."""
    k2 = 4.0 * a * b / ((a + b) ** 2 + z * z)
    k = math.sqrt(k2)
    kk, ee = ellipk_ellipe(k2)
    return MU0 * math.sqrt(a * b) * ((2.0 / k - k) * kk - 2.0 / k * ee)


def ring_self(radius, width, thickness):
    """Self-inductance (H) of a circular ring of a rectangular w x t trace (m); geometric mean distance."""
    gmd = 0.2235 * (width + thickness)
    return MU0 * radius * (math.log(8.0 * radius / gmd) - 2.0)


# =============================================================================
# the TX coil
# =============================================================================
def tx_layers(P):
    """[(layer, share of the TX current)] of the TX turns: one layer (1), two in series (1, 1) or, with a parallel
    TX (TX_WIRING = "parallel"), the same turns on two layers in parallel (1/2, 1/2: equal halves of the current)."""
    return list(Layers.layer_plan(P)["field_layers"])


def tx_loops(stator, P, prepreg=STACKUP_PREPREG_MM):
    """(radius mm, depth mm, share of the current) of every TX ring, all wound the same way."""
    radii = [float(r) for r in stator.tx_radii]
    if tx_shape(P) == "spiral":
        radii = [r + 0.5 * float(P.TX_PITCH_MM) for r in radii]          # a spiral turn runs from r to r + pitch
    return [(r, layer_depth(l, P, prepreg), float(w)) for l, w in tx_layers(P) for r in radii]


def tx_inductance(loops, width_mm, thickness_um):
    """Inductance (H) of the TX turns in series."""
    w, t = float(width_mm) * 1e-3, float(thickness_um) * 1e-6
    total = 0.0
    for i, (ri, zi, wi) in enumerate(loops):
        for j, (rj, zj, wj) in enumerate(loops):
            if i == j:
                total += wi * wj * ring_self(ri * 1e-3, w, t)
            else:
                total += wi * wj * mutual_coaxial(ri * 1e-3, rj * 1e-3, abs(zi - zj) * 1e-3)
    return total


def tx_resistance_dc(stator, P, thickness_um):
    """(DC resistance in ohm, equivalent length in m, copper length in m) of the whole TX trace.  The equivalent
    length is the length of one trace with that resistance: for a parallel TX it is shorter than the copper."""
    copper_mm = sum(math.hypot(s.b[0] - s.a[0], s.b[1] - s.a[1]) for s in stator.tx_segments)
    # parallel TX (TX_WIRING = "parallel"): where the turns run twice, in parallel, the pair counts as one resistance
    # of the two paths in parallel (TX_Wiring.emit_parallel_arcs works out how much length that saves: equal paths
    # count as half the length of one, i.e. 1.5 x the arc comes off; a go-around path with its run-outs and brackets
    # is longer than the base turn beside it, L_a * L_b / (L_a + L_b))
    saving = getattr(stator, "tx_parallel_saving_mm", None)
    if saving is None:
        saving = 1.5 * float(getattr(stator, "tx_parallel_length_mm", 0.0) or 0.0)
    length_mm = copper_mm - float(saving)
    area = float(P.TX_TRACE_WIDTH_MM) * 1e-3 * float(thickness_um) * 1e-6
    return RHO_CU * length_mm * 1e-3 / area, length_mm * 1e-3, copper_mm * 1e-3


def rotor_inductance_drop(loops, r_in, r_out, duty, gap_mm, n=4001):
    """How much the rotor lowers the TX inductance (H), centred rotor.  The TX field at the rotor plane is
    taken as screened where the copper is (an ideal screen), and the change
    spreads out (Laplace / Poisson kernel) on its way back to every TX turn - for one turn of radius R at the
    distance h below the rotor that is the step 1/2 + atan((R - r) / h) / pi instead of a sharp edge.  For a
    rotor covering the whole plane this comes close to the exact mirror-image result."""
    if not 0.0 < r_in < r_out:
        return 0.0
    g = float(gap_mm)
    r = np.linspace(float(r_in), float(r_out), n)
    bz = np.zeros_like(r)
    for R, depth, w in loops:
        bz += w * np.array([loop_bz(R, float(x), g + depth) for x in r])    # TX field at the rotor plane
    linked = np.zeros_like(r)
    for R, depth, w in loops:
        linked += w * (0.5 + np.arctan((R - r) / (g + depth)) / math.pi)   # how much of a change at r each turn sees
    f = bz * r * linked
    flux = float(np.sum(0.5 * (f[1:] + f[:-1]) * np.diff(r)))     # mm (model units), per radian
    return MODEL_TO_HENRY * float(duty) * 2.0 * math.pi * flux


def standard_caps(c_needed, n=2):
    """The E12 values just below and just above c_needed (F)."""
    if not c_needed > 0:
        return []
    dec = math.floor(math.log10(c_needed))
    vals = sorted(v * 10.0 ** d for d in (dec - 1, dec, dec + 1) for v in E12)
    lo = [v for v in vals if v <= c_needed * (1 + 1e-9)][-n // 2:] if n > 1 else []
    hi = [v for v in vals if v > c_needed * (1 + 1e-9)][:n - len(lo)]
    return lo + hi


def ic_limits(P):
    """(name, limits dict) of RECEIVER_IC, or (None, None) for None or a name that is not in IC_LIMITS."""
    name = getattr(P, "RECEIVER_IC", DEFAULT_RECEIVER_IC)
    if name is None:
        return None, None
    key = str(name).strip().upper()
    return (key, IC_LIMITS[key]) if key in IC_LIMITS else (None, None)


# =============================================================================
# the estimate
# =============================================================================
class Electrics:
    """Electrical estimate of one stator + rotor.  rotor may be None (inductance without a rotor only), or
    anything with .r_in, .r_out (mm) and .duty.
    .findings = [(level, code, message), ...]: the checks against RECEIVER_IC at the nominal air gap."""

    def __init__(self, stator, rotor, P, prepreg=None):
        self.P = P
        self.prepreg = STACKUP_PREPREG_MM if prepreg is None else float(prepreg)
        self.thickness_um = float(getattr(P, "COPPER_THICKNESS_UM", DEFAULT_COPPER_THICKNESS_UM))
        self.width_mm = float(P.TX_TRACE_WIDTH_MM)
        self.loops = tx_loops(stator, P, self.prepreg)
        self.n_turns = int(round(sum(w for _r, _d, w in self.loops)))     # turns in series
        self.L_free = tx_inductance(self.loops, self.width_mm, self.thickness_um)
        self.R_dc, self.length_m, self.copper_m = tx_resistance_dc(stator, P, self.thickness_um)
        self.gap = float(P.AIR_GAP_MM)
        self.has_rotor = rotor is not None
        if self.has_rotor:
            self.rotor_in, self.rotor_out, self.duty = float(rotor.r_in), float(rotor.r_out), float(rotor.duty)
        else:
            self.rotor_in = self.rotor_out = self.duty = None
        self.ic, self.lim = ic_limits(P)
        self.f_target = float(P.EXCITATION_FREQ_HZ)
        # the tank is designed for the target frequency with the rotor in place at the nominal air gap
        self.L_nom = self.L_at(self.gap)
        if not self.L_nom > 0.0:
            raise ValueError("the rotor model gives no inductance left at this air gap (the air gap is too small "
                             "for the estimate)")
        self.C = 1.0 / ((2.0 * math.pi * self.f_target) ** 2 * self.L_nom)
        self.findings = []
        self._check()

    def L_at(self, gap):
        """TX inductance with the rotor at this air gap (H); without a rotor the free inductance."""
        if not self.has_rotor:
            return self.L_free
        return self.L_free - rotor_inductance_drop(self.loops, self.rotor_in, self.rotor_out, self.duty, gap)

    def f_at(self, L):
        """Oscillator frequency (Hz) with the tank capacitance C and the inductance L."""
        return 1.0 / (2.0 * math.pi * math.sqrt(L * self.C))

    def q_range(self, L, f):
        """Q of the coil: (with AC_FACTOR x R_dc, with R_dc)."""
        w = 2.0 * math.pi * f
        return w * L / (AC_FACTOR * self.R_dc), w * L / self.R_dc

    def rp_range(self, L, f):
        """Tank parallel resistance (ohm): (with AC_FACTOR x R_dc, with R_dc)."""
        w = 2.0 * math.pi * f
        return (w * L) ** 2 / (AC_FACTOR * self.R_dc), (w * L) ** 2 / self.R_dc

    def rp_lowest(self):
        """(lowest tank parallel resistance with the rotor as estimated, the same with the rotor's effect left out)
        in ohm, both with AC_FACTOR x R_dc.  The tank capacitance is fixed, so R_P = L / (C R) grows with L: the
        true value lies between the two (the estimate overstates the rotor's effect)."""
        return (self.rp_range(self.L_nom, self.f_target)[0],
                self.rp_range(self.L_free, self.f_at(self.L_free))[0])

    # ------------------------------------------------------------ IC checks
    def _check(self):
        add, lim, ic = self.findings.append, self.lim, self.ic
        if not lim:
            return
        f = self.f_at(self.L_nom)
        if not lim["f_min"] <= f <= lim["f_max"]:
            add(("warning", "f_range",
                 f"the oscillator frequency at the nominal air gap ({_mhz(f)}) is outside the {ic}'s range "
                 f"{lim['f_min'] / 1e6:g} ... {lim['f_max'] / 1e6:g} MHz.  Change EXCITATION_FREQ_HZ"))
        rp, rp_best = self.rp_lowest()
        if rp_best < lim["rp_min"]:
            add(("warning", "rp_low",
                 f"the tank's parallel resistance at the nominal air gap may be as low as {rp:.0f} ohm (if the AC "
                 f"resistance is {AC_FACTOR:g} x the DC value); the {ic} needs at least {lim['rp_min']:g} ohm.  More "
                 f"TX turns, wider TX traces, thicker copper or a higher EXCITATION_FREQ_HZ raise it"))
        elif rp < lim["rp_min"]:
            add(("info", "rp_maybe",
                 f"the tank's parallel resistance with the rotor lies between {rp:.0f} and {rp_best:.0f} ohm (if the AC "
                 f"resistance is {AC_FACTOR:g} x the DC value): the lower value comes from the upper estimate of the "
                 f"rotor's effect and is below the {ic}'s {lim['rp_min']:g} ohm.  Measure it on the board, or raise it "
                 f"with more TX turns, wider TX traces, thicker copper or a higher EXCITATION_FREQ_HZ"))
        if self.has_rotor and lim["f_min"] <= self.f_target <= lim["f_max"]:
            f_free = self.f_at(self.L_free)
            if not lim["f_min"] <= f_free <= lim["f_max"]:
                add(("info", "f_free", f"with the rotor removed the oscillator would run at {f_free / 1e6:.2f} MHz, "
                                       f"outside the {ic}'s range {lim['f_min'] / 1e6:g} ... {lim['f_max'] / 1e6:g} "
                                       f"MHz (with the rotor it runs between that and "
                                       f"{self.f_target / 1e6:g} MHz)"))

    @property
    def warnings(self):
        return [m for l, _c, m in self.findings if l == "warning"]

    # ------------------------------------------------------------ text
    def heading(self):
        return ((f"receiver IC {self.ic}" if self.lim else "no receiver IC set (RECEIVER_IC): no IC checks")
                + "; model only, not checked on hardware")

    def title(self):
        return "ELECTRICAL ESTIMATE  (" + self.heading() + ")"

    def lines(self, title=True):
        """The report lines (no colours; the findings are not in them: print .findings as well)."""
        out = [self.title()] if title else []
        f = self.f_target
        out.append(f"  TX coil     L = {self.L_free * 1e6:.3f} uH with the rotor away")
        if self.has_rotor:
            drop = (self.L_free - self.L_nom) / self.L_free * 100.0
            out.append(f"              L = {self.L_nom * 1e6:.3f} uH with the rotor at the {self.gap:g} mm air gap "
                       f"({-drop:+.1f} %: an upper estimate of the drop)")
        if abs(self.copper_m - self.length_m) < 0.005:
            copper = f"{self.length_m:.2f} m of {self.width_mm:g} mm x {self.thickness_um:g} um copper"
        else:
            copper = (f"{self.copper_m:.2f} m of {self.width_mm:g} mm x {self.thickness_um:g} um copper, "
                      f"{self.length_m:.2f} m equivalent for the two layers in parallel")
        out.append(f"              R = {self.R_dc:.2f} ohm DC ({self.n_turns} turn(s), {copper}), up to about "
                   f"{AC_FACTOR:g}x that at {f / 1e6:g} MHz")
        where = "with the rotor in place" if self.has_rotor else "(no rotor)"
        if self.lim:
            out.append(f"  tank        for {f / 1e6:g} MHz {where}: 2 x {_cap(2 * self.C)}, from TX1 and from TX2 "
                       f"to ground (= {_cap(self.C)} across the coil)")
        else:
            out.append(f"  tank        for {f / 1e6:g} MHz {where}: {_cap(self.C)} across the coil (or 2 x "
                       f"{_cap(2 * self.C)}, from each coil end to ground)")
        parts = []
        for c2 in standard_caps(2.0 * self.C):
            c_eq = c2 / 2.0
            f_rot = 1.0 / (2.0 * math.pi * math.sqrt(self.L_nom * c_eq))
            txt = f"2 x {_cap(c2)} -> {f_rot / 1e6:.2f} MHz"
            if self.has_rotor:
                txt += f" ({1.0 / (2.0 * math.pi * math.sqrt(self.L_free * c_eq)) / 1e6:.2f} rotor away)"
            parts.append(txt)
        if parts:
            out.append("              nearest standard C0G: " + ";  ".join(parts))
        f_free = self.f_at(self.L_free)
        osc = (f"              oscillator with the exact capacitors: {f_free / 1e6:.2f} MHz with the rotor away, "
               f"{f / 1e6:.2f} MHz with it" if self.has_rotor else
               f"              oscillator with the exact capacitors: {f / 1e6:.2f} MHz")
        if self.lim:
            fl, fh = self.lim["f_min"], self.lim["f_max"]
            osc += f"  ({self.ic} range {fl / 1e6:g} ... {fh / 1e6:g} MHz: " + ("OK)" if fl <= f <= fh else "OUTSIDE)")
        out.append(osc)
        if self.has_rotor:
            out.append("              (the true frequency with the rotor lies between the two: the drop is an upper "
                       "estimate)")
        q_lo, q_hi = self.q_range(self.L_nom, f)
        rp_lo, rp_hi = self.rp_range(self.L_nom, f)
        line = f"              Q = {q_lo:.0f} ... {q_hi:.0f}, parallel resistance {_ohm(rp_lo)} ... {_ohm(rp_hi)}"
        if self.lim:
            low, best = self.rp_lowest()
            line += f"  ({self.ic} needs >= {self.lim['rp_min']:g} ohm: " + (
                "OK)" if low >= self.lim["rp_min"] else "TOO LOW)" if best < self.lim["rp_min"] else
                f"OK without the rotor ({_ohm(best)}), not with the estimated rotor - see the note)")
        out.append(line)
        return out

    def summary(self):
        """One line: inductance, tank, IC verdict."""
        txt = f"TX L {self.L_free * 1e6:.2f} uH"
        if self.has_rotor:
            txt += f" ({self.L_nom * 1e6:.2f} with the rotor)"
        txt += f", R {self.R_dc:.2f} ohm DC, tank 2 x {_cap(2 * self.C)} for {self.f_target / 1e6:g} MHz"
        if self.lim:
            n = len(self.warnings)
            txt += f"; {self.ic}: " + ("OK" if not n else f"{n} warning(s)")
        return txt


def estimate(stator, rotor, P):
    """Electrics of a built stator + rotor (rotor None = no rotor)."""
    el = Electrics(stator, rotor, P)
    if rotor is None:
        el.findings.append(("info", "no_rotor", "no rotor: the inductance is the one without it"))
    return el


def _cap(c):
    """Capacitance text (F -> pF / nF / uF)."""
    if c < 1e-9:
        return f"{c * 1e12:.3g} pF"
    if c < 1e-6:
        return f"{c * 1e9:.3g} nF"
    return f"{c * 1e6:.3g} uF"


def _ohm(r):
    return f"{r:.0f} ohm" if r < 1000 else f"{r / 1000:.3g} kohm"


def _mhz(f):
    return f"{f / 1e6:.3f} MHz"
