#!/usr/bin/env python3
"""
RotorEddyModel.py  -  eddy currents in the rotor copper: what the rotor really does to the TX field.

Used by AnalyzeCoil.py, OptimizeCoil.py and CoilElectrics.py (it never changes a board).

Why
  The older "ideal screen" model deletes the TX field wherever there is rotor copper and leaves it unchanged
  everywhere else.  A real rotor does not delete anything: its eddy currents keep the field off the copper
  and push it through the gaps and around the copper edges, crowded at the edges.  How much signal the rotor
  gives, how clean it is, and what copper over or past the TX turns does, all follow from those currents -
  so this model computes them.

Model
  * Every sector of rotor copper is a thin, perfect conductor (at 2-5 MHz the skin depth of copper,
    30-45 um, is about one copper thickness): no field goes through it.  Each sector carries its own
    eddy current; the current circulates inside the sector (none flows from one sector to the next).
  * The current is described by a stream function psi (the current flows along the lines psi = const,
    psi = 0 at the copper edges).  The copper is cut into small cells (a polar grid, finest at the copper
    edges, where the current crowds); psi is constant on a cell, which is the same as a current psi around
    the outline of that cell.  The normal field of every such loop in the rotor plane is computed exactly
    (Biot-Savart of its straight pieces), and psi is chosen so that the total normal field is zero at the
    centre of every cell (TX field + field of all the loops of all sectors).
  * A centred rotor sits in an axially symmetric TX field, so all sectors carry the same current, mirror
    symmetric about the middle of the sector: half a sector is solved.  An off-centre or tilted rotor
    adds small fields with one or two periods per turn ("Bloch" parts +/-1, +/-2); those are solved on one
    whole sector.
  * What a coil picks up follows by reciprocity:  flux = sum over the cells of psi x (flux of the coil's own
    field through the cell).  For the receiver coils that field is taken from AnalyzeCoil.py's winding grids
    (the normal field of a coil at the height h above it is -2 pi d/dh of its winding number smoothed over h,
    in units of mu0 / (4 pi)); for the TX coil it is its ring field.  So the same numbers give the receiver
    signal at every rotor angle and the change of the TX inductance.

Units: mm, fields in mu0 / (4 pi) per ampere ("B~"); AnalyzeCoil.py's model units are mu0 / (2 pi), i.e. half.

Checks made: a thin disc in a uniform field (exact: psi = -(R^2 - r^2)^(1/2) / pi^2; the dipole moment
agrees within 0.3-0.8 %), long narrow sectors against the exact 2-D strip result (within 1-2 % on fine
grids), the off-centre path against the centred one (1e-4), convergence with the grid (above).
NOT checked against measurements on hardware.

Needs only Python 3 and numpy.
"""

import math

import numpy as np

# grid of the copper.  The defaults are a compromise between run time and accuracy: compared with much finer
# grids the receiver signal is within about 3 % and the peak angle error within about 5-10 % (good enough
# to rank designs; make the cells smaller for a closer look, at the cost of run time)
RADIAL_CELL_MM = 0.6        # radial cell size in the middle of the copper (finer towards the inner/outer edge)
AZIMUTH_CELL_MM = 1.0       # azimuthal cell size in the middle of a sector (finer towards its radial edges)
MAX_RADIAL_CELLS = 60
MAX_AZIMUTH_CELLS = 40      # per half sector
CHORD_MM = 0.5              # the arcs of a cell outline are cut into straight pieces no longer than this
EXACT_FACTOR = 2.5          # cells closer than this many cell sizes: their outline is summed exactly
FAR_FACTOR = 12.0           # cells farther than this many cell sizes act as point dipoles (between: rectangles)


# =============================================================================
# geometry
# =============================================================================
def _graded_both(a, b, n):
    """n cells from a to b, finest at both ends (cosine spacing)."""
    t = np.linspace(0.0, math.pi, n + 1)
    return a + (b - a) * 0.5 * (1.0 - np.cos(t))


def _graded_end(w, n):
    """n cells from 0 to w, finest at w (the copper edge), coarse at 0 (the middle of the sector)."""
    return w * np.sin(0.5 * math.pi * np.linspace(0.0, 1.0, n + 1))


class Cells:
    """Polar cells (radial edges re, azimuthal edges pe, angles relative to the middle of the sector) as
    closed counter-clockwise polygons.  Fields: rc, pc (centre), area, size, the outline pieces seg_a, seg_b
    (shape S, 2) and seg_cell (the cell of every piece, sorted)."""

    def __init__(self, re, pe):
        self.re, self.pe = np.asarray(re, float), np.asarray(pe, float)
        nr, na = len(self.re) - 1, len(self.pe) - 1
        self.nr, self.na = nr, na
        rl, ph_l = np.meshgrid(self.re[:-1], self.pe[:-1], indexing="ij")
        rh, ph_h = np.meshgrid(self.re[1:], self.pe[1:], indexing="ij")
        self.rl, self.rh, self.pl, self.ph = rl.ravel(), rh.ravel(), ph_l.ravel(), ph_h.ravel()
        self.rc = 0.5 * (self.rl + self.rh)
        self.pc = 0.5 * (self.pl + self.ph)
        self.area = 0.5 * (self.rh ** 2 - self.rl ** 2) * (self.ph - self.pl)
        self.size = np.maximum(self.rh - self.rl, self.rh * (self.ph - self.pl))
        self.n = len(self.rc)
        segs_a, segs_b, owner = [], [], []
        for c in range(self.n):
            pts = self._outline(self.rl[c], self.rh[c], self.pl[c], self.ph[c])
            segs_a.append(pts)
            segs_b.append(np.roll(pts, -1, axis=0))
            owner.append(np.full(len(pts), c))
        self.seg_a = np.concatenate(segs_a)
        self.seg_b = np.concatenate(segs_b)
        self.seg_cell = np.concatenate(owner)

    @staticmethod
    def _arc(r, p0, p1):
        m = max(1, int(math.ceil(abs(p1 - p0) * r / CHORD_MM)))
        t = np.linspace(p0, p1, m + 1)
        return np.stack([r * np.cos(t), r * np.sin(t)], axis=1)

    def _outline(self, r0, r1, p0, p1):
        """Vertices of the cell outline, counter-clockwise (polar angle measured from the x axis)."""
        out_arc = self._arc(r1, p0, p1)                       # outer arc, angle increasing
        in_arc = self._arc(r0, p1, p0)                        # inner arc, angle decreasing
        return np.concatenate([[[r0 * math.cos(p0), r0 * math.sin(p0)]], out_arc, in_arc[:-1]])

    def xy(self, angle=0.0, mirror=False):
        """Cell centres turned by `angle` (and mirrored about the x axis first)."""
        p = -self.pc if mirror else self.pc
        return self.rc * np.cos(p + angle), self.rc * np.sin(p + angle)


def _segments(cells, angle, mirror):
    """Outline pieces of all cells, turned by angle (mirrored about the x axis first: the order of every
    piece is then reversed so that the loops stay counter-clockwise)."""
    a, b = cells.seg_a, cells.seg_b
    if mirror:
        a, b = b * [1.0, -1.0], a * [1.0, -1.0]
    c, s = math.cos(angle), math.sin(angle)
    rot = np.array([[c, -s], [s, c]])
    return a @ rot.T, b @ rot.T


def _seg_bz(ax, ay, bx, by, px, py, h=0.0):
    """Normal field (mu0 / 4 pi per ampere) at (px, py), the height h above or below the plane, of the
    straight current a -> b in the plane."""
    ux, uy, vx, vy = ax - px, ay - py, bx - px, by - py
    h2 = h * h
    lu, lv = np.sqrt(ux * ux + uy * uy + h2), np.sqrt(vx * vx + vy * vy + h2)
    cross = ux * vy - uy * vx
    den = lu * lv * (lu * lv + ux * vx + uy * vy + h2)
    with np.errstate(divide="ignore", invalid="ignore"):
        val = cross * (lu + lv) / den
    return np.where(np.abs(den) > 1e-300, val, 0.0)


def _rect_bz(u, v, p, q):
    """Normal field (B~ units) in the plane at (u, v) of a unit current around the rectangle |x| < p, |y| < q:
    minus the integral of 1 / rho^3 over the rectangle (the point is outside it)."""
    eps = 1e-9 * np.maximum(p, q)

    def nz(a):                                    # on the line of an edge the value is the (continuous) limit
        return np.where(np.abs(a) < eps, eps, a)

    def G(X, Y):
        return -np.sqrt(X * X + Y * Y) / (X * Y)
    X1, X2, Y1, Y2 = nz(-p - u), nz(p - u), nz(-q - v), nz(q - v)
    return -(G(X2, Y2) - G(X1, Y2) - G(X2, Y1) + G(X1, Y1))


def loop_field_matrix(cells, px, py, images, near_factor=None, h=0.0):
    """F[i, j] = normal field at the points (px[i], py[i]) (the height h off the plane) of a unit current
    around cell j, summed over the images [(angle, mirror, weight), ...] (weight may be complex: Bloch phase).
    In the plane: cells closer than EXACT_FACTOR sizes are summed exactly over their outline pieces, cells
    farther than FAR_FACTOR sizes act as point dipoles (-area / rho^3), the ones between as rectangles of the
    same size (exact integral of 1 / rho^3).  Off the plane (h > 0): exact within near_factor sizes, dipoles
    beyond."""
    px, py = np.asarray(px, float), np.asarray(py, float)
    n_p, n_c = len(px), cells.n
    dtype = complex if any(isinstance(w, complex) for _, _, w in images) else float
    F = np.zeros((n_p, n_c), dtype=dtype)
    starts = np.searchsorted(cells.seg_cell, np.arange(n_c))
    counts = np.diff(np.append(starts, len(cells.seg_cell)))
    max_seg = int(counts.max())
    exact_f = (EXACT_FACTOR if h == 0.0 else FAR_FACTOR) if near_factor is None else near_factor
    half_r = 0.5 * (cells.rh - cells.rl)
    half_t = 0.5 * cells.rc * (cells.ph - cells.pl)
    for angle, mirror, weight in images:
        cx, cy = cells.xy(angle, mirror)
        pc = (-cells.pc if mirror else cells.pc) + angle
        er_x, er_y = np.cos(pc), np.sin(pc)
        sa, sb = _segments(cells, angle, mirror)
        pad_a = np.zeros((n_c, max_seg, 2))
        pad_b = np.zeros((n_c, max_seg, 2))
        idx = np.arange(len(cells.seg_cell)) - starts[cells.seg_cell]
        pad_a[cells.seg_cell, idx] = sa
        pad_b[cells.seg_cell, idx] = sb                       # (padding: a = b = 0, field 0)
        chunk = max(1, int(4.0e6 // max(n_c, 1)))
        for s0 in range(0, n_p, chunk):
            qx, qy = px[s0:s0 + chunk, None], py[s0:s0 + chunk, None]
            dx, dy = qx - cx[None, :], qy - cy[None, :]
            rho2 = dx * dx + dy * dy
            size2 = cells.size[None, :] ** 2
            with np.errstate(divide="ignore", invalid="ignore"):
                block = cells.area[None, :] * (2.0 * h * h - rho2) / (rho2 + h * h) ** 2.5
            if h == 0.0:
                mid = (rho2 < FAR_FACTOR ** 2 * size2) & (rho2 >= exact_f ** 2 * size2)
                ii, jj = np.nonzero(mid)
                if len(ii):
                    ddx, ddy = dx[ii, jj], dy[ii, jj]
                    u = ddx * er_x[jj] + ddy * er_y[jj]
                    v = -ddx * er_y[jj] + ddy * er_x[jj]
                    block[ii, jj] = _rect_bz(u, v, half_r[jj], half_t[jj])
            near = rho2 + h * h < exact_f ** 2 * size2
            ii, jj = np.nonzero(near)
            if len(ii):
                A, B = pad_a[jj], pad_b[jj]                   # (k, max_seg, 2)
                val = _seg_bz(A[..., 0], A[..., 1], B[..., 0], B[..., 1],
                              qx[ii, 0][:, None], qy[ii, 0][:, None], h).sum(axis=1)
                block[ii, jj] = val
            F[s0:s0 + chunk] += weight * block
    return F


# =============================================================================
# one rotor
# =============================================================================
class EddyRotor:
    """Eddy currents of a rotor of `sectors` identical sectors of copper from r_in to r_out (mm), metal
    fraction duty; sector k spans the angles start + k T ... start + k T + duty T (T = 2 pi / sectors).

    solve_sym(b)        psi on half a sector for a TX field with the rotor's symmetry: b(r) at the cell
                        centres (the field depends on the radius only)
    solve_any(B)        psi on all sectors for any field (an off-centre or tilted rotor), B[k] at the cells of
                        one whole sector of sector k; the operator is split into N Bloch blocks
    """

    def __init__(self, r_in, r_out, duty, sectors, start=0.0, radial_cell=None, azimuth_cell=None):
        self.r_in, self.r_out, self.duty = float(r_in), float(r_out), float(duty)
        self.N = int(sectors)
        self.start = float(start)
        if not (0.0 < self.r_in < self.r_out and 0.0 < self.duty < 1.0 and self.N >= 1):
            raise ValueError("eddy model: the rotor needs 0 < inner < outer radius and 0 < metal fraction < 1")
        self.T = 2.0 * math.pi / self.N
        self.w = 0.5 * self.duty * self.T                       # half width of a sector (rad)
        dr = RADIAL_CELL_MM if radial_cell is None else float(radial_cell)
        da = AZIMUTH_CELL_MM if azimuth_cell is None else float(azimuth_cell)
        span = self.r_out - self.r_in
        nr = int(min(MAX_RADIAL_CELLS, max(8, math.ceil(0.5 * math.pi * span / dr))))
        na = int(min(MAX_AZIMUTH_CELLS, max(6, math.ceil(0.5 * math.pi * self.w * self.r_out / da))))
        self.half = Cells(_graded_both(self.r_in, self.r_out, nr), _graded_end(self.w, na))
        self._inv_sym = None
        self._full = None
        self._bloch = None

    # middle angle of sector k (rotor frame)
    def centre(self, k=0):
        return self.start + self.w + k * self.T

    # ------------------------------------------------------------ symmetric (centred rotor)
    def _sym_operator(self):
        h = self.half
        px, py = h.xy(0.0)
        images = [(k * self.T, m, 1.0) for k in range(self.N) for m in (False, True)]
        return loop_field_matrix(h, px, py, images)

    def solve_sym(self, b):
        """psi (amperes per ampere of TX current) on the cells of half a sector, for the field b at their
        centres (B~ units)."""
        if self._inv_sym is None:
            self._inv_sym = np.linalg.inv(self._sym_operator())
        return -(self._inv_sym @ np.asarray(b, dtype=float))

    # ------------------------------------------------------------ one whole sector
    def full_cells(self):
        """Cells of one whole sector (angles from -w to w around the middle of the sector)."""
        if self._full is None:
            h = self.half
            pe = np.concatenate([-h.pe[::-1], h.pe[1:]])
            self._full = Cells(h.re, pe)
        return self._full

    # ------------------------------------------------------------ any field (off-centre / tilted rotor)
    BLOCH_MAX = 2            # Bloch parts 0, +-1, +-2: an off-centre / tilted rotor to second order

    def bloch_parts(self):
        """The Bloch parts m (0 <= m < N) that are solved: m = 0, +-1, +-2 (mod N)."""
        return sorted({m % self.N for m in range(-self.BLOCH_MAX, self.BLOCH_MAX + 1)})

    def bloch_inverses(self):
        """{m: inverse of Bloch block m} of the whole-rotor operator on the cells of one whole sector: block m
        acts on the part of psi that changes by e^(i m T) from one sector to the next.  Block N - m is the
        complex conjugate of block m (the operator is real), so only one of each pair is inverted."""
        if self._bloch is None:
            fc = self.full_cells()
            px, py = fc.xy(self.centre(0))
            need = sorted({min(m, (self.N - m) % self.N) for m in self.bloch_parts()})
            G = {m: np.zeros((fc.n, fc.n), dtype=complex if m else float) for m in need}
            for q in range(self.N):
                A = loop_field_matrix(fc, px, py, [(self.centre(q), False, 1.0)])
                for m in need:
                    G[m] += A * np.exp(1j * m * q * self.T) if m else A
            inv = {m: np.linalg.inv(g) for m, g in G.items()}
            self._bloch = {}
            for m in self.bloch_parts():
                k = min(m, (self.N - m) % self.N)
                self._bloch[m] = inv[k] if k == m else np.conj(inv[k])
        return self._bloch

    def solve_any(self, B):
        """psi (shape N x cells of a whole sector) for the field B (same shape: B[k] at the cells of sector k);
        Bloch parts beyond +-2 are left out (they are of third order in an offset or tilt)."""
        inv = self.bloch_inverses()
        Bh = np.fft.fft(np.asarray(B, dtype=float), axis=0)
        U = np.zeros(Bh.shape, dtype=complex)
        for m, im in inv.items():
            U[m] = -(im @ Bh[m])
        return np.real(np.fft.ifft(U, axis=0))

    def solve_any_batch(self, B):
        """solve_any for many fields at once: B has the shape (cases, N, cells); returns the same shape."""
        inv = self.bloch_inverses()
        Bh = np.fft.fft(np.asarray(B, dtype=float), axis=1)
        U = np.zeros(Bh.shape, dtype=complex)
        for m, im in inv.items():
            U[:, m, :] = -(Bh[:, m, :] @ im.T)
        return np.real(np.fft.ifft(U, axis=1))

    def full_positions(self, theta=0.0):
        """Rotor-frame polar coordinates (r, phi) of the centres of the whole-sector cells of every sector,
        turned by theta: arrays of shape (N, cells)."""
        fc = self.full_cells()
        ang = fc.pc[None, :] + np.array([self.centre(k) for k in range(self.N)])[:, None] + theta
        return np.broadcast_to(fc.rc, ang.shape), ang


# =============================================================================
# the sensor model (same interface as AnalyzeCoil.SensorModel)
# =============================================================================
import AnalyzeCoil as AC                      # noqa: E402  (AnalyzeCoil imports this module only when it is used)

SENS_DH_MM = 0.05            # step of the height derivatives of the coil fields
SUB_POINT_MM = 0.4           # an off-centre / tilted rotor: points per cell for the coupling to the coils


class EddySensorModel(AC.SensorModel):
    """AnalyzeCoil.SensorModel with the rotor as a thin, perfectly conducting sheet carrying eddy currents (see
    the top of this file) instead of an ideal screen.  Same methods and units (receiver signals in
    AnalyzeCoil's model units, mu0 / 2 pi per ampere x mm).  Extra: tx_inductance_change(gap)."""

    kind = "eddy"

    def __init__(self, stator, rotor, P, prepreg=None, ncol=None, dr=None, blur=None, reach=None, true3d=None):
        super().__init__(stator, rotor, P, prepreg=prepreg, ncol=ncol, dr=dr, blur=True, reach=reach, true3d=true3d)
        self._rotors = {}
        self._sgrid = {}
        self._sfft = {}
        self._wcache = {}

    # ------------------------------------------------------------ rotor geometry
    def set_rotor_extent(self, r_in=None, r_out=None):
        super().set_rotor_extent(r_in, r_out)

    def rotor_at(self, duty=None):
        """EddyRotor of the current radial extent and this metal fraction (cached)."""
        d = self.duty if duty is None else float(duty)
        key = (round(d, 9), round(self.r_in, 9), round(self.r_out, 9))
        if key not in self._rotors:
            if len(self._rotors) > 64:                    # (the optimiser tries many; keep memory bounded)
                self._rotors.pop(next(iter(self._rotors)))
            self._rotors[key] = EddyRotor(self.r_in, self.r_out, d, self.Nrot, start=self.start)
        return self._rotors[key]

    def drive(self, r, gap):
        """Normal TX field (B~ units, per ampere) at the rotor plane at the radii r."""
        return 2.0 * self._bz(np.asarray(r, dtype=float), float(gap))

    def drive_dh(self, r, gap, d=SENS_DH_MM):
        r = np.asarray(r, dtype=float)
        return (self.drive(r, gap + d) - self.drive(r, max(gap - d, 1e-3))) / (gap + d - max(gap - d, 1e-3))

    # ------------------------------------------------------------ the receiver coils seen from the rotor
    def coil_fields(self, gap):
        """Normal field (B~ units) of each receiver coil carrying 1 A, at the rotor plane: arrays (ncol, nr)."""
        key = round(float(gap), 6)
        if key not in self._sgrid:
            d = SENS_DH_MM
            if self.layer_grids is None:
                # (TRUE_3D_GEOMETRY = False) the copper counted half on each RX layer
                up = AC.blur_grids(self.grids, [gap + x + d for x in self.rx_depths], 1)
                dn = AC.blur_grids(self.grids, [gap + x - d for x in self.rx_depths], 1)
                self._sgrid[key] = [-2.0 * math.pi * (u.n - v.n) / (2.0 * d) for u, v in zip(up, dn)]
            else:
                # every per-layer loop from its own distance, plus the exact remainder of the split (RealCopper)
                up, dn = self.layer_blur(gap + d, 1), self.layer_blur(gap - d, 1)
                self._sgrid[key] = [-2.0 * math.pi * (u.n - v.n) / (2.0 * d) + self.chord_field(c, gap)
                                    for c, (u, v) in enumerate(zip(up, dn))]
            if len(self._sgrid) > 12:
                self._sgrid.pop(next(iter(self._sgrid)))
        return self._sgrid[key]

    def _coil_fft(self, gap):
        """Azimuthal Fourier transforms of coil_fields: (modes, nr) complex, integral of s e^(-i m phi) d phi."""
        key = round(float(gap), 6)
        if key not in self._sfft:
            phi0 = self.grids[0]._centres[0]
            out = []
            for s in self.coil_fields(gap):
                S = np.fft.rfft(s, axis=0) * self.delta
                m = np.arange(S.shape[0])
                out.append(S * np.exp(-1j * m * phi0)[:, None])
            self._sfft[key] = out
            if len(self._sfft) > 12:
                self._sfft.pop(next(iter(self._sfft)))
        return self._sfft[key]

    def _radial_weights(self, re):
        """W[i, row] = integral of r dr over the part of model row `row` inside the radial cell i (edges re)."""
        key = tuple(np.round(re, 9))
        if key not in self._wcache:
            a, b = self.r_edges[:-1], self.r_edges[1:]
            lo = np.maximum(re[:-1, None], a[None, :])
            hi = np.minimum(re[1:, None], b[None, :])
            self._wcache[key] = np.where(hi > lo, 0.5 * (hi * hi - lo * lo), 0.0)
            if len(self._wcache) > 64:
                self._wcache.pop(next(iter(self._wcache)))
        return self._wcache[key]

    # ------------------------------------------------------------ centred rotor
    def psi_centred(self, gap, duty=None):
        """(rotor, psi on half a sector (radial x azimuthal cells)) for the centred rotor."""
        rot = self.rotor_at(duty)
        h = rot.half
        psi = rot.solve_sym(self.drive(h.rc, gap))
        return rot, psi.reshape(h.nr, h.na)

    def signals_centred(self, theta, gap=None, duty=None, rotor_reach=True):
        gap = float(self.P.AIR_GAP_MM if gap is None else gap)
        duties = np.atleast_1d(np.asarray(self.duty if duty is None else duty, dtype=float))
        theta = np.asarray(theta, dtype=float)
        Sh = self._coil_fft(gap)
        out = [np.zeros((len(duties), len(theta))) for _ in Sh]
        for di, d in enumerate(duties):
            rot, psi = self.psi_centred(gap, d)
            h = rot.half
            N = rot.N
            ms = np.arange(0, Sh[0].shape[0], N)
            mf = ms.astype(float)
            with np.errstate(divide="ignore", invalid="ignore"):
                F = 2.0 * (np.sin(np.outer(h.pe[1:], mf)) - np.sin(np.outer(h.pe[:-1], mf))) / mf[None, :]
            F[:, 0] = 2.0 * (h.pe[1:] - h.pe[:-1])
            F = F * (N * np.exp(-1j * mf * rot.centre(0)))[None, :]          # (azimuthal cells, modes)
            A = self._radial_weights(h.re).T @ (psi @ F)                     # (rows, modes)
            ph = np.exp(1j * np.outer(theta, mf))                            # (theta, modes)
            for c, S in enumerate(Sh):
                cm = np.sum(S[ms, :].T * np.conj(A), axis=0)                 # (modes)
                cm[1:] *= 2.0
                out[c][di] = np.real(ph @ cm) / (2.0 * math.pi) / 2.0      # -> AnalyzeCoil units (mu0 / 2 pi)
        dc = self.direct()                                                  # direct TX-to-receiver coupling
        rp = self.ripple(theta, gap, duties, rotor_reach)                  # TX copper beyond its average (1st order)
        out = [o + x + r for o, x, r in zip(out, dc, rp)]
        if np.ndim(duty) == 0:
            return out[0][0], out[1][0]
        return out[0], out[1]

    def tx_inductance_change(self, gap=None, duty=None):
        """Change of the TX inductance (H) caused by the centred rotor at this air gap (negative)."""
        gap = float(self.P.AIR_GAP_MM if gap is None else gap)
        rot, psi = self.psi_centred(gap, duty)
        h = rot.half
        b = self.drive(h.rc, gap)
        return 2.0 * rot.N * float(np.sum(psi.ravel() * b * h.area)) * 1e-10      # mu0/4pi * mm -> H

    # ------------------------------------------------------------ off-centre / tilted rotor
    def _subpoints(self, rot):
        """Points spread over every cell of one whole sector (for the coupling to the coil fields)."""
        if getattr(rot, "_subpoints", None) is None:
            fc = rot.full_cells()
            r_all, p_all, w_all, c_all = [], [], [], []
            for c in range(fc.n):
                nr_ = max(1, int(math.ceil((fc.rh[c] - fc.rl[c]) / SUB_POINT_MM)))
                na_ = max(1, int(math.ceil(fc.rh[c] * (fc.ph[c] - fc.pl[c]) / SUB_POINT_MM)))
                re = np.linspace(fc.rl[c], fc.rh[c], nr_ + 1)
                pe = np.linspace(fc.pl[c], fc.ph[c], na_ + 1)
                rm, pm = 0.5 * (re[1:] + re[:-1]), 0.5 * (pe[1:] + pe[:-1])
                wr = 0.5 * (re[1:] ** 2 - re[:-1] ** 2)
                R, Ph = np.meshgrid(rm, pm, indexing="ij")
                W = np.outer(wr, pe[1:] - pe[:-1])
                r_all.append(R.ravel()); p_all.append(Ph.ravel()); w_all.append(W.ravel())
                c_all.append(np.full(R.size, c))
            rot._subpoints = (np.concatenate(r_all), np.concatenate(p_all), np.concatenate(w_all),
                              np.concatenate(c_all))
        return rot._subpoints

    def _interp(self, field, r, phi):
        """Bilinear value of a grid field (ncol, nr) at polar points (r, phi) (stator frame)."""
        u = ((phi - self.grids[0]._centres[0]) / self.delta) % self.ncol
        j0 = np.floor(u).astype(np.int64)
        fu = u - j0
        j1 = (j0 + 1) % self.ncol
        j0 %= self.ncol
        v = np.clip((r - self.rc[0]) / (self.rc[1] - self.rc[0]), 0.0, self.nr - 1.000001)
        i0 = np.floor(v).astype(np.int64)
        fv = v - i0
        i1 = np.minimum(i0 + 1, self.nr - 1)
        return ((field[j0, i0] * (1 - fv) + field[j0, i1] * fv) * (1 - fu)
                + (field[j1, i0] * (1 - fv) + field[j1, i1] * fv) * fu)

    def _sector0(self, rot, alphas, gap, ecc):
        """Everything sector 0 needs when it is turned by the angles `alphas` (rotor frame -> stator frame, plus
        the offset ecc): drive at its cell centres (b0, and the tilt parts bx, by: d/dh of the drive times the
        stator x, y of the cell) and its coupling to the two coils (phi0, and the tilt parts phix, phiy).
        Arrays (len(alphas), cells) and (2 coils, len(alphas), cells)."""
        fc = rot.full_cells()
        ex, ey = float(ecc[0]), float(ecc[1])
        rs, ps, ws, cs = self._subpoints(rot)
        s0 = self.coil_fields(gap)
        d = SENS_DH_MM
        lo = max(gap - d, 1e-3)
        sp, sm = self.coil_fields(gap + d), self.coil_fields(lo)
        sdh = [(a - b) / (gap + d - lo) for a, b in zip(sp, sm)]
        # the drive and its height derivative are functions of the radius only: tabulate them once
        r_tab = np.linspace(max(0.1, rot.r_in - 1.0), rot.r_out + 1.0, 4001)
        b_tab, bh_tab = self.drive(r_tab, gap), self.drive_dh(r_tab, gap)
        n_a = len(alphas)
        b0, bx, by = (np.empty((n_a, fc.n)) for _ in range(3))
        phi = np.empty((2, 3, n_a, fc.n))
        c0 = rot.centre(0)
        chunk = max(1, int(3.0e6 // max(len(rs), 1)))
        for a0 in range(0, n_a, chunk):
            al = np.asarray(alphas[a0:a0 + chunk])[:, None]
            ang = fc.pc[None, :] + c0 + al
            xc, yc = fc.rc[None, :] * np.cos(ang) + ex, fc.rc[None, :] * np.sin(ang) + ey
            rc_s = np.hypot(xc, yc)
            b0[a0:a0 + chunk] = np.interp(rc_s, r_tab, b_tab)
            bh = np.interp(rc_s, r_tab, bh_tab)
            bx[a0:a0 + chunk], by[a0:a0 + chunk] = bh * xc, bh * yc
            ang = ps[None, :] + c0 + al
            xs, ys = rs[None, :] * np.cos(ang) + ex, rs[None, :] * np.sin(ang) + ey
            r_s, p_s = np.hypot(xs, ys), np.arctan2(ys, xs)
            rows = (np.arange(al.shape[0])[:, None] * fc.n + cs[None, :]).ravel()
            nn = al.shape[0] * fc.n
            for c in range(2):
                f0 = self._interp(s0[c], r_s, p_s) * ws[None, :]
                fh = self._interp(sdh[c], r_s, p_s) * ws[None, :]
                for j, f in enumerate((f0, fh * xs, fh * ys)):
                    phi[c, j, a0:a0 + chunk] = np.bincount(rows, weights=f.ravel(), minlength=nn).reshape(-1, fc.n)
        return b0, bx, by, phi

    def signal_parts(self, theta, gap=None, ecc=(0.0, 0.0), duty=None, rotor_reach=True):
        """Receiver signals of an off-centre rotor (exact in the offset) split into the part without tilt and the
        two tilt terms, as AnalyzeCoil.SensorModel.signal_parts: array (2 coils, 3, len(theta)).  The rotor sheet
        is solved at every rotor angle (all sectors, Bloch parts up to +-2); a tilt changes the height of the
        copper above the TX turns and above the receiver coils (first order in the tilt).
        The part without tilt is the exact centred signal (signals_centred) plus what the offset changes, so
        that the small integration error of the per-angle path cancels."""
        gap = float(self.P.AIR_GAP_MM if gap is None else gap)
        theta = np.asarray(theta, dtype=float)
        # The rotor repeats after one sector pitch T and the offset and the two tilt parts are fixed to the stator,
        # so turning the rotor by T gives the same copper in the same field: the parts repeat after T.  Only the
        # angles within one pitch are computed.
        T = 2.0 * math.pi / self.Nrot
        red = np.mod(theta, T)
        key = np.round(red / T * 2.0 ** 30).astype(np.int64) % (2 ** 30)
        uniq, inv = np.unique(key, return_inverse=True)
        th_u = uniq.astype(float) / 2.0 ** 30 * T
        parts = self._parts_direct(th_u, gap, ecc, duty)
        base = parts if (ecc[0] == 0.0 and ecc[1] == 0.0) else self._parts_direct(th_u, gap, (0.0, 0.0), duty)
        vs, vc = self.signals_centred(th_u, gap=gap, duty=duty)
        parts[0, 0] += vs - base[0, 0]
        parts[1, 0] += vc - base[1, 0]
        return parts[:, :, inv]

    def _parts_direct(self, theta, gap, ecc, duty):
        ckey = (round(gap, 6), round(float(ecc[0]), 9), round(float(ecc[1]), 9),
               None if duty is None else round(float(duty), 9), round(self.r_in, 9), round(self.r_out, 9),
               len(theta), float(theta[0]) if len(theta) else 0.0, float(theta[-1]) if len(theta) else 0.0)
        cache = self.__dict__.setdefault("_parts_cache", {})
        if ckey in cache:
            return cache[ckey].copy()
        rot = self.rotor_at(duty)
        N, T = rot.N, rot.T
        # sector k at the rotor angle theta is sector 0 at theta + k T: work out sector 0 at all those angles
        A = (theta[:, None] + T * np.arange(N)[None, :]) % (2.0 * math.pi)
        key = np.round(A / (2.0 * math.pi) * 2.0 ** 30).astype(np.int64)
        uniq, inv_idx = np.unique(key.ravel(), return_inverse=True)
        first = np.zeros(len(uniq), dtype=np.int64)
        first[inv_idx[::-1]] = np.arange(A.size)[::-1]
        alphas = A.ravel()[first]
        b0, bx, by, phi = self._sector0(rot, alphas, gap, ecc)
        idx = inv_idx.reshape(A.shape)                                     # (theta, sector) -> unique angle
        out = np.zeros((2, 3, len(theta)))
        psis = [rot.solve_any_batch(B[idx]) for B in (b0, bx, by)]         # each (theta, N, cells)
        P0 = phi[:, 0][:, idx]                                               # (coil, theta, N, cells)
        P1, P2 = phi[:, 1][:, idx], phi[:, 2][:, idx]
        for c in range(2):
            out[c, 0] = np.sum(psis[0] * P0[c], axis=(1, 2))
            out[c, 1] = np.sum(psis[1] * P0[c], axis=(1, 2)) + np.sum(psis[0] * P1[c], axis=(1, 2))
            out[c, 2] = np.sum(psis[2] * P0[c], axis=(1, 2)) + np.sum(psis[0] * P2[c], axis=(1, 2))
        out /= 2.0                                                          # -> AnalyzeCoil units
        if len(cache) > 8:
            cache.pop(next(iter(cache)))
        cache[ckey] = out.copy()
        return out

    def signals(self, theta, gap=None, ecc=(0.0, 0.0), tilt=None, duty=None, rotor_reach=True):
        if (ecc[0] == 0.0 and ecc[1] == 0.0) and (tilt is None or tilt[0] == 0.0):
            return self.signals_centred(theta, gap=gap, duty=duty)
        theta = np.asarray(theta, dtype=float)
        parts = self.signal_parts(theta, gap=gap, ecc=ecc, duty=duty)
        if tilt is None or tilt[0] == 0.0:
            return parts[0, 0], parts[1, 0]
        kappa = math.tan(math.radians(tilt[0]))
        psi = math.radians(tilt[1]) + (theta if tilt[2] == "rotor" else 0.0)
        v = parts[:, 0] + kappa * (np.cos(psi) * parts[:, 1] + np.sin(psi) * parts[:, 2])
        return v[0], v[1]
