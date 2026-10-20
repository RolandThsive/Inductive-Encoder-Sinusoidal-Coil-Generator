#!/usr/bin/env python3
"""
RotorBuilder.py
=================
Generates the ROTOR (the "target") for the inductive stator made by
StatorAssembly.py: a PCB carrying N copper sectors, N = number of periods
(LOOPS) of the stator.  Two modes, chosen with ROTOR_MODE in Rotor_Parameters.py:

  "according_to_stator"  the matched rotor is derived from the stator settings
        * sectors            = LOOPS  (one metal sector per electrical period)
        * metal fraction     = ROTOR_AUTO_DUTY, 0.5 = 180 deg electrical.  A
                               copper pattern of fraction k/h has no h-th
                               harmonic, but the field it leaves does (the eddy
                               currents crowd it at the copper edges), so the
                               fraction that suits a coil best has to be found
                               with a model of the eddy currents or on a test
                               rotor.
        * outer edge         = by default (ROTOR_AUTO_COVER_TX = True) the copper
                               runs over the TX turns and ends
                               ROTOR_AUTO_TX_OVERHANG_MM past the outer edge of
                               the outermost TX turn, as in the IC makers'
                               reference designs.  Every sector is a shorted
                               turn driven by the TX flux it encloses, and that
                               flux is densest right beside the TX conductors;
                               in an eddy-current model this gave 5-8 % more
                               receiver signal than ending the copper inside the
                               TX ring.  It never comes
                               closer than ROTOR_AUTO_EDGE_CLEARANCE_MM to the
                               board outline (measured to the outermost polygon
                               vertex, which lies slightly outside the nominal
                               radius).
                               With ROTOR_AUTO_COVER_TX = False:
                               the RX band widened by ROTOR_AUTO_EXTENSION_MM /
                               ROTOR_AUTO_EXTENSION_OUTER_MM, at most up to
                               ROTOR_AUTO_TX_CLEARANCE_MM inside the TX ring.
        * inner edge         = the RX band widened by ROTOR_AUTO_EXTENSION_MM or
                               ROTOR_AUTO_EXTENSION_INNER_MM (None: one air gap),
                               at least ROTOR_AUTO_EDGE_CLEARANCE_MM from the bore;
                               a value that does not fit is cut to that limit.
        * outline / bore     = those of the stator board

  "custom"               every value comes from the ROTOR_CUSTOM_* parameters

Solder mask (both modes): ROTOR_SOLDER_MASK_EXPANSION_MM removes the solder
mask over the rotor copper.  In KiCad a shape drawn on F.Mask / B.Mask is an
OPENING in the mask, so every copper sector gets a matching filled shape on the
mask layer of its copper layer (F.Cu -> F.Mask, B.Cu -> B.Mask).  KiCad has no
expansion setting for a drawn shape, so the margin is built into the shape:
    0.05   the opening is the copper outline grown by 0.05 mm on every side
           (round corners)
    0      the opening is exactly the copper outline
    -1     no opening: the solder mask stays over the copper (the default)

Mount the rotor with its copper side facing the stator, concentric with it.
Seen from the stator side the pattern is mirrored relative to the KiCad
editor; this only reverses the sign of the measured angle.

Output: a KiCad 7+ .kicad_pcb containing the copper sectors (filled copper
polygons, no net), the solder-mask openings over them (F.Mask / B.Mask) and
the Edge.Cuts outline / bore.
"""

import math

import Parameters as P_DEFAULT
from Generator.Core.BoardLayout import tx_shape
from Generator.Core.Geometry import chord_tolerance
from Generator.Core.KiCadWriter import KiCadBoard, page_size
from Generator.Core.Conflict import ParameterConflict

DEFAULT_COPPER_CONDUCTIVITY = 5.8e7  # S/m, used when Board_Parameters.py has no COPPER_CONDUCTIVITY_S_M line
MU0 = 4.0e-7 * math.pi

# used when Rotor_Parameters.py has no such line (ParameterRules.py holds the same numbers)
DEFAULT_SOLDER_MASK_EXPANSION_MM = -1     # the mask stays over the copper
DEFAULT_COVER_TX = True
DEFAULT_TX_OVERHANG_MM = 0.5


def tx_outer_edge(stator, P):
    """Radius of the outer edge of the outermost TX turn (mm).  A spiral turn grows by one pitch per turn, so
    its last turn reaches one pitch farther out than the stepped one."""
    r = float(stator.tx_outer_radius)
    if tx_shape(P) == "spiral":
        r += float(P.TX_PITCH_MM)
    return r + float(P.TX_TRACE_WIDTH_MM) / 2.0


MASK_LAYER = {"F.Cu": "F.Mask", "B.Cu": "B.Mask"}     # the solder-mask layer over each copper layer
MASK_CORNER_STEP_DEG = 7.5                            # largest angle of one segment of a rounded mask corner
MASK_CORNER_TOLERANCE_MM = 0.001                      # a rounded corner is at most this far outside the true circle


def offset_polygon(points, distance, corner_step_deg=MASK_CORNER_STEP_DEG):
    """Grow a simple polygon outward by `distance`: no point of the new outline is closer than `distance`
    to the old polygon, and none is much farther (a vertex lies at most distance / cos(turn / 2) away,
    turn = the angle the outline turns there; rounded corners are cut finely enough to keep that within
    MASK_CORNER_TOLERANCE_MM).  Straight edges move sideways, convex corners get a rounded join (radius
    `distance`) whose chords touch the circle from outside, concave corners get the sharp point where the
    two moved edges meet.  Works for either winding direction."""
    pts = []
    for p in points:                                   # drop repeated points
        if not pts or math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) > 1e-12:
            pts.append((float(p[0]), float(p[1])))
    if len(pts) > 1 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) <= 1e-12:
        pts.pop()
    n = len(pts)
    if n < 3:
        raise ValueError("a polygon needs at least 3 points")
    if distance <= 0.0:
        return pts
    area2 = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    if area2 < 0.0:                                    # make it counter-clockwise: the outside is on the right
        pts.reverse()
    dirs, normals = [], []
    for i in range(n):
        dx, dy = pts[(i + 1) % n][0] - pts[i][0], pts[(i + 1) % n][1] - pts[i][1]
        length = math.hypot(dx, dy)
        dirs.append((dx / length, dy / length))
        normals.append((dy / length, -dx / length))    # outward normal of the edge starting at point i
    # segment angle of a rounded corner: the chords sit up to distance * (1 / cos(step / 2) - 1) outside the circle
    step = min(math.radians(corner_step_deg), 2.0 * math.acos(distance / (distance + MASK_CORNER_TOLERANCE_MM)))
    out = []
    for i in range(n):
        d1, d2, n1, n2 = dirs[i - 1], dirs[i], normals[i - 1], normals[i]
        vx, vy = pts[i]
        turn = math.atan2(d1[0] * d2[1] - d1[1] * d2[0], d1[0] * d2[0] + d1[1] * d2[1])
        if turn > 1e-9:                                # convex corner: rounded join
            m = max(1, int(math.ceil(turn / step - 1e-9)))
            delta = turn / m
            rho = distance / math.cos(delta / 2.0)
            th0 = math.atan2(n1[1], n1[0])
            for j in range(m):
                th = th0 + (j + 0.5) * delta
                out.append((vx + rho * math.cos(th), vy + rho * math.sin(th)))
        else:                                          # straight or concave: the moved edges meet in one point
            k = distance / (1.0 + n1[0] * n2[0] + n1[1] * n2[1])
            out.append((vx + k * (n1[0] + n2[0]), vy + k * (n1[1] + n2[1])))
    return out


class RotorDesign:
    def __init__(self, P=P_DEFAULT, stator=None):
        self.P = P
        mode = str(P.ROTOR_MODE).lower()
        if mode == "according_to_stator":
            self.mode = mode
            if stator is None:
                raise ValueError("the rotor needs the stator it belongs to (RunCoilGenerator.py builds it first)")
            self.stator = stator
            self._from_stator()
        elif mode == "custom":
            self.mode = mode
            self.stator = stator
            self._from_custom()
        else:
            raise ValueError('ROTOR_MODE must be "according_to_stator" or "custom"')
        self._read_mask_setting()
        self._validate()
        self.notes = []
        self._make_notes()

    # ------------------------------------------------------------------ modes
    def _from_stator(self):
        P, st = self.P, self.stator
        self.sectors = st.N
        self.duty = float(P.ROTOR_AUTO_DUTY)
        self.start_angle = math.radians(P.ROTOR_AUTO_START_ANGLE_DEG)
        # how far the copper reaches past the RX band: both edges together, or each edge on its own
        ext = P.AIR_GAP_MM if P.ROTOR_AUTO_EXTENSION_MM is None else float(P.ROTOR_AUTO_EXTENSION_MM)
        given_in = getattr(P, "ROTOR_AUTO_EXTENSION_INNER_MM", None)
        given_out = getattr(P, "ROTOR_AUTO_EXTENSION_OUTER_MM", None)
        want_in = ext if given_in is None else float(given_in)
        self.bore_radius = st.inner_edge_radius
        self.outline_radius = st.outer_edge_radius
        r_in_limit = self.bore_radius + P.EDGE_LINE_WIDTH_MM / 2.0 + P.ROTOR_AUTO_EDGE_CLEARANCE_MM
        self.r_in = max(st.ri - want_in, r_in_limit)
        # an edge that was asked for explicitly (ROTOR_AUTO_EXTENSION_INNER_MM / _OUTER_MM, or ROTOR_AUTO_EXTENSION_MM
        # when it is set) and had to be cut back (DesignChecks reports it, naming the parameter it came from).
        # The default, ROTOR_AUTO_EXTENSION_MM = None (one air gap), is cut back silently.
        all_set = P.ROTOR_AUTO_EXTENSION_MM is not None
        self.cut_in_name = "ROTOR_AUTO_EXTENSION_INNER_MM" if given_in is not None else "ROTOR_AUTO_EXTENSION_MM"
        self.cut_out_name = "ROTOR_AUTO_EXTENSION_OUTER_MM" if given_out is not None else "ROTOR_AUTO_EXTENSION_MM"
        explicit_in = given_in is not None or all_set
        explicit_out = given_out is not None or all_set
        self.cut_in = (None if not explicit_in or st.ri - want_in >= r_in_limit - 1e-9
                       else (want_in, st.ri - r_in_limit))
        self.cover_tx = bool(getattr(P, "ROTOR_AUTO_COVER_TX", DEFAULT_COVER_TX))
        self.tx_outer_edge = tx_outer_edge(st, P)
        self.cut_out = self.cut_overhang = None
        if self.cover_tx:
            # over the TX turns, ending ROTOR_AUTO_TX_OVERHANG_MM past the outermost one, inside the outline
            over = float(getattr(P, "ROTOR_AUTO_TX_OVERHANG_MM", DEFAULT_TX_OVERHANG_MM))
            r_out_limit = self.outline_radius - P.EDGE_LINE_WIDTH_MM / 2.0 - P.ROTOR_AUTO_EDGE_CLEARANCE_MM
            want_out_edge = self.tx_outer_edge + over
            self.r_out = self._fit_outer_vertices(min(want_out_edge, r_out_limit), r_out_limit)
            if want_out_edge > self.r_out + 1e-9:
                self.cut_overhang = (over, self.r_out - self.tx_outer_edge)
        else:
            # (ROTOR_AUTO_EXTENSION_OUTER_MM and ROTOR_AUTO_TX_CLEARANCE_MM are read only here: with the
            # TX covered they are not used, so a leftover value there cannot stop the generator)
            want_out = ext if given_out is None else float(given_out)
            r_out_limit = st.tx_inner_edge - P.ROTOR_AUTO_TX_CLEARANCE_MM
            self.r_out = self._fit_outer_vertices(min(st.ro + want_out, r_out_limit), r_out_limit)
            if explicit_out and st.ro + want_out > self.r_out + 1e-9:
                self.cut_out = (want_out, self.r_out - st.ro)
        self.layers = list(P.ROTOR_AUTO_COPPER_LAYERS)
        self.cx, self.cy = st.cx, st.cy

    def _fit_outer_vertices(self, r_out, limit):
        """The nominal outer radius to use: `r_out`, or less when the outermost polygon vertices (sector_polygon puts
        them at r_out / cos(half a step), farther out than r_out) would pass `limit`.  The number of steps may depend
        on r_out ("auto"), so it is repeated until the vertices fit."""
        self.r_out = r_out
        for _ in range(20):
            fitted = limit * math.cos(self._half_step())
            if self.r_out <= fitted + 1e-12:
                break
            self.r_out = fitted
        return self.r_out

    def _from_custom(self):
        P = self.P
        self.sectors = int(P.ROTOR_CUSTOM_SECTORS)
        self.duty = float(P.ROTOR_CUSTOM_DUTY)
        self.start_angle = math.radians(P.ROTOR_CUSTOM_START_ANGLE_DEG)
        self.r_in = float(P.ROTOR_CUSTOM_INNER_RADIUS_MM)
        self.r_out = float(P.ROTOR_CUSTOM_OUTER_RADIUS_MM)
        self.layers = list(P.ROTOR_CUSTOM_COPPER_LAYERS)
        self.outline_radius = P.ROTOR_CUSTOM_OUTLINE_RADIUS_MM
        self.bore_radius = P.ROTOR_CUSTOM_BORE_RADIUS_MM
        self.cut_in = self.cut_out = self.cut_overhang = None
        self.cut_in_name = self.cut_out_name = None
        self.cover_tx = None
        self.tx_outer_edge = tx_outer_edge(self.stator, P) if self.stator is not None else None
        self.cx, self.cy = float(P.CENTER_X_MM), float(P.CENTER_Y_MM)

    def _read_mask_setting(self):
        """ROTOR_SOLDER_MASK_EXPANSION_MM (both modes): 0 or more = mask opening this many mm wider than the
        copper on every side (0 = exactly the copper outline); exactly -1 = no opening.
        self.mask_expansion is the number of mm, or None for no opening."""
        raw = getattr(self.P, "ROTOR_SOLDER_MASK_EXPANSION_MM", DEFAULT_SOLDER_MASK_EXPANSION_MM)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) \
                or (raw < 0 and raw != -1):
            raise ValueError("ROTOR_SOLDER_MASK_EXPANSION_MM must be 0 or more (mm), or exactly -1 for no "
                             f"mask opening; it is {raw!r}")
        self.mask_expansion = None if raw == -1 else float(raw)

    def _validate(self):
        if self.sectors < 1:
            raise ValueError("rotor needs at least 1 sector")
        if not 0.0 < self.duty < 1.0:
            raise ValueError("rotor duty must be between 0 and 1")
        if not 0.0 < self.r_in < self.r_out:
            names = (("ROTOR_CUSTOM_INNER_RADIUS_MM", "ROTOR_CUSTOM_OUTER_RADIUS_MM") if self.mode == "custom" else
                     ("ROTOR_AUTO_EXTENSION_INNER_MM", "ROTOR_AUTO_EXTENSION_OUTER_MM", "ROTOR_AUTO_TX_OVERHANG_MM"))
            raise ParameterConflict(names, f"the rotor copper has no width: inner radius {self.r_in:.2f} mm, outer radius "
                                    f"{self.r_out:.2f} mm (the outer side may have been limited by the TX ring or the "
                                    f"board outline)")
        if not self.layers or any(l not in ("F.Cu", "B.Cu") for l in self.layers):
            raise ValueError('rotor copper layers must be a list of "F.Cu" / "B.Cu"')
        if self.bore_radius is not None and self.bore_radius >= self.r_in:
            raise ParameterConflict(("ROTOR_CUSTOM_BORE_RADIUS_MM", "ROTOR_CUSTOM_INNER_RADIUS_MM"), f"the rotor bore "
                                    f"({self.bore_radius:g} mm) must be smaller than the inner copper radius "
                                    f"({self.r_in:g} mm)")
        if self.outline_radius is not None and self.outline_radius <= self.r_out:
            raise ParameterConflict(("ROTOR_CUSTOM_OUTLINE_RADIUS_MM", "ROTOR_CUSTOM_OUTER_RADIUS_MM"), f"the rotor outline "
                                    f"({self.outline_radius:g} mm) must be larger than the outer copper radius "
                                    f"({self.r_out:g} mm)")
        e = self.mask_expansion
        if e is not None and e > 0.0:
            # (5 um of room is kept: the rounded corners of the opening may lie up to MASK_CORNER_TOLERANCE_MM
            # outside the true circle)
            if e >= self.r_in - 0.005:
                raise ParameterConflict(("ROTOR_SOLDER_MASK_EXPANSION_MM", "ROTOR_CUSTOM_INNER_RADIUS_MM" if self.mode == "custom"
                                         else "INSIDE_RADIUS_MM"),
                                        f"the mask expansion ({e:g} mm) is not smaller than the inner copper radius "
                                        f"({self.r_in:.2f} mm): the mask opening would reach the rotor centre")
            if self.sectors == 1:
                # the two ends of the single sector face each other across the gap; their openings must not meet
                gap = (1.0 - self.duty) * 2.0 * math.pi
                room = self.r_in * math.sin(min(gap, math.pi) / 2.0)
                if e >= room - 0.005:
                    raise ParameterConflict(("ROTOR_SOLDER_MASK_EXPANSION_MM", "ROTOR_AUTO_DUTY" if self.mode != "custom"
                                             else "ROTOR_CUSTOM_DUTY"),
                                            f"a mask expansion of {e:g} mm is too large for the single rotor sector: the "
                                            f"mask openings at its two ends would run into each other (it must be less "
                                            f"than {max(room - 0.005, 0.0):.3f} mm here). Lower it, or lower the metal "
                                            f"fraction")

    # ---------------------------------------------------------------- geometry
    def arc_steps(self):
        """Chords (straight pieces) on every arc of a sector, n; an arc has n + 1 vertices.  ROTOR_ARC_STEPS_PER_SECTOR,
        or (auto) the fewest (at least 8) whose polygon stays within ROTOR_CHORD_TOLERANCE_MM of the circle (the
        outer vertices sit outside it)."""
        s = getattr(self.P, "ROTOR_ARC_STEPS_PER_SECTOR", "auto")
        if not (isinstance(s, str) and s.lower() == "auto"):
            return max(8, int(s))
        tol = chord_tolerance(self.P, "ROTOR")
        delta = self.duty * 2.0 * math.pi / self.sectors
        half_max = math.acos(self.r_out / (self.r_out + tol))
        return max(8, int(math.ceil(delta / (2.0 * half_max))))

    def _half_step(self):
        """Half the angle of one chord of a sector arc (radians)."""
        return self.duty * 2.0 * math.pi / self.sectors / self.arc_steps() / 2.0

    def sector_polygon(self, k):
        """Closed polygon (list of (x, y)) of sector k."""
        period = 2.0 * math.pi / self.sectors
        n = self.arc_steps()
        a0 = self.start_angle + k * period
        a1 = a0 + self.duty * period
        # vertices sit on a slightly larger circle (r / cos(half step)), so that the straight chords are tangent
        # to the nominal radii.  On the outer arc this keeps the copper from being smaller than requested (its
        # vertices reach up to r_out * (1 / cos(half) - 1) past r_out).  On the inner arc the same shift moves
        # the chords outward, so the inner copper edge lies between r_in and r_in / cos(half): the copper may be
        # narrower than requested there by up to the chord sag.
        half = (a1 - a0) / n / 2.0
        r_out = self.r_out / math.cos(half)
        r_in = self.r_in / math.cos(half)
        pts = []
        for i in range(n + 1):                       # outer arc, counter-clockwise
            a = a0 + (a1 - a0) * i / n
            pts.append((self.cx + r_out * math.cos(a), self.cy + r_out * math.sin(a)))
        for i in range(n + 1):                       # inner arc, back
            a = a1 - (a1 - a0) * i / n
            pts.append((self.cx + r_in * math.cos(a), self.cy + r_in * math.sin(a)))
        return pts

    def mask_polygon(self, k):
        """Solder-mask opening over sector k: the copper polygon grown by ROTOR_SOLDER_MASK_EXPANSION_MM
        (exactly the copper polygon for 0).  Only meaningful when mask_expansion is not None."""
        if self.mask_expansion is None:
            raise ValueError("ROTOR_SOLDER_MASK_EXPANSION_MM = -1: there is no mask opening")
        poly = self.sector_polygon(k)
        return poly if self.mask_expansion == 0.0 else offset_polygon(poly, self.mask_expansion)

    @property
    def mask_layers(self):
        """The mask layer(s) that carry the openings, in the order of the copper layers; [] for no openings."""
        return [] if self.mask_expansion is None else [MASK_LAYER[l] for l in self.layers]

    # ---------------------------------------------------------------- reporting
    def conductivity(self):
        """Copper conductivity (S/m): COPPER_CONDUCTIVITY_S_M (Board_Parameters.py)."""
        return float(getattr(self.P, "COPPER_CONDUCTIVITY_S_M", DEFAULT_COPPER_CONDUCTIVITY))

    def skin_depth_um(self):
        f = float(self.P.EXCITATION_FREQ_HZ)
        return 1e6 * math.sqrt(1.0 / (math.pi * f * MU0 * self.conductivity()))

    def screening_percent(self, thickness_um):
        """Thin-sheet estimate of the share of the TX field that a copper sheet of this thickness keeps
        away from the receiver.  A sheet of sheet conductance s passes a field pattern of spatial
        wavenumber k with the factor 1 / (1 + j*w*mu0*s / (2k)); the pattern has the size of the
        distance to the field source, which is somewhere between the air gap and the air gap plus the
        board thickness.  Returns (low, high) in percent."""
        w = 2.0 * math.pi * float(self.P.EXCITATION_FREQ_HZ)
        q = MU0 * self.conductivity() * thickness_um * 1e-6 * w
        out = []
        for dist_mm in (float(self.P.AIR_GAP_MM), float(self.P.AIR_GAP_MM) + float(self.P.PCB_THICKNESS_MM)):
            r = q * dist_mm * 1e-3 / 2.0
            out.append(100.0 * (1.0 - 1.0 / math.sqrt(1.0 + r * r)))
        return min(out), max(out)

    @staticmethod
    def _reach_text(ext):
        return f"{ext:.2f} mm past the band" if ext >= 0 else f"{-ext:.2f} mm short of the band"

    def _make_notes(self):
        if self.sectors == 1:
            shape = "half disc" if self.duty == 0.5 else f"{self.duty * 360.0:.0f} deg of copper"
            self.notes.append(f"1 sector ({shape}) is mechanically unbalanced: add a non-metal "
                              f"counterweight if the shaft turns fast.")
        if self.stator is not None:
            # how far the copper reaches past the RX band (negative = stops short of it)
            self.ext_in, self.ext_out = self.stator.ri - self.r_in, self.r_out - self.stator.ro
            lam = 2.0 * math.pi * 0.5 * (self.stator.ri + self.stator.ro) / self.sectors
            decay = math.exp(-2.0 * math.pi * self.P.AIR_GAP_MM / lam)
            self.notes.append(f"spatial period at mid radius {lam:.1f} mm -> signal falls about "
                              f"exp(-2*pi*gap/period) = {decay:.2f} at the nominal {self.P.AIR_GAP_MM:g} mm gap")

    def _mask_text(self):
        e = self.mask_expansion
        if e is None:
            return "  solder mask: stays over the copper (ROTOR_SOLDER_MASK_EXPANSION_MM = -1), no mask openings"
        where = ", ".join(self.mask_layers)
        if e == 0.0:
            return f"  solder mask: removed over the copper, openings exactly the copper outline on {where}"
        return f"  solder mask: removed over the copper, openings {e:g} mm wider than the copper on {where}"

    def summary(self):
        lines = [f"Rotor ({self.mode}): {self.sectors} sector(s), metal fraction {self.duty:g} "
                 f"({self.duty * 360.0 / self.sectors:.2f} deg mechanical each)",
                 f"  copper r = {self.r_in:.2f} ... {self.r_out:.2f} mm on {', '.join(self.layers)}, "
                 f"{self.arc_steps()} chords per arc"]
        if self.stator is not None:
            lines.append(f"  RX band r = {self.stator.ri:g} ... {self.stator.ro:g} mm: the copper reaches "
                         f"{self._reach_text(self.ext_in)} at the inner edge and "
                         f"{self._reach_text(self.ext_out)} at the outer edge")
            tx_in, tx_out = self.stator.tx_inner_edge, self.tx_outer_edge
            if self.r_out >= tx_out:
                where = f"covers the TX turns and ends {self.r_out - tx_out:.2f} mm past the outermost one"
            elif self.r_out > tx_in:
                where = f"ends over the TX turns, {tx_out - self.r_out:.2f} mm inside the outermost one"
            else:
                where = f"ends {tx_in - self.r_out:.2f} mm inside the TX ring (it does not cover the TX turns)"
            lines.append(f"  TX turns r = {tx_in:g} ... {tx_out:g} mm (copper): the rotor copper {where}")
        lines.append(self._mask_text())
        lo1, hi1 = self.screening_percent(35.0)
        lo2, hi2 = self.screening_percent(70.0)
        lines += [f"  outline r = {self.outline_radius}, bore r = {self.bore_radius}",
                  f"  copper skin depth at {self.P.EXCITATION_FREQ_HZ / 1e6:g} MHz = "
                  f"{self.skin_depth_um():.0f} um; 35 um copper (1 oz) screens the TX field by about "
                  f"{lo1:.0f}-{hi1:.0f} %, 70 um (2 oz) by about {lo2:.0f}-{hi2:.0f} % (thin-sheet estimate): "
                  f"thicker copper adds little signal"]
        lines += [f"  note: {n}" for n in self.notes]
        return "\n".join(lines)

    # ------------------------------------------------------------------ output
    def page_size(self):
        """The KiCad page (KiCadWriter.page_size) for everything on the rotor board: its outline, or its copper
        and solder-mask openings when it has no outline."""
        r = max(x for x in (self.outline_radius, self.r_out + max(0.0, self.mask_expansion or 0.0)) if x is not None)
        return page_size(self.P, self.cx, self.cy, r)

    def write(self, path):
        """Write the rotor to `path` (RunCoilGenerator.py chooses it: OutputFolders.py)."""
        P = self.P
        if not path:
            raise ValueError("RotorDesign.write needs the file path; boards are written by RunCoilGenerator.py")
        f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
        words = {"F.Cu": "Top", "B.Cu": "Bottom"}
        # (KiCad's default drawing sheet shows Comment1 ... Comment4, Comment1 at the bottom)
        comments = ["Generator: RotorBuilder.py (metal target for the stator)",
                    f"Copper: Sectors: {self.sectors}, Metal Fraction: {self.duty:.4g}, Radius: {f(self.r_in)} ... "
                    f"{f(self.r_out)} mm, Layer: {' + '.join(words.get(l, l) for l in self.layers)}"]
        if self.outline_radius is not None or self.bore_radius is not None:
            comments.append(", ".join(x for x in (
                f"Radius-Outer: {f(self.outline_radius)} mm" if self.outline_radius is not None else "",
                f"Radius-Inner: {f(self.bore_radius)} mm" if self.bore_radius is not None else "") if x))
        thickness = getattr(P, "ROTOR_PCB_THICKNESS_MM", None)
        if thickness is None:
            thickness = P.PCB_THICKNESS_MM                # None = the same board thickness as the stator
        board = KiCadBoard(title="Rotor %d sector%s" % (self.sectors, "" if self.sectors == 1 else "s"),
                           comments=comments, page=self.page_size(), thickness=thickness)
        for layer in self.layers:
            for k in range(self.sectors):
                board.polygon(self.sector_polygon(k), layer)
        if self.mask_expansion is not None:          # shapes on a mask layer are openings in the solder mask
            for layer in self.layers:
                for k in range(self.sectors):
                    board.polygon(self.mask_polygon(k), MASK_LAYER[layer])
        if self.bore_radius is not None:
            board.circle((self.cx, self.cy), self.bore_radius, "Edge.Cuts", P.EDGE_LINE_WIDTH_MM)
        if self.outline_radius is not None:
            board.circle((self.cx, self.cy), self.outline_radius, "Edge.Cuts", P.EDGE_LINE_WIDTH_MM)
        board.save(path)
        return path
