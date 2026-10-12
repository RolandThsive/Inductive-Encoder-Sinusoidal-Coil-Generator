#!/usr/bin/env python3
"""
CoilElectrics.py  -  absolute electrical estimates for the generated stator + rotor.

RunCoilGenerator.py prints them for every generation, AnalyzeCoil.py for every case of its tolerance
window and OptimizeCoil.py for every candidate.  Nothing here changes a board.  It gives

    the TX inductance (rotor away / rotor at the air gap), the TX resistance and Q,
    the tank capacitors for EXCITATION_FREQ_HZ and the oscillator frequency they give,
    the parallel resistance of the tank (what the oscillator has to drive),
    the receiver (RX) voltage, peak-to-peak, at the TX voltage of the IC,

and checks them against the datasheet limits of RECEIVER_IC (Board_Parameters.py).

How the numbers are made  (read this before trusting them)
  * TX inductance: every TX turn is taken as a circular loop (radius from the generator, depth from the
    stack-up).  L = the turn self-inductances (a ring of a w x t trace) + the mutual inductances of every
    pair of turns (Maxwell's formula for coaxial circles).  The radial steps, the spiral pitch and the
    terminal tails are left out; against the full TX polyline (Neumann integral) that is within 2 %.
  * Resistance: DC resistance of all the TX copper.  At the TX frequency skin and proximity effects raise
    it; the checks allow for up to AC_FACTOR x the DC value.
  * Rotor (eddy-current model, RotorEddyModel.py, the default): the eddy currents in the rotor copper are
    solved, and the change of the TX inductance follows from them exactly (thin, perfectly conducting copper).
    Centred rotor.  With the older ideal-screen model (AnalyzeCoil.py --rotor-model screen) the drop comes
    from rotor_inductance_drop() below: an upper estimate (a real rotor with gaps pushes the field through
    them instead of removing it), so the true frequency lies between "rotor away" and the predicted one.
  * Receiver voltage: AnalyzeCoil.py's receiver signal (the same model as its angle error) in volts.  The IC
    sets the TX voltage, so the ratio counts:  V_RX / V_TX = M / L  (M = TX-to-receiver mutual inductance
    of the signal at the rotor angle where it is largest, L = TX inductance with the rotor).
  * With the ideal-screen model the receiver voltage misses the crowding of the field at the copper edges.
    For long radial sectors that is an exact 2-D problem: the fundamental of the field in the rotor plane is
    1 - cos(pi d) instead of (2 / pi) sin(pi d) (d = metal fraction), i.e. (pi / 2) tan(pi d / 2) times the
    ideal-screen value: 0.51 / 0.65 / 0.91 / 1.14 / 1.57 at d = 0.2 / 0.25 / 1/3 / 0.4 / 0.5
    (crowding_factor); the screen-model report gives that range.  The eddy model computes it.
  * Not included: parasitic capacitance (IC pins, coil, wiring; typically some 10 pF - it lowers the
    frequency a little), the IC's receiver input filter (100 pF per line in the Renesas reference designs -
    it raises the receiver voltage by a few per cent), the temperature (copper: +0.39 % resistance per K).
  * None of it has been checked against a measured board: keep a margin to every limit of the IC.

Needs only Python 3 and numpy.  Runs from any folder (project layout: README.txt in the project folder).
"""

import math

import numpy as np

MU0 = 4.0e-7 * math.pi
RHO_CU = 1.0 / 5.8e7                 # copper resistivity at 20 C (ohm m)
AC_FACTOR = 2.0                      # at the TX frequency R can be up to this x the DC value (checks use it)
MODEL_TO_HENRY = MU0 / (2.0 * math.pi) * 1e-3   # AnalyzeCoil's flux per ampere (field in 1/mm, area in mm2) -> H
STACKUP_PREPREG_MM = 0.2             # 4-layer boards: outer layer to its inner neighbour (as AnalyzeCoil.py)
E12 = (1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2)   # C0G capacitor values per decade
MARGIN = 2.0                         # a receiver voltage closer than this factor to an IC limit is pointed out

DEFAULT_RECEIVER_IC = "IPS2550"      # used when Board_Parameters.py has no RECEIVER_IC line (as ParameterChecker.py)
DEFAULT_COPPER_THICKNESS_UM = 35.0   # ... no COPPER_THICKNESS_UM line

# Datasheet limits of the receiver ICs that RECEIVER_IC can name (Renesas datasheets - check your revision).
# Both reference designs put the tank capacitance in two halves: 2 C from TX1 and 2 C from TX2 to ground.
IC_LIMITS = {
    "IPS2550": dict(
        f_min=2.0e6, f_max=5.6e6,           # LC oscillator frequency
        rp_min=250.0,                       # R_Peq: "the minimum loss resistance that the oscillator can drive
                                            # for safe operation"
        tx_vpp=(6.0, 11.0),                 # V_TX_P (TX1 vs TX2), set by the programmed coil current
        rx_vpp=(0.015, 0.920),              # V_RX for the default AGC target (1.8 Vpp), gain boost off
        rx_note="default AGC target 1.8 Vpp, gain boost off",
        rx_alt=(("with the gain boost on", 0.008, 0.470),        # other settings of the receiver input
                ("with the AGC target 3.0 Vpp", 0.025, 1.500))),
    "IPS2200": dict(
        f_min=1.7e6, f_max=5.8e6,           # f_LC
        rp_min=100.0,                       # R_Peq
        tx_vpp=(11.0, 11.0),                # V_TX_P (one value in the datasheet)
        rx_vpp=(0.005, 5.2),                # V_RX input range (the usable part depends on the front-end gain)
        rx_note="input range; the usable part depends on the front-end gain",
        rx_alt=()),
}

# short names of the warnings (the `code` of a finding)
CODE_TEXT = {"f_range": "oscillator frequency out of range", "rp_low": "tank resistance too low",
             "rx_low": "receiver signal too small", "rx_high": "receiver signal too large",
             "rx_span": "receiver signal varies too much", "tx_range": "TX voltage out of range"}


# =============================================================================
# field and inductance formulas  (AnalyzeCoil.py uses the same functions)
# =============================================================================
def ellipk_ellipe(m):
    """Complete elliptic integrals K(m), E(m) for arrays, 0 <= m < 1 (AGM)."""
    m = np.clip(np.asarray(m, dtype=float), 0.0, 1.0 - 1e-15)
    a = np.ones_like(m)
    b = np.sqrt(1.0 - m)
    c = np.sqrt(m)
    total = 0.5 * c * c
    pw = 0.5
    for _ in range(60):
        a, b, c = 0.5 * (a + b), np.sqrt(a * b), 0.5 * (a - b)
        pw *= 2.0
        total = total + pw * c * c
        if np.max(np.abs(c)) < 1e-16:
            break
    k = math.pi / (2.0 * a)
    return k, k * (1.0 - total)


def loop_bz(radius, r, z):
    """Axial field of a circular current loop, in units of mu0 * I / (2 pi) per mm (r, z arrays or numbers, mm)."""
    r = np.asarray(r, dtype=float)
    m = 4.0 * radius * r / ((radius + r) ** 2 + z * z)
    k, e = ellipk_ellipe(m)
    den = (radius - r) ** 2 + z * z
    return (k + (radius * radius - r * r - z * z) / den * e) / np.sqrt((radius + r) ** 2 + z * z)


def layer_depth(layer, P, prepreg=STACKUP_PREPREG_MM):
    """Distance of a copper layer below the top copper (mm)."""
    t = float(P.PCB_THICKNESS_MM)
    if layer == "F.Cu":
        return 0.0
    if layer == "B.Cu":
        return t
    inner = prepreg if 2.0 * prepreg < t else t / 3.0
    return inner if layer == "In1.Cu" else t - inner


def mutual_coaxial(a, b, z):
    """Mutual inductance (H) of two coaxial circular filaments, radii a, b and axial distance z (m); Maxwell."""
    k2 = 4.0 * a * b / ((a + b) ** 2 + z * z)
    k = math.sqrt(k2)
    kk, ee = ellipk_ellipe(k2)
    kk, ee = float(kk), float(ee)
    return MU0 * math.sqrt(a * b) * ((2.0 / k - k) * kk - 2.0 / k * ee)


def ring_self(radius, width, thickness):
    """Self-inductance (H) of a circular ring of a rectangular w x t trace (m); geometric mean distance."""
    gmd = 0.2235 * (width + thickness)
    return MU0 * radius * (math.log(8.0 * radius / gmd) - 2.0)


# =============================================================================
# the TX coil
# =============================================================================
def tx_layers(stator, P):
    """[(layer, share of the TX current)] of the TX turns: one layer (1), two in series (1, 1) or, with a parallel
    TX (TX_SERIES = False), the same turns on two layers in parallel (1/2, 1/2: equal halves of the current)."""
    fl = getattr(stator, "tx_field_layers", None)
    if fl:
        return list(fl)
    return [("B.Cu", 1.0)]


def tx_loops(stator, P, prepreg=STACKUP_PREPREG_MM):
    """(radius mm, depth mm, share of the current) of every TX ring, all wound the same way."""
    radii = [float(r) for r in stator.tx_radii]
    if str(P.TX_TURN_SHAPE).lower() == "spiral":
        radii = [r + 0.5 * float(P.TX_PITCH_MM) for r in radii]          # a spiral turn runs from r to r + pitch
    return [(r, layer_depth(l, P, prepreg), float(w)) for l, w in tx_layers(stator, P) for r in radii]


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
    """(DC resistance in ohm, copper length in m) of the whole TX trace."""
    length_mm = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b, _layer in stator.tx_segments)
    # parallel TX (TX_SERIES = False): the turns run twice, in parallel - where both copies exist the pair counts as half
    # the length of one (equal halves of the current), i.e. 2 x length / 4
    par = float(getattr(stator, "tx_parallel_length_mm", 0.0) or 0.0)
    length_mm -= 1.5 * par
    area = float(P.TX_TRACE_WIDTH_MM) * 1e-3 * float(thickness_um) * 1e-6
    return RHO_CU * length_mm * 1e-3 / area, length_mm * 1e-3


def rotor_inductance_drop(loops, r_in, r_out, duty, gap_mm, n=4001):
    """How much the rotor lowers the TX inductance (H), centred rotor.  Same model as the receiver signal
    of AnalyzeCoil.py: the TX field at the rotor plane is screened where the copper is, and the change
    spreads out (Laplace / Poisson kernel) on its way back to every TX turn - for one turn of radius R at the
    distance h below the rotor that is the step 1/2 + atan((R - r) / h) / pi instead of a sharp edge.  For a
    rotor covering the whole plane this comes close to the exact mirror-image result."""
    if not 0.0 < r_in < r_out:
        return 0.0
    g = float(gap_mm)
    r = np.linspace(float(r_in), float(r_out), n)
    bz = np.zeros_like(r)
    for R, depth, w in loops:
        bz += w * loop_bz(R, r, g + depth)                        # TX field at the rotor plane
    linked = np.zeros_like(r)
    for R, depth, w in loops:
        linked += w * (0.5 + np.arctan((R - r) / (g + depth)) / math.pi)   # how much of a change at r each turn sees
    f = bz * r * linked
    flux = float(np.sum(0.5 * (f[1:] + f[:-1]) * np.diff(r)))     # mm (model units), per radian
    return MODEL_TO_HENRY * float(duty) * 2.0 * math.pi * flux


def crowding_factor(duty):
    """Receiver signal of a thin, perfectly conducting rotor with long radial sectors (exact 2-D result) divided
    by the ideal-screen signal of AnalyzeCoil.py, for the metal fraction `duty`: (pi / 2) tan(pi d / 2).  The
    field pushed off the copper crowds through the gaps (most at the copper edges); the fundamental of the field
    in the rotor plane is 1 - cos(pi d) instead of (2 / pi) sin(pi d).  Real, finite sectors lie between this
    factor and 1."""
    d = float(duty)
    if not 0.0 < d < 1.0:
        return 1.0
    return 0.5 * math.pi * math.tan(0.5 * math.pi * d)


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
    """Electrical estimate of one stator + rotor.  Build it with Electrics(stator, rotor, P, amp) where amp
    is the receiver amplitude of AnalyzeCoil.py (model units, nominal air gap, rotor centred) - or None when
    there is no sensor model (the receiver voltage is then left out).  rotor may be None (inductance without
    a rotor only), or anything with .r_in, .r_out (mm) and .duty.
    .findings = [(level, code, message), ...]: the checks against RECEIVER_IC at the nominal air gap."""

    def __init__(self, stator, rotor, P, amp=None, prepreg=None, model=None):
        self.P = P
        # the eddy-current model gives the inductance change exactly (a screen model only an upper estimate)
        self.model = model if getattr(model, "kind", "") == "eddy" else None
        self.prepreg = STACKUP_PREPREG_MM if prepreg is None else float(prepreg)
        self.thickness_um = float(getattr(P, "COPPER_THICKNESS_UM", DEFAULT_COPPER_THICKNESS_UM))
        self.width_mm = float(P.TX_TRACE_WIDTH_MM)
        self.loops = tx_loops(stator, P, self.prepreg)
        self.n_turns = int(round(sum(w for _r, _d, w in self.loops)))     # turns in series
        self.L_free = tx_inductance(self.loops, self.width_mm, self.thickness_um)
        self.R_dc, self.length_m = tx_resistance_dc(stator, P, self.thickness_um)
        self.gap = float(P.AIR_GAP_MM)
        self.has_rotor = rotor is not None
        if self.has_rotor:
            self.rotor_in, self.rotor_out, self.duty = float(rotor.r_in), float(rotor.r_out), float(rotor.duty)
            self.sectors = int(getattr(rotor, "sectors", 0) or 0) or None
        else:
            self.rotor_in = self.rotor_out = self.duty = self.sectors = None
        self._L_cache = {}
        self.ic, self.lim = ic_limits(P)
        self.f_target = float(P.EXCITATION_FREQ_HZ)
        # the tank is designed for the target frequency with the rotor in place at the nominal air gap
        self.L_nom = self.L_at(self.gap)
        if not self.L_nom > 0.0:
            raise ValueError("the rotor model gives no inductance left at this air gap (the air gap is too small "
                             "for the estimate)")
        self.C = 1.0 / ((2.0 * math.pi * self.f_target) ** 2 * self.L_nom)
        self.amp = None if amp is None else float(amp)
        # where the real receiver voltage is expected, relative to the ideal-screen value (see crowding_factor)
        crowd = crowding_factor(self.duty) if (self.has_rotor and self.model is None) else 1.0
        self.rx_band = (min(1.0, crowd), max(1.0, crowd))
        tx = getattr(P, "TX_AMPLITUDE_VPP", None)
        self.tx_given = tx is not None
        if self.tx_given:
            self.tx_vpp = (float(tx), float(tx))
        elif self.lim:
            self.tx_vpp = tuple(float(v) for v in self.lim["tx_vpp"])
        else:
            self.tx_vpp = None
        self.findings = []
        self._check()

    # ------------------------------------------------------------ at another air gap / rotor
    def L_at(self, gap, duty=None, r_in=None, r_out=None):
        """TX inductance with the rotor at this air gap (H); without a rotor the free inductance."""
        if not self.has_rotor:
            return self.L_free
        d = self.duty if duty is None else float(duty)
        a = self.rotor_in if r_in is None else float(r_in)
        b = self.rotor_out if r_out is None else float(r_out)
        key = (round(float(gap), 9), round(d, 9), round(a, 9), round(b, 9))
        if key not in self._L_cache:
            if self.model is not None and abs(a - self.model.r_in) < 1e-9 and abs(b - self.model.r_out) < 1e-9:
                self._L_cache[key] = self.L_free + self.model.tx_inductance_change(gap, d)
            else:
                self._L_cache[key] = self.L_free - rotor_inductance_drop(self.loops, a, b, d, gap)
        return self._L_cache[key]

    def f_at(self, L):
        """Oscillator frequency (Hz) with the tank capacitance C and the inductance L."""
        return 1.0 / (2.0 * math.pi * math.sqrt(L * self.C))

    def coupling(self, amp, L):
        """V_RX / V_TX for a receiver amplitude (AnalyzeCoil units) and the TX inductance L."""
        return MODEL_TO_HENRY * float(amp) / L

    def rx_vpp(self, amp, L):
        """(low, high) receiver voltage, peak-to-peak (V), over the TX voltage range; None without one."""
        if self.tx_vpp is None or amp is None:
            return None
        k = self.coupling(amp, L)
        return k * self.tx_vpp[0], k * self.tx_vpp[1]

    def q_range(self, L, f):
        """Q of the coil: (with AC_FACTOR x R_dc, with R_dc)."""
        w = 2.0 * math.pi * f
        return w * L / (AC_FACTOR * self.R_dc), w * L / self.R_dc

    def rp_range(self, L, f):
        """Tank parallel resistance (ohm): (with AC_FACTOR x R_dc, with R_dc)."""
        w = 2.0 * math.pi * f
        return (w * L) ** 2 / (AC_FACTOR * self.R_dc), (w * L) ** 2 / self.R_dc

    def case(self, amp, gap, duty=None):
        """The numbers of one simulated case (air gap, rotor metal fraction, receiver amplitude in model units;
        amp may be None): dict(gap, L, f, k = V_RX / V_TX, rx = (low, high) Vpp or None, rp = lowest R_P)."""
        L = self.L_at(gap, duty)
        f = self.f_at(L)
        return dict(gap=float(gap), L=L, f=f,
                    k=None if amp is None else self.coupling(amp, L),
                    rx=None if amp is None else self.rx_vpp(amp, L),
                    rp=self.rp_range(L, f)[0])

    # ------------------------------------------------------------ IC checks
    def usable_tx(self, cases):
        """(low, high): the TX voltages, within the TX range, at which every one of these cases gives a receiver
        signal inside the IC's input range - or None (no IC, no TX voltage, no receiver amplitude, or no such
        voltage).  The IC sets one TX voltage, so it has to suit every case at the same time."""
        if not self.lim or self.tx_vpp is None:
            return None
        ks = [c["k"] for c in cases if c["k"] is not None]
        if not ks:
            return None
        rmin, rmax = self.lim["rx_vpp"]
        t_lo = max([self.tx_vpp[0]] + [rmin / k if k > 0 else math.inf for k in ks])
        t_hi = min([self.tx_vpp[1]] + [rmax / k if k > 0 else math.inf for k in ks])
        return (t_lo, t_hi) if t_lo <= t_hi * (1.0 + 1e-12) else None

    def rx_status(self, cases):
        """'OK', 'OK only at a ... b Vpp TX' or 'OUTSIDE': the receiver signal of these cases against the IC."""
        u = self.usable_tx(cases)
        if u is None:
            return "OUTSIDE"
        if u[0] <= self.tx_vpp[0] * (1.0 + 1e-9) and u[1] >= self.tx_vpp[1] * (1.0 - 1e-9):
            return "OK"
        return f"OK only at {u[0]:.3g} ... {u[1]:.3g} Vpp TX"

    def check_cases(self, cases, scope):
        """Checks of one or more cases (from case()) against RECEIVER_IC.  scope: where, for the messages
        ("at the nominal air gap", "over the tolerance window" ...).  Returns [(level, code, message), ...]."""
        lim, ic, out = self.lim, self.ic, []
        if not lim or not cases:
            return out
        f_lo, f_hi = min(c["f"] for c in cases), max(c["f"] for c in cases)
        if f_lo < lim["f_min"] or f_hi > lim["f_max"]:
            out.append(("warning", "f_range",
                        f"the oscillator frequency {scope} ({_mhz(f_lo, f_hi)}) is outside the {ic}'s range "
                        f"{lim['f_min'] / 1e6:g} ... {lim['f_max'] / 1e6:g} MHz.  Change EXCITATION_FREQ_HZ"))
        rp = min(c["rp"] for c in cases)
        if rp < lim["rp_min"]:
            out.append(("warning", "rp_low",
                        f"the tank's parallel resistance {scope} may be as low as {rp:.0f} ohm (if the AC resistance "
                        f"is {AC_FACTOR:g} x the DC value); the {ic} needs at least {lim['rp_min']:g} ohm.  More TX "
                        f"turns, wider TX traces, thicker copper or a higher EXCITATION_FREQ_HZ raise it"))
        rx = [c["rx"] for c in cases if c["rx"] is not None]
        if rx:
            weakest = min(r[1] for r in rx)          # the smallest signal, at the largest TX voltage
            strongest = max(r[0] for r in rx)        # the largest signal, at the smallest TX voltage
            rmin, rmax = lim["rx_vpp"]
            tx_lo, tx_hi = self.tx_vpp
            one_tx = tx_lo == tx_hi
            at_hi = f"at {tx_hi:g} Vpp TX" + ("" if one_tx else " (the largest TX voltage)")
            at_lo = f"at {tx_lo:g} Vpp TX" + ("" if one_tx else " (the smallest TX voltage)")
            if weakest < rmin:
                alt = [f"; {name} it accepts down to {_lim(lo)} mVpp" for name, lo, _hi in lim["rx_alt"] if lo <= weakest]
                out.append(("warning", "rx_low",
                            f"the receiver signal {scope} is only {_mv(weakest)} mVpp {at_hi}: below the {ic}'s "
                            f"minimum {_lim(rmin)} mVpp ({lim['rx_note']}){alt[0] if alt else ''}.  A smaller air "
                            f"gap, 2 sub-coils (RX_SUBCOILS), a wider RX band or fewer TX turns (watch the tank "
                            f"resistance) raise it"))
            if strongest > rmax:
                alt = [f"; {name} it accepts up to {_lim(hi)} mVpp" for name, _lo, hi in lim["rx_alt"] if hi >= strongest]
                out.append(("warning", "rx_high",
                            f"the receiver signal {scope} is {_mv(strongest)} mVpp {at_lo}: above the {ic}'s "
                            f"maximum {_lim(rmax)} mVpp ({lim['rx_note']}){alt[0] if alt else ''}.  More TX turns, "
                            f"1 sub-coil or a larger air gap lower it"))
            notes = []
            m_lo = max(MARGIN, 1.0 / self.rx_band[0])        # the real value may be this much lower ...
            m_hi = max(MARGIN, self.rx_band[1])              # ... or higher (at least the general margin)
            if rmin <= weakest < m_lo * rmin:
                notes.append(f"{at_hi} it is {_mv(weakest)} mVpp, less than {m_lo:.3g}x the {ic}'s minimum "
                             f"{_lim(rmin)} mVpp")
            if rmax / m_hi < strongest <= rmax:
                notes.append(f"{at_lo} it is {_mv(strongest)} mVpp, less than {m_hi:.3g}x below the {ic}'s maximum "
                             f"{_lim(rmax)} mVpp")
            if notes:
                out.append(("info", "rx_margin", f"receiver signal {scope}: " + "; ".join(notes)
                            + ".  The model is not checked on hardware: keep a margin"))
            if weakest >= rmin and strongest <= rmax and self.usable_tx(cases) is None:
                out.append(("warning", "rx_span",
                            f"the receiver signal {scope} varies so much that no single TX voltage keeps it inside "
                            f"the {ic}'s input range {_lim(rmin)} ... {_lim(rmax)} mVpp in every case"))
        return out

    def _check(self):
        add, lim, ic = self.findings.append, self.lim, self.ic
        if lim and self.tx_given:
            lo, hi = lim["tx_vpp"]
            if lo < hi and not lo <= self.tx_vpp[0] <= hi:
                add(("warning", "tx_range", f"TX_AMPLITUDE_VPP = {self.tx_vpp[0]:g} Vpp is outside the {ic}'s TX "
                                            f"voltage range {lo:g} ... {hi:g} Vpp"))
        self.findings += self.check_cases([self.case(self.amp, self.gap)], "at the nominal air gap")
        if lim and self.has_rotor and lim["f_min"] <= self.f_target <= lim["f_max"]:
            f_free = self.f_at(self.L_free)
            if not lim["f_min"] <= f_free <= lim["f_max"]:
                add(("info", "f_free", f"with the rotor removed the oscillator would run at {f_free / 1e6:.2f} MHz, "
                                       f"outside the {ic}'s range {lim['f_min'] / 1e6:g} ... {lim['f_max'] / 1e6:g} "
                                       f"MHz (with the rotor it runs between that and "
                                       f"{self.f_target / 1e6:g} MHz)"))

    @property
    def warnings(self):
        return [m for l, _c, m in self.findings if l == "warning"]

    @property
    def warning_codes(self):
        return sorted({c for l, c, _m in self.findings if l == "warning"})

    # ------------------------------------------------------------ text
    def heading(self):
        return ((f"receiver IC {self.ic}" if self.lim else "no receiver IC set (RECEIVER_IC): no IC checks")
                + "; model only, not checked on hardware")

    def title(self):
        return "ELECTRICAL ESTIMATE  (" + self.heading() + ")"

    def tx_text(self):
        """The TX voltage(s) the receiver voltage is given for, e.g. '6 ... 11 Vpp TX'."""
        lo, hi = self.tx_vpp
        return f"{lo:g} Vpp TX" if lo == hi else f"{lo:g} ... {hi:g} Vpp TX"

    def lines(self, title=True):
        """The report lines (no colours; the findings are not in them: print .findings as well)."""
        out = [self.title()] if title else []
        f = self.f_target
        out.append(f"  TX coil     L = {self.L_free * 1e6:.3f} uH with the rotor away")
        if self.has_rotor:
            drop = (self.L_free - self.L_nom) / self.L_free * 100.0
            out.append(f"              L = {self.L_nom * 1e6:.3f} uH with the rotor at the {self.gap:g} mm air gap "
                       + (f"({-drop:+.1f} %, eddy-current model)" if self.model is not None else
                          f"({-drop:+.1f} %: an upper estimate of the drop)"))
        out.append(f"              R = {self.R_dc:.2f} ohm DC ({self.n_turns} turn(s), {self.length_m:.2f} m of "
                   f"{self.width_mm:g} mm x {self.thickness_um:g} um copper), up to about {AC_FACTOR:g}x that at "
                   f"{f / 1e6:g} MHz")
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
        if self.has_rotor and self.model is None:
            out.append("              (the true frequency with the rotor lies between the two: the drop is an upper "
                       "estimate)")
        q_lo, q_hi = self.q_range(self.L_nom, f)
        rp_lo, rp_hi = self.rp_range(self.L_nom, f)
        line = f"              Q = {q_lo:.0f} ... {q_hi:.0f}, parallel resistance {_ohm(rp_lo)} ... {_ohm(rp_hi)}"
        if self.lim:
            line += f"  ({self.ic} needs >= {self.lim['rp_min']:g} ohm: " + (
                "OK)" if rp_lo >= self.lim["rp_min"] else "TOO LOW)")
        out.append(line)
        if self.amp is not None:
            k = self.coupling(self.amp, self.L_nom)
            line = f"  receiver    M = {MODEL_TO_HENRY * self.amp * 1e9:.1f} nH, M/L = {k * 100:.2f} % of the TX voltage"
            rng = self.rx_vpp(self.amp, self.L_nom)
            if rng is not None:
                line += f"  ->  {_mv_range(*rng)} mVpp at {self.tx_text()}"
            out.append(line)
            if rng is not None and self.lim:
                rmin, rmax = self.lim["rx_vpp"]
                ok = self.rx_status([self.case(self.amp, self.gap)])
                out.append(f"              ({self.ic} accepts {_lim(rmin)} ... {_lim(rmax)} mVpp, "
                           f"{self.lim['rx_note']}: {ok})")
            if self.rx_band != (1.0, 1.0):
                up = self.rx_band[1] > 1.0
                out.append("              ideal-screen rotor: the field crowding at the copper edges can "
                           + (f"raise this, up to {self.rx_band[1]:.2g}x" if up else
                              f"lower this, down to {self.rx_band[0]:.2g}x") + ",")
                txt = "              for sectors much narrower than long"
                if self.sectors:
                    width = self.duty * math.pi * (self.rotor_in + self.rotor_out) / self.sectors
                    txt += f" (yours: {width:.1f} mm wide, {self.rotor_out - self.rotor_in:.1f} mm long)"
                out.append(txt + "; see CoilElectrics.py")
        else:
            out.append("  receiver    not estimated (see the note below)")
        return out

    def summary(self):
        """One line: inductance, tank, receiver voltage, IC verdict."""
        txt = f"TX L {self.L_free * 1e6:.2f} uH"
        if self.has_rotor:
            txt += f" ({self.L_nom * 1e6:.2f} with the rotor)"
        txt += f", R {self.R_dc:.2f} ohm DC, tank 2 x {_cap(2 * self.C)} for {self.f_target / 1e6:g} MHz"
        if self.amp is not None:
            rng = self.rx_vpp(self.amp, self.L_nom)
            if rng is not None:
                txt += f", RX {_mv_range(*rng)} mVpp at {self.tx_text()}"
            else:
                txt += f", M/L {self.coupling(self.amp, self.L_nom) * 100:.2f} %"
        if self.lim:
            n = len(self.warnings)
            txt += f"; {self.ic}: " + ("OK" if not n else f"{n} warning(s)")
            if self.amp is None:
                txt += " (receiver voltage not estimated)"
        return txt


def estimate(stator, rotor, P, rotor_model=None):
    """Electrics of a built stator + rotor, with the receiver amplitude and the rotor's effect on the TX inductance
    from AnalyzeCoil.py's model (ROTOR_MODEL there: eddy currents by default; nominal air gap, rotor centred).
    If that model cannot be used (for example a custom rotor whose sector count is not the loop count) the
    receiver voltage is left out and a note says why; rotor None = no rotor."""
    amp, prepreg, why, model = None, None, None, None
    if rotor is not None:
        try:
            import AnalyzeCoil as AC                      # (here, not at the top: AnalyzeCoil imports this file)
            model = AC.make_model(stator, rotor, P, rotor_model=rotor_model)
            prepreg = model.prepreg
            amp = AC.evaluate(model).m["amp_s"]
        except Exception as e:                            # the estimate must never stop a generation
            why = str(e) or type(e).__name__
            model = None
    el = Electrics(stator, rotor, P, amp=amp, prepreg=prepreg, model=model)
    if rotor is None:
        el.findings.append(("info", "no_rotor", "no rotor: the inductance is the one without it, and the receiver "
                                                "voltage needs the rotor"))
    elif amp is None:
        el.findings.append(("info", "no_model", f"the receiver voltage is not estimated: {why}"))
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


def _mv(v):
    """Volts -> millivolt text for a computed value (3 significant digits, at least the whole millivolts)."""
    mv = v * 1e3
    if mv >= 100:
        return f"{mv:.0f}"
    return f"{mv:.1f}" if mv >= 10 else (f"{mv:.2f}" if mv >= 1 else f"{mv:.3f}")


def _lim(v):
    """Volts -> millivolt text for a datasheet limit."""
    return f"{v * 1e3:g}"


def _mv_range(lo, hi):
    return _mv(hi) if lo == hi else f"{_mv(lo)} ... {_mv(hi)}"


def _mhz(lo, hi):
    return f"{lo / 1e6:.3f} MHz" if abs(hi - lo) < 0.5e3 else f"{lo / 1e6:.3f} ... {hi / 1e6:.3f} MHz"
