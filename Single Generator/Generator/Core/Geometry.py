"""
Geometry.py  -  small numeric helpers shared by the generator modules: the axial field of a circular current
loop (the electrical estimate), point / segment distances (clearance checks) and the
chord tolerance of the polylines.  Nothing to edit here.
"""

import math

import numpy as np


def ellipk_ellipe(m):
    """Complete elliptic integrals K(m), E(m) (parameter m = k^2) by AGM."""
    if m <= 0.0:
        return math.pi / 2.0, math.pi / 2.0
    a, b, c = 1.0, math.sqrt(1.0 - m), math.sqrt(m)
    total, pw = 0.5 * c * c, 0.5
    while abs(c) > 1e-16:
        a, b, c = 0.5 * (a + b), math.sqrt(a * b), 0.5 * (a - b)
        pw *= 2.0
        total += pw * c * c
    k = math.pi / (2.0 * a)
    return k, k * (1.0 - total)


def loop_bz(radius, r, z):
    """Axial field (arbitrary units, per ampere) of a circular current loop."""
    m = 4.0 * radius * r / ((radius + r) ** 2 + z * z)
    k, e = ellipk_ellipe(min(m, 1.0 - 1e-12))
    den = (radius - r) ** 2 + z * z
    return (k + (radius * radius - r * r - z * z) / den * e) / math.sqrt((radius + r) ** 2 + z * z)


def point_segments_distance(p, a, b):
    """Distance from point p to each segment a[i]-b[i]  (arrays Nx2)."""
    ab = b - a
    ap = p - a
    den = np.einsum("ij,ij->i", ab, ab)
    t = np.where(den > 0, np.einsum("ij,ij->i", ap, ab) / np.where(den > 0, den, 1.0), 0.0)
    t = np.clip(t, 0.0, 1.0)
    proj = a + ab * t[:, None]
    return np.hypot(*(p - proj).T)


def points_segments_min_distance(pts, a, b, chunk=2048):
    """For every point of pts (n, 2): the distance to the nearest of the segments a[i] -> b[i] (m, 2)."""
    pts = np.asarray(pts, dtype=float).reshape(-1, 2)
    if len(a) == 0 or len(pts) == 0:
        return np.full(len(pts), np.inf)
    d = b - a
    dd = np.maximum(np.einsum("ij,ij->i", d, d), 1e-30)
    out = np.empty(len(pts))
    for s0 in range(0, len(pts), max(1, chunk * 64 // max(len(a), 1))):
        p = pts[s0:s0 + max(1, chunk * 64 // max(len(a), 1))]
        w = p[:, None, :] - a[None, :, :]
        t = np.clip(np.einsum("ijk,jk->ij", w, d) / dd[None, :], 0.0, 1.0)
        c = a[None, :, :] + t[:, :, None] * d[None, :, :]
        out[s0:s0 + len(p)] = np.sqrt(((p[:, None, :] - c) ** 2).sum(axis=2)).min(axis=1)
    return out


def near_points_segments_min_distance(pts, a, b, cutoff, chunk=200000):
    """Smallest distance from the points to the segments a[i]-b[i], exact when it is below `cutoff` (otherwise
    some value >= cutoff).  Only nearby pairs are measured (a grid of cells), so it stays fast for long, finely
    divided polylines."""
    pts, a, b = (np.asarray(x, dtype=float).reshape(-1, 2) for x in (pts, a, b))
    if not len(pts) or not len(a):
        return float("inf")
    h = float(cutoff) + float(np.hypot(*(b - a).T).max()) / 2.0 + 1e-9
    mid = 0.5 * (a + b)
    lo = np.minimum(mid.min(axis=0), pts.min(axis=0))
    cs = np.floor((mid - lo) / h).astype(np.int64)
    cp = np.floor((pts - lo) / h).astype(np.int64)
    K = int(max(cs.max(), cp.max())) + 3
    key = (cs[:, 0] + 1) * K + (cs[:, 1] + 1)
    order = np.argsort(key, kind="stable")
    ks = key[order]
    best = float("inf")
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            k = (cp[:, 0] + 1 + dx) * K + (cp[:, 1] + 1 + dy)
            l0 = np.searchsorted(ks, k, "left")
            cnt = np.searchsorted(ks, k, "right") - l0
            idx = np.nonzero(cnt)[0]
            if not len(idx):
                continue
            # pairs, in slices of about `chunk`
            csum = np.cumsum(cnt[idx])
            start = 0
            while start < len(idx):
                stop = int(np.searchsorted(csum, (csum[start - 1] if start else 0) + chunk, "right"))
                stop = max(stop, start + 1)
                sel = idx[start:stop]
                c = cnt[sel]
                tot = int(c.sum())
                pi = np.repeat(sel, c)
                off = np.arange(tot) - np.repeat(np.cumsum(c) - c, c)
                si = order[np.repeat(l0[sel], c) + off]
                A, B, Pp = a[si], b[si], pts[pi]
                ab = B - A
                den = np.einsum("ij,ij->i", ab, ab)
                t = np.where(den > 0, np.einsum("ij,ij->i", Pp - A, ab) / np.where(den > 0, den, 1.0), 0.0)
                t = np.clip(t, 0.0, 1.0)
                d = np.hypot(*(Pp - (A + ab * t[:, None])).T)
                best = min(best, float(d.min()))
                start = stop
    return best


def segment_distance(p1, p2, q1, q2):
    """Shortest distance between the segments p1-p2 and q1-q2: 0 when they cross or touch."""
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if side(q1, q2, p1) * side(q1, q2, p2) < 0 and side(p1, p2, q1) * side(p1, p2, q2) < 0:
        return 0.0                                         # they cross
    p1, p2, q1, q2 = (np.asarray(v, dtype=float) for v in (p1, p2, q1, q2))
    return float(min(point_segments_distance(p1, q1[None], q2[None])[0],
                     point_segments_distance(p2, q1[None], q2[None])[0],
                     point_segments_distance(q1, p1[None], p2[None])[0],
                     point_segments_distance(q2, p1[None], p2[None])[0]))


def chord_tolerance(P, which):
    """RX_ / TX_ / ROTOR_CHORD_TOLERANCE_MM (mm, which = "RX" | "TX" | "ROTOR"); 0.001 (1 micron) when the line is
    missing."""
    v = getattr(P, f"{which}_CHORD_TOLERANCE_MM", None)
    return 0.001 if v is None else float(v)
