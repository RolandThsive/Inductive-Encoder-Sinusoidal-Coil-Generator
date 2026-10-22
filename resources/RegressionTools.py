"""
RegressionTools.py  -  what the two regression test suites share: reading a written .kicad_pcb back, measuring it
independently of the generator, and comparing files with their references.

Used by "Single Generator/Regression Testing" and "Dual Generator/Regression Testing".  It knows nothing about
the generators: it only reads what they wrote.  Needs Python 3 and numpy, nothing else.

    Board          the file parsed: nets, segments, vias, polygons, the Edge.Cuts circles, the silkscreen, the header
    min_clearance  the smallest edge-to-edge distance between copper of different nets (same layer; vias on every
                   layer), measured on the written coordinates with a cell grid, not with the generator's own code
    connectivity   per net: connected components, free ends, free ends that do not sit on a via of that net
    copper_extent  per layer: the innermost and outermost copper radius from the board centre
    compare_text   two texts compared token by token: numbers within a tolerance, everything else exactly
    normalise_record  Parameters.txt without the lines that change with every run (time, folder, command, the
                   verbatim copies of the parameter files)
    read_reference / write_reference   references stored gzip-compressed (<name>.gz) or plain
"""

import gzip
import math
import os
import re

import numpy as np

# ---------------------------------------------------------------------------------------------- the file
_NUM = r"(-?\d+(?:\.\d+)?)"
SEG_RE = re.compile(r'^\s*\(segment \(start ' + _NUM + " " + _NUM + r'\) \(end ' + _NUM + " " + _NUM +
                    r'\) \(width ' + _NUM + r'\) \(layer "([^"]+)"\) \(net (\d+)\)\)\s*$')
VIA_RE = re.compile(r'^\s*\(via \(at ' + _NUM + " " + _NUM + r'\) \(size ' + _NUM + r'\) \(drill ' + _NUM +
                    r'\) \(layers "([^"]+)" "([^"]+)"\) \(net (\d+)\)\)\s*$')
NET_RE = re.compile(r'^\s*\(net (\d+) "([^"]*)"\)\s*$')
CIRCLE_RE = re.compile(r'^\s*\(gr_circle \(center ' + _NUM + " " + _NUM + r'\) \(end ' + _NUM + " " + _NUM +
                       r'\) (?:\(stroke \(width ' + _NUM + r'\) \(type (\w+)\) \(color (\d+) (\d+) (\d+) 1\)\) )?'
                       r'(?:\(fill (\w+)\) )?\(layer "([^"]+)"\)(?: \(width ' + _NUM + r'\))?(?: \(fill (\w+)\))?\)\s*$')
LINE_RE = re.compile(r'^\s*\(gr_line \(start ' + _NUM + " " + _NUM + r'\) \(end ' + _NUM + " " + _NUM +
                     r'\) \(stroke \(width ' + _NUM + r'\) \(type (\w+)\) \(color (\d+) (\d+) (\d+) 1\)\) '
                     r'\(layer "([^"]+)"\)\)\s*$')
POLY_RE = re.compile(r'^\s*\(gr_poly \(pts ((?:\(xy ' + _NUM + " " + _NUM + r'\) ?)+)\) \(layer "([^"]+)"\) '
                     r'\(width ' + _NUM + r'\) \(fill (\w+)\)\)\s*$')
XY_RE = re.compile(r'\(xy ' + _NUM + " " + _NUM + r'\)')
LAYER_RE = re.compile(r'^\s*\((\d+) "([^"]+)" (signal|user)(?: "([^"]+)")?\)\s*$')
HEADER_RE = re.compile(r'^\(kicad_pcb \(version (\d+)\) \(generator (\w+)\)\s*$')
THICK_RE = re.compile(r'^\s*\(general \(thickness ' + _NUM + r'\)\)\s*$')
PAPER_RE = re.compile(r'^\s*\(paper "([^"]+)" ' + _NUM + " " + _NUM + r'\)\s*$')
TITLE_RE = re.compile(r'^\s*\(title_block \(title "([^"]*)"\)((?: \(comment \d+ "[^"]*"\))*)\)\s*$')
COMMENT_RE = re.compile(r'\(comment (\d+) "([^"]*)"\)')
COPPER_LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


class Board:
    """A written .kicad_pcb, read back line by line.  Every line of the body must be one of the elements the
    generators write (segment, via, gr_circle, gr_line, gr_poly); anything else is counted in `unknown` so that a
    test can insist the parser understood the whole file."""

    def __init__(self, text):
        self.text = text
        self.version = self.generator = None
        self.thickness = None
        self.page = None
        self.title, self.comments = None, {}
        self.layers = []                     # (number, name, kind) from the layers block
        self.nets = {}                       # id -> name
        seg, seg_layer, seg_net = [], [], []
        via, via_net, via_layers = [], [], []
        self.edges = []                      # (cx, cy, r) on Edge.Cuts
        self.circles = []                    # every other gr_circle: dict
        self.lines = []                      # gr_line: dict
        self.polys = []                      # (layer, (n, 2) array, fill)
        self.unknown = []
        in_layers = False
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            m = SEG_RE.match(line)
            if m:
                seg.append([float(v) for v in m.group(1, 2, 3, 4, 5)])
                seg_layer.append(m.group(6))
                seg_net.append(int(m.group(7)))
                continue
            m = VIA_RE.match(line)
            if m:
                via.append([float(v) for v in m.group(1, 2, 3, 4)])
                via_layers.append((m.group(5), m.group(6)))
                via_net.append(int(m.group(7)))
                continue
            m = NET_RE.match(line)
            if m:
                self.nets[int(m.group(1))] = m.group(2)
                continue
            m = LINE_RE.match(line)
            if m:
                self.lines.append(dict(start=(float(m.group(1)), float(m.group(2))),
                                       end=(float(m.group(3)), float(m.group(4))), width=float(m.group(5)),
                                       type=m.group(6), color=tuple(int(c) for c in m.group(7, 8, 9)),
                                       layer=m.group(10)))
                continue
            m = CIRCLE_RE.match(line)
            if m:
                cx, cy, ex, ey = (float(v) for v in m.group(1, 2, 3, 4))
                layer = m.group(11)
                r = math.hypot(ex - cx, ey - cy)
                if layer == "Edge.Cuts":
                    self.edges.append((cx, cy, r))
                else:
                    width = m.group(5) if m.group(5) is not None else m.group(12)
                    self.circles.append(dict(centre=(cx, cy), radius=r, width=float(width) if width else None,
                                             type=m.group(6), color=tuple(int(c) for c in m.group(7, 8, 9))
                                             if m.group(7) else None, fill=m.group(10) or m.group(13), layer=layer))
                continue
            m = POLY_RE.match(line)
            if m:
                pts = np.array([[float(x), float(y)] for x, y in XY_RE.findall(m.group(1))])
                self.polys.append((m.group(4), pts, m.group(6)))
                continue
            if line.strip() == "(layers":
                in_layers = True
                continue
            if in_layers:
                m = LAYER_RE.match(line)
                if m:
                    self.layers.append((int(m.group(1)), m.group(2), m.group(3)))
                    continue
                if line.strip() == ")":
                    in_layers = False
                    continue
            m = HEADER_RE.match(line)
            if m:
                self.version, self.generator = int(m.group(1)), m.group(2)
                continue
            m = THICK_RE.match(line)
            if m:
                self.thickness = float(m.group(1))
                continue
            m = PAPER_RE.match(line)
            if m:
                self.page = (m.group(1), float(m.group(2)), float(m.group(3)))
                continue
            m = TITLE_RE.match(line)
            if m:
                self.title = m.group(1)
                self.comments = {int(i): c for i, c in COMMENT_RE.findall(m.group(2))}
                continue
            if line.strip() in (")", "(setup (pad_to_mask_clearance 0))"):
                continue
            self.unknown.append(line)
        self.seg = np.array(seg, dtype=float).reshape(-1, 5)
        self.seg_layer = np.array(seg_layer, dtype=object)
        self.seg_net = np.array(seg_net, dtype=int)
        self.via = np.array(via, dtype=float).reshape(-1, 4)
        self.via_net = np.array(via_net, dtype=int)
        self.via_layers = via_layers
        self.net_id = {name: i for i, name in self.nets.items()}
        self.copper_layers = [name for _n, name, kind in self.layers if kind == "signal"]

    @classmethod
    def from_file(cls, path):
        with open(path, encoding="utf-8") as fh:
            return cls(fh.read())

    # ------------------------------------------------------------------ handy views
    @property
    def centre(self):
        """The common centre of the Edge.Cuts circles (the board centre)."""
        if not self.edges:
            raise ValueError("the file has no Edge.Cuts circle")
        return float(np.mean([e[0] for e in self.edges])), float(np.mean([e[1] for e in self.edges]))

    @property
    def outer_radius(self):
        return max(e[2] for e in self.edges)

    @property
    def inner_radius(self):
        return min(e[2] for e in self.edges)

    def segments_of(self, net_id=None, layer=None):
        m = np.ones(len(self.seg), dtype=bool)
        if net_id is not None:
            m &= self.seg_net == net_id
        if layer is not None:
            m &= self.seg_layer == layer
        return m

    def vias_of(self, net_id):
        return self.via_net == net_id

    def nets_used(self):
        """Net ids that carry copper (segments or vias)."""
        return set(int(n) for n in self.seg_net) | set(int(n) for n in self.via_net)

    def length_of(self, net_id, layer=None):
        m = self.segments_of(net_id, layer)
        s = self.seg[m]
        return float(np.sum(np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]))) if len(s) else 0.0

    def silk(self, layer):
        return [l for l in self.lines if l["layer"] == layer] + [c for c in self.circles if c["layer"] == layer]


def brackets_balanced(text):
    """True when every '(' of the file has its ')' and the file ends with the closing one (quoted text has no
    brackets: the writer removes quotes and never writes brackets inside them)."""
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and text.rstrip().endswith(")")


# ---------------------------------------------------------------------------------------------- geometry
def point_segment_distance(P, A, B):
    """Distance from each point P (k, 2) to its segment A-B (k, 2 each)."""
    P, A, B = (np.asarray(v, dtype=float) for v in (P, A, B))
    d = B - A
    l2 = np.sum(d * d, axis=1)
    t = np.where(l2 > 0, np.sum((P - A) * d, axis=1) / np.where(l2 > 0, l2, 1.0), 0.0)
    t = np.clip(t, 0.0, 1.0)
    foot = A + t[:, None] * d
    return np.hypot(*(P - foot).T)


def segment_segment_distance(A1, A2, B1, B2):
    """Centre-line distance between segments A1-A2 and B1-B2 (k, 2 each): 0 where they cross."""
    A1, A2, B1, B2 = (np.asarray(v, dtype=float) for v in (A1, A2, B1, B2))

    def cross(u, v):
        return u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]

    d1 = cross(B2 - B1, A1 - B1)
    d2 = cross(B2 - B1, A2 - B1)
    d3 = cross(A2 - A1, B1 - A1)
    d4 = cross(A2 - A1, B2 - A1)
    crossing = (d1 * d2 < 0) & (d3 * d4 < 0)
    dist = np.min(np.stack([point_segment_distance(A1, B1, B2), point_segment_distance(A2, B1, B2),
                            point_segment_distance(B1, A1, A2), point_segment_distance(B2, A1, A2)]), axis=0)
    return np.where(crossing, 0.0, dist)


def _cells(xmin, ymin, xmax, ymax, cell):
    return (np.floor(xmin / cell).astype(int), np.floor(ymin / cell).astype(int),
            np.floor(xmax / cell).astype(int), np.floor(ymax / cell).astype(int))


def _candidate_pairs(xmin, ymin, xmax, ymax, cell):
    """Index pairs (i < j) of boxes that share a grid cell."""
    cx0, cy0, cx1, cy1 = _cells(xmin, ymin, xmax, ymax, cell)
    buckets = {}
    for i in range(len(xmin)):
        for cx in range(cx0[i], cx1[i] + 1):
            for cy in range(cy0[i], cy1[i] + 1):
                buckets.setdefault((cx, cy), []).append(i)
    pairs = set()
    for members in buckets.values():
        if len(members) < 2:
            continue
        members.sort()
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                pairs.add((members[a], members[b]))
    if not pairs:
        return np.zeros((0, 2), dtype=int)
    return np.array(sorted(pairs), dtype=int)


def min_clearance(board, max_interest=1.0, cell=1.0):
    """The smallest edge-to-edge distance between copper of DIFFERENT nets: segments on the same layer, vias
    against everything (a via goes through every layer).  Only distances below `max_interest` are measured exactly
    (the cell grid finds every pair closer than that); the result is min(max_interest, true minimum).
    Returns (distance, description of the closest pair)."""
    best, where = max_interest, "no two nets come closer than %g mm" % max_interest
    seg, nets = board.seg, board.seg_net
    half = seg[:, 4] / 2.0
    for layer in sorted(set(board.seg_layer.tolist())):
        idx = np.nonzero(board.seg_layer == layer)[0]
        if len(idx) < 2:
            continue
        s, h = seg[idx], half[idx]
        grow = h + max_interest / 2.0
        xmin = np.minimum(s[:, 0], s[:, 2]) - grow
        xmax = np.maximum(s[:, 0], s[:, 2]) + grow
        ymin = np.minimum(s[:, 1], s[:, 3]) - grow
        ymax = np.maximum(s[:, 1], s[:, 3]) + grow
        pairs = _candidate_pairs(xmin, ymin, xmax, ymax, cell)
        if not len(pairs):
            continue
        a, b = pairs[:, 0], pairs[:, 1]
        other = nets[idx[a]] != nets[idx[b]]
        a, b = a[other], b[other]
        if not len(a):
            continue
        d = segment_segment_distance(s[a, 0:2], s[a, 2:4], s[b, 0:2], s[b, 2:4]) - h[a] - h[b]
        k = int(np.argmin(d))
        if d[k] < best:
            best = float(d[k])
            where = (f"segments of nets {board.nets.get(int(nets[idx[a[k]]]))!r} and "
                     f"{board.nets.get(int(nets[idx[b[k]]]))!r} on {layer} at "
                     f"({s[a[k], 0]:.3f}, {s[a[k], 1]:.3f}) / ({s[b[k], 0]:.3f}, {s[b[k], 1]:.3f})")
    via = board.via
    if len(via):
        vr = via[:, 2] / 2.0
        for i in range(len(via)):
            other = nets != board.via_net[i]
            if other.any():
                s = seg[other]
                P = np.repeat(via[i:i + 1, 0:2], len(s), axis=0)
                d = point_segment_distance(P, s[:, 0:2], s[:, 2:4]) - half[other] - vr[i]
                k = int(np.argmin(d))
                if d[k] < best:
                    best = float(d[k])
                    where = (f"via of net {board.nets.get(int(board.via_net[i]))!r} at ({via[i, 0]:.3f}, {via[i, 1]:.3f}) "
                             f"and a segment of net {board.nets.get(int(nets[other][k]))!r}")
            for j in range(i + 1, len(via)):
                if board.via_net[i] != board.via_net[j]:
                    d = math.hypot(via[i, 0] - via[j, 0], via[i, 1] - via[j, 1]) - vr[i] - vr[j]
                    if d < best:
                        best, where = float(d), f"vias at ({via[i, 0]:.3f}, {via[i, 1]:.3f}) and ({via[j, 0]:.3f}, {via[j, 1]:.3f})"
    return best, where


def copper_extent(board, centre=None):
    """{layer: (innermost radius, outermost radius)} of the copper (segments with their width; vias on every
    copper layer) from the board centre."""
    cx, cy = centre if centre is not None else board.centre
    out = {}
    seg = board.seg
    if len(seg):
        C = np.repeat(np.array([[cx, cy]]), len(seg), axis=0)
        near = point_segment_distance(C, seg[:, 0:2], seg[:, 2:4]) - seg[:, 4] / 2.0
        far = np.maximum(np.hypot(seg[:, 0] - cx, seg[:, 1] - cy), np.hypot(seg[:, 2] - cx, seg[:, 3] - cy)) + seg[:, 4] / 2.0
        for layer in sorted(set(board.seg_layer.tolist())):
            m = board.seg_layer == layer
            out[layer] = (float(near[m].min()), float(far[m].max()))
    if len(board.via):
        r = np.hypot(board.via[:, 0] - cx, board.via[:, 1] - cy)
        lo, hi = float((r - board.via[:, 2] / 2.0).min()), float((r + board.via[:, 2] / 2.0).max())
        for layer in board.copper_layers or list(out):
            a, b = out.get(layer, (lo, hi))
            out[layer] = (min(a, lo), max(b, hi))
    return out


def polygon_area(pts):
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def polygon_radii(pts, centre):
    r = np.hypot(pts[:, 0] - centre[0], pts[:, 1] - centre[1])
    return float(r.min()), float(r.max())


def polygon_angular_span(pts, centre):
    """Angular width (deg) of a sector polygon seen from the centre (its points span less than 360 deg)."""
    a = np.degrees(np.arctan2(pts[:, 1] - centre[1], pts[:, 0] - centre[0]))
    a = np.sort(np.mod(a, 360.0))
    gaps = np.diff(np.concatenate([a, [a[0] + 360.0]]))
    return float(360.0 - gaps.max())


# ---------------------------------------------------------------------------------------------- connectivity
class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, a):
        p = self.parent.setdefault(a, a)
        while p != a:
            self.parent[a] = self.parent[p]
            a, p = p, self.parent[p]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def connectivity(board, net_id, tol=1e-3):
    """How the copper of one net hangs together.  Segment ends meet where the written coordinates are equal (the
    writer prints the same float the same way); a via of the net joins, on every layer, each segment of the net
    whose centre line passes within the via's radius (+ tol) of it, so a stitching via in the middle of a trace
    counts as well as one at its end.  Returns dict(components, free_ends=[(x, y, layer)], loose_ends=[those
    not on a via of the net], vias=number of vias of the net, segments=number of segments)."""
    m = board.segments_of(net_id)
    seg, layers = board.seg[m], board.seg_layer[m]
    vias = board.via[board.vias_of(net_id)]
    uf = _UnionFind()
    degree = {}
    nodes_a = []
    for (x1, y1, x2, y2, _w), layer in zip(seg, layers):
        a, b = (x1, y1, layer), (x2, y2, layer)
        uf.union(a, b)
        nodes_a.append(a)
        degree[a] = degree.get(a, 0) + 1
        degree[b] = degree.get(b, 0) + 1
    on_via = set()
    if len(vias) and len(seg):
        for v in vias:
            P = np.repeat(np.array([[v[0], v[1]]]), len(seg), axis=0)
            d = point_segment_distance(P, seg[:, 0:2], seg[:, 2:4])
            touching = np.nonzero(d <= v[2] / 2.0 + tol)[0]
            key = ("via", float(v[0]), float(v[1]))
            for i in touching:
                uf.union(nodes_a[i], key)
            for i in touching:
                for n in ((seg[i, 0], seg[i, 1], layers[i]), (seg[i, 2], seg[i, 3], layers[i])):
                    if math.hypot(n[0] - v[0], n[1] - v[1]) <= v[2] / 2.0 + tol:
                        on_via.add(n)
    roots = set(uf.find(n) for n in degree)
    free = [n for n, d in degree.items() if d == 1]
    loose = [n for n in free if n not in on_via]
    return dict(components=len(roots), free_ends=free, loose_ends=loose, vias=int(len(vias)), segments=int(len(seg)))


# ---------------------------------------------------------------------------------------------- comparing
_TOKEN = re.compile(r"-?\d+\.\d+(?:[eE][-+]?\d+)?|-?\d+(?:[eE][-+]?\d+)?|\S+")


def compare_text(expected, actual, tol=1e-5, limit=12):
    """Line by line, token by token: numbers must agree within tol (absolute), other tokens exactly.  Returns a
    list of difference texts (at most `limit`), empty when the texts agree."""
    a_lines = expected.replace("\r\n", "\n").split("\n")
    b_lines = actual.replace("\r\n", "\n").split("\n")
    out = []
    n = max(len(a_lines), len(b_lines))
    for i in range(n):
        if len(out) >= limit:
            out.append(f"... (stopped after {limit} differences)")
            break
        a = a_lines[i] if i < len(a_lines) else None
        b = b_lines[i] if i < len(b_lines) else None
        if a is None or b is None:
            out.append(f"line {i + 1}: {'missing in the result' if b is None else 'extra in the result'}: "
                       f"{(a if b is None else b)!r}")
            continue
        if a == b:
            continue
        ta, tb = _TOKEN.findall(a), _TOKEN.findall(b)
        same = len(ta) == len(tb)
        if same:
            for x, y in zip(ta, tb):
                if x == y:
                    continue
                try:
                    if abs(float(x) - float(y)) <= tol:
                        continue
                except ValueError:
                    pass
                same = False
                break
        if not same:
            out.append(f"line {i + 1}:\n      reference: {a!r}\n      result:    {b!r}")
    return out


RECORD_DROP = ("generated ", "folder ", "command ")


def normalise_record(text, project_dir=None):
    """Parameters.txt as something that must not change between runs: without the time stamp, the folder and the
    command, without the verbatim copies of the parameter files (a comment edited there is not a regression; only
    their names stay), and with the project folder replaced by <project> where it appears.  A section title is a
    line of capitals followed by a line of dashes."""
    lines = text.replace("\r\n", "\n").split("\n")
    out, skipping = [], False
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        title = bool(line) and line == line.upper() and nxt and set(nxt) <= {"-", "="} and len(nxt) >= len(line) - 2
        if line.startswith("##########"):
            skipping = True
            out.append(line.split(" ")[1] if " " in line else line)
            continue
        if skipping:
            if title:
                skipping = False
            else:
                continue
        if any(line.startswith(d) for d in RECORD_DROP):
            continue
        if project_dir:
            for form in (project_dir, project_dir.replace("\\", "/"), project_dir.replace("\\", "\\\\")):
                line = line.replace(form, "<project>")
        out.append(line)
    return "\n".join(out).rstrip("\n") + "\n"


def read_reference(path):
    """The reference text, from <path> or <path>.gz (whichever exists); None when there is none."""
    if os.path.isfile(path + ".gz"):
        with gzip.open(path + ".gz", "rt", encoding="utf-8", newline="") as fh:
            return fh.read().replace("\r\n", "\n")
    if os.path.isfile(path):
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read().replace("\r\n", "\n")
    return None


def write_reference(path, text, compress=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if compress:
        if os.path.isfile(path):
            os.remove(path)
        with gzip.open(path + ".gz", "wt", encoding="utf-8", newline="\n", compresslevel=9) as fh:
            fh.write(text)
    else:
        if os.path.isfile(path + ".gz"):
            os.remove(path + ".gz")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
