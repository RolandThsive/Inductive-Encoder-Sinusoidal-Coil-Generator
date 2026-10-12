"""
RealCopper.py  -  the stator's real copper in 3-D, for AnalyzeCoil.py and RotorEddyModel.py (not a tool of its own;
nothing to edit here).

Receiver coils
  Every trace sits at the real depth of its layer.  Each coil (one closed series loop that changes layers at
  vias) is split into closed loops per layer, so that the existing fast machinery (winding numbers on a polar
  grid, smoothed across the distance to the rotor) can treat each at its own distance:
      base loop  = the coil's pieces on the base layer + the straight chord across every piece on another layer
      lens loops = every piece on another layer, closed by its chord (on that layer)
  The sum of the loops is the coil; what is left over is each chord once at the depth of its piece and once
  (backwards) at the depth of the base layer.  That remainder is computed exactly (Biot-Savart of the straight
  chords), so the split is exact.  Vias carry vertical current: it has no field normal to the board, so it
  does not couple to the rotor at all; in the direct TX-to-receiver coupling it is included.

TX coil
  The TX is taken from its real copper: the turns with their radial steps, the tails, the go-around runs and
  brackets, every layer at its depth.  Where the TX branches (a parallel TX), the current split is the DC split
  of the copper network (every trace has the same width, so a resistance proportional to its length).
  * rings(): the part of the TX current that is the same at every azimuth (the azimuthal average), as rings -
    what drives the rotor, centred, in the analysis.
  * the direct TX-to-receiver coupling without any rotor (Neumann double line integral over the real copper of
    both coils, vias included): an ideal sensor has none; the real copper leaves a little, which appears as an
    offset of the receiver signals.

Needs only Python 3 and numpy.
"""

import collections
import math

import numpy as np

GL_X, GL_W = np.polynomial.legendre.leggauss(3)          # Gauss points per receiver piece (Neumann integral)
CHORD_REACH_MM = 15.0       # the remainder of the per-layer split: copper within this distance of a point counts


# =============================================================================
# field of straight horizontal current pieces
# =============================================================================
def seg_bz(ax, ay, bx, by, px, py, h=0.0):
    """Normal field (mu0 / 4 pi per ampere, 1/mm) at (px, py), the height h above or below the plane, of the
    straight current a -> b in the plane (the same formula as RotorEddyModel._seg_bz)."""
    ux, uy, vx, vy = ax - px, ay - py, bx - px, by - py
    h2 = h * h
    lu, lv = np.sqrt(ux * ux + uy * uy + h2), np.sqrt(vx * vx + vy * vy + h2)
    cross = ux * vy - uy * vx
    den = lu * lv * (lu * lv + ux * vx + uy * vy + h2)
    with np.errstate(divide="ignore", invalid="ignore"):
        val = cross * (lu + lv) / den
    return np.where(np.abs(den) > 1e-300, val, 0.0)


def pieces_bz(A, B, w, px, py, h, chunk=64):
    """Sum over the pieces A[i] -> B[i] (weights w) of the normal field at the points (px, py), height h."""
    out = np.zeros(np.shape(px))
    for s in range(0, len(A), chunk):
        a, b, ww = A[s:s + chunk], B[s:s + chunk], w[s:s + chunk]
        v = seg_bz(a[:, 0, None], a[:, 1, None], b[:, 0, None], b[:, 1, None], px[None, :], py[None, :], h)
        out += ww @ v
    return out


# =============================================================================
# receiver coils: closed loops per layer
# =============================================================================
def _line(a, b, step=0.2):
    """Points from a to b on the straight line, at most `step` mm apart (both ends included)."""
    n = max(1, int(math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / step)))
    t = np.linspace(0.0, 1.0, n + 1)[:, None]
    return np.asarray(a, float)[None, :] * (1.0 - t) + np.asarray(b, float)[None, :] * t


def _closure(p, centre, arc_step=1.0):
    """A path from the first to the last point of the run p that stays in the coil's band (vertices only): the
    straight chord when it does not dip below the run, otherwise radially to the run's mean radius, along that
    circle the same way round as the run (straight pieces of about arc_step mm), radially to the end."""
    cx, cy = centre
    X, Y = p[:, 0] - cx, p[:, 1] - cy
    r, ph = np.hypot(X, Y), np.arctan2(Y, X)
    a, b = np.array([X[0], Y[0]]), np.array([X[-1], Y[-1]])
    ab = b - a
    t = np.clip(-float(a @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    if float(np.hypot(*(a + t * ab))) >= float(r.min()) - 0.3:
        return np.array([p[0], p[-1]])
    travel = float(np.sum((np.diff(ph) + math.pi) % (2.0 * math.pi) - math.pi))
    rm = float(np.mean(r))
    n = max(2, int(math.ceil(abs(travel) * rm / arc_step)))
    tt = ph[0] + travel * np.linspace(0.0, 1.0, n + 1)
    arc = np.column_stack([cx + rm * np.cos(tt), cy + rm * np.sin(tt)])
    return np.concatenate([p[:1], arc, p[-1:]])


def _dense(c, step=0.2):
    """The polyline c with every piece cut into straight bits at most `step` mm long (the same geometry)."""
    out = [c[:1]]
    for a, b in zip(c[:-1], c[1:]):
        out.append(_line(a, b, step)[1:])
    return np.concatenate(out)


class LayerSplit:
    """One receiver coil split into closed loops per layer (see the top of this file).
      loops   {layer: [closed polylines (k, 2)]}
      chords  arrays A, B (n, 2), z_piece, z_base (n,): the remainder is
              sum_i  Bz(chord_i at z_piece_i) - Bz(chord_i at z_base_i)
      pieces3 (A3, B3): every straight piece of the coil in 3-D (z = -depth), vias included (vertical pieces)."""

    def __init__(self, path, layers, depth_of, base=None, centre=(0.0, 0.0)):
        path = np.asarray(path, dtype=float)
        layers = list(layers)
        n = len(layers)
        # start at a layer change, so that the pieces on one layer are whole runs
        start = next((i for i in range(n) if layers[i] != layers[i - 1]), 0)
        pts = np.concatenate([path[start:-1], path[:start], path[start:start + 1]])
        lay = layers[start:] + layers[:start]
        runs = []                                             # (layer, points)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and lay[j + 1] == lay[i]:
                j += 1
            runs.append((lay[i], pts[i:j + 2]))
            i = j + 1
        if base is None or base not in lay:
            length = collections.Counter()
            for l, p in runs:
                length[l] += float(np.sum(np.hypot(*np.diff(p, axis=0).T)))
            base = max(length, key=length.get)
        self.base = base
        zb = float(depth_of(base))
        self.depths = {l: float(depth_of(l)) for l in set(lay)}
        loops = collections.defaultdict(list)
        base_pts = [runs[0][1][:1]]
        ca, cb, zp, zq = [], [], [], []
        for l, p in runs:
            if l == base:
                base_pts.append(p[1:])
            else:
                # the closure (a straight chord, or radial-arc-radial for a long run), cut into short straight pieces
                # (the winding grid interpolates the radius linearly in the azimuth along every piece)
                c = _closure(p, centre) if len(p) > 2 else p
                cd = _dense(c)
                base_pts.append(cd[1:])
                if len(p) > 2:                                # a straight piece needs no lens
                    loops[l].append(np.concatenate([p, cd[::-1][1:]]))
                cc = _dense(c, 1.0)                           # (pieces of at most 1 mm for the local sums)
                ca.append(cc[:-1]); cb.append(cc[1:])
                zp.append(np.full(len(cc) - 1, self.depths[l])); zq.append(np.full(len(cc) - 1, zb))
        loops[base].insert(0, np.concatenate(base_pts))
        self.loops = dict(loops)
        cat = lambda x, k: np.concatenate(x) if x else np.zeros((0,) + k)
        self.chords = (cat(ca, (2,)), cat(cb, (2,)), cat(zp, ()), cat(zq, ()))
        # the coil in 3-D: horizontal pieces at their depths, vertical via pieces between them
        A3, B3 = [], []
        for k, (l, p) in enumerate(runs):
            z = -self.depths[l]
            A3.append(np.column_stack([p[:-1], np.full(len(p) - 1, z)]))
            B3.append(np.column_stack([p[1:], np.full(len(p) - 1, z)]))
            nl = runs[(k + 1) % len(runs)][0]
            if nl != l:                                       # via at the end of this run
                A3.append(np.array([[p[-1][0], p[-1][1], z]]))
                B3.append(np.array([[p[-1][0], p[-1][1], -self.depths[nl]]]))
        self.pieces3 = (np.concatenate(A3), np.concatenate(B3))

    def chord_field(self, px, py, height, reach=CHORD_REACH_MM):
        """The remainder (B~ units, mu0 / 4 pi per ampere) at the points (px, py) of the plane `height` above the
        top copper.  Every closure piece appears twice (two depths, opposite currents), so its field falls off
        quickly: each point sums the pieces within `reach` mm."""
        A, B, zp, zq = self.chords
        if not len(A):
            return np.zeros(np.shape(px))
        out = np.zeros(np.shape(px))
        for z in np.unique(np.concatenate([zp, zq])):
            w = (zp == z).astype(float) - (zq == z).astype(float)
            keep = w != 0
            if keep.any():
                out += local_bz(px, py, A[keep], B[keep], w[keep], height + z, reach)
        return out


# =============================================================================
# the TX coil from its copper
# =============================================================================
class TXCopper:
    """The TX's real copper with the current in every piece (per ampere at the terminals).
      pieces  A, B (n, 2), depth (n,), I (n,): horizontal pieces, current from A to B
      vias    xy (m, 2), z_top, z_bottom, I (m,): vertical pieces, current downwards
      ok      False when the copper is not one connected network between two terminals (then nothing else is set)
      why     the reason when not ok"""

    def __init__(self, stator, P, depth_of):
        self.ok, self.why = False, ""
        try:
            self._build(stator, P, depth_of)
            self.ok = True
        except ValueError as e:
            self.why = str(e)

    def _build(self, stator, P, depth_of):
        tw = float(P.TX_TRACE_WIDTH_MM)
        vr = float(P.VIA_DIAMETER_MM) / 2.0
        segs = [(np.asarray(a, float), np.asarray(b, float), l) for a, b, l in stator.tx_segments
                if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-9]
        if not segs:
            raise ValueError("no TX copper")
        layers = sorted({l for _a, _b, l in segs}, key=lambda l: depth_of(l))
        A = np.array([s[0] for s in segs]); B = np.array([s[1] for s in segs])
        L = np.array([s[2] for s in segs])
        # where a via touches a trace of a layer: at its end, or part way along (a T junction: the trace is split)
        splits = collections.defaultdict(list)                  # segment -> [t]
        contacts = []                                            # per via: [(layer, segment, t)]
        for v in np.asarray(stator.tx_vias, dtype=float).reshape(-1, 2):
            c = []
            for l in layers:
                idx = np.nonzero(L == l)[0]
                a, b = A[idx], B[idx]
                ab = b - a
                den = np.einsum("ij,ij->i", ab, ab)
                t = np.clip(np.einsum("ij,ij->i", v - a, ab) / den, 0.0, 1.0)
                d = np.hypot(*(v - (a + ab * t[:, None])).T)
                k = int(np.argmin(d))
                if d[k] <= max(vr, tw / 2.0) + 1e-6:
                    s, tt = int(idx[k]), float(t[k])
                    ln = math.sqrt(den[k])
                    if tt * ln < 1e-4:
                        tt = 0.0
                    elif (1.0 - tt) * ln < 1e-4:
                        tt = 1.0
                    else:
                        splits[s].append(tt)
                    c.append((l, s, tt))
            if len(c) >= 2:
                contacts.append((v, c))
        # nodes and edges
        node = {}

        def nid(p, l):
            k = (round(float(p[0]), 5), round(float(p[1]), 5), l)
            if k not in node:
                node[k] = len(node)
            return node[k]
        ea, eb, er, ekind = [], [], [], []                       # edge endpoints, resistance, ("seg", A, B, layer)
        for s in range(len(A)):
            ts = sorted(set([0.0, 1.0] + splits.get(s, [])))
            for t0, t1 in zip(ts[:-1], ts[1:]):
                p0, p1 = A[s] + (B[s] - A[s]) * t0, A[s] + (B[s] - A[s]) * t1
                ea.append(nid(p0, L[s])); eb.append(nid(p1, L[s]))
                er.append(float(np.hypot(*(p1 - p0)))); ekind.append(("seg", p0, p1, L[s]))
        for v, c in contacts:
            c = sorted(c, key=lambda x: depth_of(x[0]))
            pts = []
            for l, s, t in c:
                p = A[s] + (B[s] - A[s]) * t
                pts.append((nid(p, l), l, p))
            for (n0, l0, p0), (n1, l1, p1) in zip(pts[:-1], pts[1:]):
                ea.append(n0); eb.append(n1); er.append(1e-6); ekind.append(("via", v, depth_of(l0), depth_of(l1)))
        # a trace end that lies inside a via pad is connected to it (e.g. the start of a turn under the terminal via)
        deg = np.bincount(np.array(ea + eb, dtype=np.int64), minlength=len(node))
        keys = list(node.keys())
        kxy = np.array([[k[0], k[1]] for k in keys]).reshape(-1, 2)
        for v, c in contacts:
            near = np.nonzero((np.hypot(*(kxy - v).T) < vr - 1e-6) & (deg[:len(keys)] == 1))[0]
            for n0 in near:
                l = keys[n0][2]
                tgt = next((nid(A[s] + (B[s] - A[s]) * t, l) for ll, s, t in c if ll == l), None)
                if tgt is not None and tgt != n0:
                    ea.append(int(n0)); eb.append(tgt); er.append(1e-6); ekind.append(("pad",))
        nn = len(node)
        ea, eb, er = np.array(ea), np.array(eb), np.array(er)
        deg = np.bincount(np.concatenate([ea, eb]), minlength=nn)
        terms = np.nonzero(deg == 1)[0]
        if len(terms) != 2:
            raise ValueError(f"the TX copper has {len(terms)} open ends (expected the two terminals)")
        # contract chains of degree-2 nodes; solve the network on the junctions
        inc = collections.defaultdict(list)
        for e in range(len(ea)):
            inc[ea[e]].append(e); inc[eb[e]].append(e)
        junction = (deg != 2)
        jidx = {int(n): i for i, n in enumerate(np.nonzero(junction)[0])}
        chains, seen = [], np.zeros(len(ea), dtype=bool)          # (j_from, j_to, [(edge, +1/-1)], R)
        for n0 in jidx:
            for e0 in inc[n0]:
                if seen[e0]:
                    continue
                cur, e, lst, R = n0, e0, [], 0.0
                while True:
                    seen[e] = True
                    sgn = 1 if ea[e] == cur else -1
                    lst.append((e, sgn)); R += er[e]
                    cur = eb[e] if sgn == 1 else ea[e]
                    if junction[cur]:
                        break
                    e = next(x for x in inc[cur] if x != e)
                chains.append((jidx[n0], jidx[int(cur)], lst, R))
        if not seen.all():
            raise ValueError("the TX copper contains a closed ring that is not connected to the terminals")
        nj = len(jidx)
        G = np.zeros((nj, nj))
        for a, b, _l, R in chains:
            if a == b:
                continue
            g = 1.0 / max(R, 1e-9)
            G[a, a] += g; G[b, b] += g; G[a, b] -= g; G[b, a] -= g
        ta, tb = jidx[int(terms[0])], jidx[int(terms[1])]
        rhs = np.zeros(nj); rhs[ta] = 1.0
        keep = [i for i in range(nj) if i != tb]
        V = np.zeros(nj)
        V[keep] = np.linalg.solve(G[np.ix_(keep, keep)], rhs[keep])
        cur_e = np.zeros(len(ea))                                 # current along each edge, from ea to eb
        for a, b, lst, R in chains:
            i = (V[a] - V[b]) / max(R, 1e-9) if a != b else 0.0
            for e, sgn in lst:
                cur_e[e] = i * sgn
        pa, pb, pd, pi = [], [], [], []
        va, vt, vbt, vi = [], [], [], []
        for e, k in enumerate(ekind):
            if k[0] == "seg":
                pa.append(k[1]); pb.append(k[2]); pd.append(depth_of(k[3])); pi.append(cur_e[e])
            elif k[0] == "via":
                va.append(k[1]); vt.append(k[2]); vbt.append(k[3]); vi.append(cur_e[e])
        self.A, self.B = np.array(pa), np.array(pb)
        self.depth, self.I = np.array(pd), np.array(pi)
        self.via_xy = np.array(va).reshape(-1, 2)
        self.via_z = (np.array(vt), np.array(vbt))
        self.via_I = np.array(vi)
        # the sense of the current: as the original rings (counter-clockwise on average)
        cx, cy = float(stator.cx), float(stator.cy)
        p1 = np.arctan2(self.A[:, 1] - cy, self.A[:, 0] - cx)
        p2 = np.arctan2(self.B[:, 1] - cy, self.B[:, 0] - cx)
        self._dphi = (p2 - p1 + math.pi) % (2.0 * math.pi) - math.pi
        self._rmid = 0.5 * (np.hypot(self.A[:, 0] - cx, self.A[:, 1] - cy) + np.hypot(self.B[:, 0] - cx, self.B[:, 1] - cy))
        if float(np.sum(self.I * self._dphi)) < 0.0:
            self.I, self.via_I = -self.I, -self.via_I
        self.turns = float(np.sum(self.I * self._dphi)) / (2.0 * math.pi)

    def rings(self, bin_mm=0.005):
        """The azimuthally averaged TX current as rings [(radius, depth, share of the current)]: every piece adds a
        ring of its mean radius carrying I x (its angle) / (2 pi)."""
        w = self.I * self._dphi / (2.0 * math.pi)
        key = collections.defaultdict(float)
        rr = collections.defaultdict(float)
        for R, d, ww in zip(self._rmid, self.depth, w):
            k = (round(float(d), 6), int(round(R / bin_mm)))
            key[k] += ww
            rr[k] += ww * R
        out = []
        for k, ww in key.items():
            if abs(ww) > 1e-12:
                out.append((rr[k] / ww, k[0], ww))
        return sorted(out)

    def pieces3(self):
        """Every piece in 3-D (z = -depth) with its current: A3, B3, I (vias as vertical pieces)."""
        A3 = np.column_stack([self.A, -self.depth])
        B3 = np.column_stack([self.B, -self.depth])
        if len(self.via_xy):
            A3 = np.vstack([A3, np.column_stack([self.via_xy, -self.via_z[0]])])
            B3 = np.vstack([B3, np.column_stack([self.via_xy, -self.via_z[1]])])
        return A3, B3, np.concatenate([self.I, self.via_I])


def local_bz(px, py, A, B, w, h, reach, chunk=400000):
    """Like pieces_bz, but every point only sees the pieces whose midpoint is within `reach` mm (pairs found on a grid
    of cells, so it stays fast for many points and pieces)."""
    px, py = np.asarray(px, float), np.asarray(py, float)
    out = np.zeros(len(px))
    if not len(A):
        return out
    mid = 0.5 * (A + B)
    half = 0.5 * float(np.hypot(*(B - A).T).max())
    cell = reach + half
    lo = np.minimum(mid.min(axis=0), [px.min(), py.min()]) - cell
    cs = np.floor((mid - lo) / cell).astype(np.int64)
    cp = np.floor((np.column_stack([px, py]) - lo) / cell).astype(np.int64)
    K = int(max(cs.max(), cp.max())) + 3
    key = (cs[:, 0] + 1) * K + (cs[:, 1] + 1)
    order = np.argsort(key, kind="stable")
    ks = key[order]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            k = (cp[:, 0] + 1 + dx) * K + (cp[:, 1] + 1 + dy)
            l0 = np.searchsorted(ks, k, "left")
            cnt = np.searchsorted(ks, k, "right") - l0
            idx = np.nonzero(cnt)[0]
            if not len(idx):
                continue
            csum = np.cumsum(cnt[idx])
            start = 0
            while start < len(idx):
                stop = max(int(np.searchsorted(csum, (csum[start - 1] if start else 0) + chunk, "right")), start + 1)
                sel = idx[start:stop]
                c = cnt[sel]
                tot = int(c.sum())
                pi = np.repeat(sel, c)
                si = order[np.repeat(l0[sel], c) + np.arange(tot) - np.repeat(np.cumsum(c) - c, c)]
                near = np.hypot(mid[si, 0] - px[pi], mid[si, 1] - py[pi]) < reach
                pi, si = pi[near], si[near]
                v = seg_bz(A[si, 0], A[si, 1], B[si, 0], B[si, 1], px[pi], py[pi], h) * w[si]
                out += np.bincount(pi, weights=v, minlength=len(px))
                start = stop
    return out


def tx_deviation_bz(tx, centre, px, py, height, reach=8.0, arc_mm=0.5, bin_mm=0.05):
    """Normal field (B~ units) of the TX at the points (px, py) of the plane `height` above the top copper, minus the
    field of its azimuthal average (tx.rings()): what the steps, tails, gaps, go-around runs and brackets add.  Both
    are summed over the copper within `reach` mm of each point; what lies farther away is the same for both
    (the average ring current) up to a remainder that falls off like a dipole field."""
    cx, cy = centre
    out = np.zeros(len(px))
    # the real pieces, cut so that none is longer than arc_mm
    L = np.hypot(*(tx.B - tx.A).T)
    n = np.maximum(1, np.ceil(L / arc_mm).astype(np.int64))
    rep = np.repeat(np.arange(len(L)), n)
    k = np.arange(int(n.sum())) - np.repeat(np.cumsum(n) - n, n)
    t0, t1 = (k / n[rep])[:, None], ((k + 1) / n[rep])[:, None]
    A = tx.A[rep] + (tx.B[rep] - tx.A[rep]) * t0
    B = tx.A[rep] + (tx.B[rep] - tx.A[rep]) * t1
    dep, I = tx.depth[rep], tx.I[rep]
    for z in np.unique(dep):
        s = dep == z
        out += local_bz(px, py, A[s], B[s], I[s], height + z, reach)
    # minus the average rings (coarser radial bins), as arcs of about arc_mm.  Their local sum depends on the radius
    # only, so it is computed once per distinct radius of the points and spread around
    rp = np.round(np.hypot(px - cx, py - cy), 6)
    ur, inv = np.unique(rp, return_inverse=True)
    qx, qy = cx + ur, np.full(len(ur), float(cy))
    m0 = np.zeros(len(ur))
    rings = collections.defaultdict(float)
    for R, z, w in tx.rings():
        rings[(round(z, 6), round(R / bin_mm) * bin_mm)] += w
    by_z = collections.defaultdict(lambda: ([], [], []))
    for (z, R), w in rings.items():
        if abs(w) < 1e-9:
            continue
        m = max(16, int(math.ceil(2.0 * math.pi * R / arc_mm)))
        th = np.linspace(0.0, 2.0 * math.pi, m + 1)
        p = np.column_stack([cx + R * np.cos(th), cy + R * np.sin(th)])
        a, b, ww = by_z[z]
        a.append(p[:-1]); b.append(p[1:]); ww.append(np.full(m, w))
    for z, (a, b, ww) in by_z.items():
        m0 += local_bz(qx, qy, np.concatenate(a), np.concatenate(b), np.concatenate(ww), height + z, reach)
    return out - m0[inv]


# =============================================================================
# direct coupling: Neumann double line integral
# =============================================================================
def _seg_potential(Pp, A, B):
    """F[i, j] = integral over the straight piece j of dl / |P_i - r| (mm / mm), and the unit vectors of the pieces."""
    D = B - A
    L = np.linalg.norm(D, axis=1)
    U = D / np.where(L > 0, L, 1.0)[:, None]
    W = Pp[:, None, :] - A[None, :, :]
    t = np.einsum("ijk,jk->ij", W, U)
    perp = W - t[:, :, None] * U[None, :, :]
    d = np.sqrt(np.maximum(np.einsum("ijk,ijk->ij", perp, perp), 1e-14))
    return np.arcsinh((L[None, :] - t) / d) + np.arcsinh(t / d), U


def neumann(Ar, Br, At, Bt, It, chunk=160):
    """sum over receiver pieces (Ar -> Br) and TX pieces (At -> Bt, currents It) of the integral of dl.dl'/R (mm).
    Mutual inductance = mu0 / (4 pi) x this (mm -> 1e-3 m)."""
    Dr = Br - Ar
    tot = 0.0
    for s in range(0, len(Ar), chunk):
        a, d = Ar[s:s + chunk], Dr[s:s + chunk]
        for x, w in zip(GL_X, GL_W):
            Pp = a + (0.5 * (x + 1.0)) * d
            F, U = _seg_potential(Pp, At, Bt)
            Avec = (F * It[None, :]) @ U
            tot += 0.5 * w * float(np.einsum("ij,ij->", Avec, d))
    return tot
