"""
LeadCutting_SilkscreenSuggestion.py  -  the last step of a generation: a silkscreen suggestion for cutting the
leads, drawn into the finished Stator.kicad_pcb (RunCoilGenerator.py calls it after the stator is written).

Every RX coil the generator makes is one closed loop, and the two ends of the TX coil lie on top of each other
at the end of its tail (one on each of its two layers).  To reach the IC, the user breaks each RX loop once and
sets a via at each side of the cut, and extends each TX end to a via of its own.  This step finds, on the written board, a spot
for each of those vias that has room on every layer (through vias) and inside the board edges, and draws:

    RX coil   a dashed box around the break, a filled dot at each via site, the lead names (SIN_1, SIN_2, ...)
    TX coil   a filled dot at each via site beside the stacked end, a dashed line from the end to each site, the
              lead names (TX_1 TOP, TX_2 BOT: each end with its layer)
    (option)  a dot on every via the generator placed

The names are drawn as strokes of the repository's own font (resources/SilkscreenFont.py at the root of the
repository, loaded by its path), not as KiCad text, and each name is placed where it covers no other mark, no
other name and no via, inside the board edges.  The marks go on F.SilkS and/or B.SilkS (bottom text mirrored).
The settings are in Parameters/SilkScreenSuggestion_Parameters.py.  No copper is changed and nothing else in
the generator is touched: the step reads the written file, appends the drawings before the closing bracket and writes it back.  It
never fails a generation: anything it cannot do is printed as a warning and the file stays as it was.

    result = add_to_file(path, P)       path: the written Stator.kicad_pcb;  P: Parameters
    append_record(record_path, result)  adds the result to Parameters.txt
"""

import importlib.util
import math
import os
import re

import numpy as np

from Generator.Core.Conflict import Colour
from Generator.Stator.StatorAssembly import TERMINAL_DEG

PARAMETER_FILE = "SilkScreenSuggestion_Parameters.py"

# the stroke font: resources/SilkscreenFont.py at the root of the repository (this file is four folders below it)
FONT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                         "resources", "SilkscreenFont.py")


def load_font():
    """The font module loaded by its path, or None (with the reason) if it is missing or broken."""
    if not os.path.isfile(FONT_FILE):
        return None, f"the font {FONT_FILE} was not found: the lead names are not drawn"
    try:
        spec = importlib.util.spec_from_file_location("SilkscreenFont", FONT_FILE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.layout("A", 0.0, 0.0, 1.0)
        return module, None
    except Exception as e:
        return None, f"the font {FONT_FILE} cannot be loaded ({type(e).__name__}: {e}): the lead names are not drawn"

DEFAULTS = dict(
    SILKSCREEN_SUGGESTION=True, SILKSCREEN_SIDES="both", SILKSCREEN_COLOR="#FFFFFF", SILKSCREEN_LABELS=True,
    SILKSCREEN_DOT_ON_ALL_VIAS=False, SILKSCREEN_LINE_WIDTH_MM=0.12, SILKSCREEN_TEXT_SIZE_MM=0.5,
    SILKSCREEN_TEXT_STROKE_MM=0.1,
    SILKSCREEN_DOT_RADIUS_MM=0.16, SILKSCREEN_BOX_MARGIN_MM=0.5, SILKSCREEN_BREAK_VIA_GAP_MM=1.2,
    SILKSCREEN_SEARCH_SPAN_DEG=30.0, SILKSCREEN_BREAK_SEPARATION_MM=4.0, SILKSCREEN_BREAK_LAYERS=["F.Cu", "B.Cu"],
    SILKSCREEN_VIA_EDGE_CLEARANCE_MM=0.25, SILKSCREEN_TX_SITE_REACH_MM=2.0)

LAYER_WORD = {"F.Cu": "Top", "In1.Cu": "In1", "In2.Cu": "In2", "B.Cu": "Bottom"}
LABEL_WORD = {"F.Cu": "TOP", "In1.Cu": "IN1", "In2.Cu": "IN2", "B.Cu": "BOT"}   # on the silkscreen (capitals)

_SEG = re.compile(r'\(segment \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\) \(width ([\d.]+)\) '
                  r'\(layer "([^"]+)"\) \(net (\d+)\)\)')
_VIA = re.compile(r'\(via (?:blind )?\(at ([-\d.]+) ([-\d.]+)\) \(size ([\d.]+)\) \(drill ([\d.]+)\) \(layers "[^"]+" "[^"]+"\) '
                  r'\(net (\d+)\)\)')
_NET = re.compile(r'\(net (\d+) "([^"]*)"\)')
_EDGE = re.compile(r'\(gr_circle \(center ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\) \(layer "Edge.Cuts"\)')


# ====================================================================== settings
class Settings:
    """The values of SilkScreenSuggestion_Parameters.py, checked; a wrong value falls back to its default with a
    warning (the step never stops a generation)."""

    def __init__(self):
        self.warnings = []
        try:
            import SilkScreenSuggestion_Parameters as M
        except ImportError:
            M = None
            self.warnings.append(f"{PARAMETER_FILE} was not found in the Parameters folder: the defaults are used")
        except Exception as e:                                             # a syntax error in the file
            M = None
            self.warnings.append(f"{PARAMETER_FILE} cannot be loaded ({type(e).__name__}: {e}): the defaults are used")
        for name, default in DEFAULTS.items():
            value = getattr(M, name, default) if M is not None else default
            ok, value = self._check(name, value, default)
            setattr(self, name, value)
        if M is not None:
            for name in sorted(n for n in dir(M) if n.isupper() and not n.startswith("_") and n not in DEFAULTS):
                self.warnings.append(f"{name} in {PARAMETER_FILE} is not a setting of the silkscreen suggestion and is ignored")
        self.rgb = self._rgb(self.SILKSCREEN_COLOR)

    def _check(self, name, value, default):
        def bad(what):
            self.warnings.append(f"{name} = {value!r} in {PARAMETER_FILE}: {what}; using {default!r}")
            return False, default
        if isinstance(default, bool):
            if not isinstance(value, bool):
                return bad("must be True or False")
        elif name == "SILKSCREEN_SIDES":
            if not isinstance(value, str) or value.strip().lower() not in ("both", "top", "bottom"):
                return bad('must be "both", "top" or "bottom"')
            value = value.strip().lower()
        elif name == "SILKSCREEN_COLOR":
            if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value.strip()):
                return bad('must be a hex colour "#RRGGBB"')
            value = value.strip().upper()
        elif name == "SILKSCREEN_BREAK_LAYERS":
            if not isinstance(value, (list, tuple)) or not value \
                    or any(v not in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu") for v in value):
                return bad('must be a list of copper layers, e.g. ["F.Cu", "B.Cu"]')
            value = list(value)
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                return bad("must be a number above 0")
            value = float(value)
        return True, value

    @staticmethod
    def _rgb(hexcolour):
        h = hexcolour.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ====================================================================== the board as written
class Board:
    """The copper of the written stator file: segments (n, 5: x1 y1 x2 y2 width) with their layer and net, the vias,
    the net names and the two Edge.Cuts circles."""

    def __init__(self, text, P):
        B = P
        self.cx, self.cy = float(B.CENTER_X_MM), float(B.CENTER_Y_MM)
        self.net_name = {int(n): name for n, name in _NET.findall(text)}
        self.net_id = {name: n for n, name in self.net_name.items()}
        rows = _SEG.findall(text)
        self.seg = np.array([[float(a), float(b), float(c), float(d), float(w)] for a, b, c, d, w, l, n in rows]).reshape(-1, 5)
        self.layer = np.array([l for *_, l, n in rows])
        self.net = np.array([int(n) for *_, n in rows])
        via_rows = _VIA.findall(text)
        self.vias = np.array([[float(x), float(y), float(s)] for x, y, s, _d, _n in via_rows]).reshape(-1, 3)
        self.via_net = np.array([int(n) for *_, n in via_rows])
        radii = sorted(math.hypot(float(ex) - float(x), float(ey) - float(y)) for x, y, ex, ey in _EDGE.findall(text))
        self.bore = radii[0] if len(radii) >= 2 else None
        self.outline = radii[-1] if radii else None
        self.via_d = float(B.VIA_DIAMETER_MM)
        self.clear = float(B.MIN_CLEARANCE_MM)

    def dist_to_segments(self, p, mask=None):
        """distance from p to the centre line of every segment (or of those in mask)"""
        S = self.seg if mask is None else self.seg[mask]
        if len(S) == 0:
            return np.full(0, np.inf)
        a, b = S[:, 0:2], S[:, 2:4]
        ab, ap = b - a, p - a
        L2 = (ab * ab).sum(1)
        L2[L2 == 0] = 1e-12
        u = np.clip((ap * ab).sum(1) / L2, 0.0, 1.0)
        q = a + u[:, None] * ab
        return np.hypot(*(p - q).T)

    def via_room(self, p, exclude=None, edge_clear=0.0):
        """the copper clearance a via of VIA_DIAMETER_MM at p would have: the smallest gap to every segment not
        excluded (edge to edge), to every via, and to the bore and the outline less edge_clear.  Below
        MIN_CLEARANCE_MM = no room."""
        mask = None if exclude is None else ~exclude
        S = self.seg if mask is None else self.seg[mask]
        room = np.inf
        if len(S):
            room = float((self.dist_to_segments(p, mask) - S[:, 4] / 2.0 - self.via_d / 2.0).min())
        if len(self.vias):
            room = min(room, float((np.hypot(self.vias[:, 0] - p[0], self.vias[:, 1] - p[1]) - self.vias[:, 2] / 2.0
                                    - self.via_d / 2.0).min()))
        r = math.hypot(p[0] - self.cx, p[1] - self.cy)
        if self.outline is not None:
            room = min(room, self.outline - r - self.via_d / 2.0 - edge_clear + self.clear)
        if self.bore is not None:
            room = min(room, r - self.bore - self.via_d / 2.0 - edge_clear + self.clear)
        return room

    def angle_deg(self, p):
        """The angle of p about the centre, in the generator's convention (x = cx + r cos a, y = cy + r sin a, the
        same as TERMINAL_DEG and the TX start angle)."""
        return math.degrees(math.atan2(p[1] - self.cy, p[0] - self.cx)) % 360.0


def _dang(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


# ====================================================================== the search
def find_rx_break(board, net_id, layers, centre_deg, span_deg, gap, edge_clear, avoid=(), separation=0.0):
    """The break of one RX coil: on the coil's segments on the first layer of `layers` that has a spot, within
    span_deg of centre_deg and at least `separation` from every point in `avoid` (the other marks of the set), the
    point where two through vias `gap` apart along the trace have the most room.
    Returns dict(p, t, layer, room, angle) or None."""
    need = board.clear
    own = gap / 2.0 + board.via_d / 2.0 + 0.3           # the trace being cut, this far from the break, does not count
    for layer in layers:
        idx = np.where((board.net == net_id) & (board.layer == layer))[0]
        best = None
        for i in idx:
            a, b = board.seg[i, 0:2], board.seg[i, 2:4]
            L = float(np.hypot(*(b - a)))
            if L < 1e-9:
                continue
            t = (b - a) / L
            for u in (0.0, 1.0 / 3.0, 2.0 / 3.0):
                p = a + u * (b - a)
                d = _dang(board.angle_deg(p), centre_deg)
                if d > span_deg or any(float(np.hypot(*(p - q))) < separation for q in avoid):
                    continue
                near = (board.net == net_id) & (board.layer == layer) & (board.dist_to_segments(p) < own)
                room = min(board.via_room(p + t * gap / 2.0, near, edge_clear), board.via_room(p - t * gap / 2.0, near, edge_clear))
                if room < need:
                    continue
                score = room - 0.004 * d                      # the most room, close to the terminal angle
                if best is None or score > best[0]:
                    best = (score, dict(p=p, t=t, layer=layer, room=room, angle=board.angle_deg(p)))
        if best is not None:
            return best[1]
    return None


def find_tx_end(board, net_id):
    """The stacked end of a TX coil: the point that is a free end of a segment on two layers and has no via of the
    net on it (a via there joins the layers: the inner joint of a series ring, not the terminal).  When there
    are several, the one furthest from the centre (the terminal at the end of a tail).
    Returns (point, [layers]) or None."""
    idx = np.where(board.net == net_id)[0]
    count = {}
    for i in idx:
        for p in (tuple(np.round(board.seg[i, 0:2], 4)), tuple(np.round(board.seg[i, 2:4], 4))):
            count[(p, board.layer[i])] = count.get((p, board.layer[i]), 0) + 1
    free = {}
    for (p, l), c in count.items():
        if c == 1:
            free.setdefault(p, []).append(l)
    own = board.vias[board.via_net == net_id] if len(board.vias) else board.vias

    def on_via(p):
        return len(own) > 0 and bool((np.hypot(own[:, 0] - p[0], own[:, 1] - p[1]) < own[:, 2] / 2.0 + 1e-3).any())

    stacked = [(p, ls) for p, ls in free.items() if len(ls) >= 2 and not on_via(p)]
    if stacked:
        p, ls = max(stacked, key=lambda s: math.hypot(s[0][0] - board.cx, s[0][1] - board.cy))
        return np.array(p), sorted(ls, key=lambda l: ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu").index(l))
    return None


def find_tx_sites(board, e, reach, edge_clear):
    """Two via sites for the two TX ends, mirror images about the radial line through the stacked end e, with
    room (copper on every layer, the edges, and each other), as close to the end as the room allows.
    Returns (site_a, site_b, room) or None."""
    out = e - np.array([board.cx, board.cy])
    out = out / (np.linalg.norm(out) + 1e-12)
    nrm = np.array([-out[1], out[0]])
    need = board.clear
    best = None
    for d in np.arange(0.5, reach + 1e-9, 0.1):
        for th in range(5, 176, 5):                                       # half plane, mirrored below
            a = e + d * (math.cos(math.radians(th)) * out + math.sin(math.radians(th)) * nrm)
            b = e + d * (math.cos(math.radians(th)) * out - math.sin(math.radians(th)) * nrm)
            pair = float(np.hypot(*(a - b))) - board.via_d
            room = min(board.via_room(a, None, edge_clear), board.via_room(b, None, edge_clear), pair)
            if room < need:
                continue
            score = min(room, 0.5) - 0.3 * d                              # room up to 0.5 mm counts, then the closest
            if best is None or score > best[0]:
                best = (score, a, b, room)
    return None if best is None else best[1:]


# ====================================================================== KiCad drawings (KiCad 7 format)
def _f(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


class Silk:
    def __init__(self, s, sides, font=None):
        self.s = s
        self.font = font
        self.layers = {"both": ["F.SilkS", "B.SilkS"], "top": ["F.SilkS"], "bottom": ["B.SilkS"]}[sides]
        self.items = []
        r, g, b = s.rgb
        self.colour = f"(color {r} {g} {b} 1)"

    def _stroke(self, kind="default"):
        return f"(stroke (width {_f(self.s.SILKSCREEN_LINE_WIDTH_MM)}) (type {kind}) {self.colour})"

    def line(self, p, q, dashed=False):
        for lay in self.layers:
            self.items.append(f'  (gr_line (start {_f(p[0])} {_f(p[1])}) (end {_f(q[0])} {_f(q[1])}) '
                              f'{self._stroke("dash" if dashed else "default")} (layer "{lay}"))')

    def dot(self, c, radius):
        for lay in self.layers:
            self.items.append(f'  (gr_circle (center {_f(c[0])} {_f(c[1])}) (end {_f(c[0] + radius)} {_f(c[1])}) '
                              f'{self._stroke()} (fill solid) (layer "{lay}"))')

    def text(self, p, label):
        """The label as strokes of the font: it runs from p to the right (+x on the page), its vertical middle at p.
        On the bottom it is mirrored about its own middle, so it reads right from below and keeps the same place on
        the page."""
        if self.font is None:
            return
        w = _f(self.s.SILKSCREEN_TEXT_STROKE_MM)
        for lay in self.layers:
            bottom = lay.startswith("B.")
            for a, b in self.font.layout(label, p[0], p[1], self.s.SILKSCREEN_TEXT_SIZE_MM, "left", mirror=bottom):
                self.items.append(f'  (gr_line (start {_f(a[0])} {_f(a[1])}) (end {_f(b[0])} {_f(b[1])}) '
                                  f'(stroke (width {w}) (type default) {self.colour}) (layer "{lay}"))')

    def box(self, centre, t, half_len, half_wid):
        n = np.array([-t[1], t[0]])
        c = [centre + t * half_len + n * half_wid, centre + t * half_len - n * half_wid,
             centre - t * half_len - n * half_wid, centre - t * half_len + n * half_wid]
        for i in range(4):
            self.line(c[i], c[(i + 1) % 4], dashed=True)


# ====================================================================== the names: placed so that nothing overlaps
def _rect(cx, cy, w, h):
    return [(cx - w / 2.0, cy - h / 2.0), (cx + w / 2.0, cy - h / 2.0), (cx + w / 2.0, cy + h / 2.0), (cx - w / 2.0, cy + h / 2.0)]


def _thick(p, q, half):
    """a segment from p to q as a rectangle of half width `half` (and `half` past each end)"""
    p, q = np.asarray(p, float), np.asarray(q, float)
    d = q - p
    L = float(np.hypot(*d))
    t = d / L if L > 1e-9 else np.array([1.0, 0.0])
    n = np.array([-t[1], t[0]]) * half
    a, b = p - t * half, q + t * half
    return [tuple(a + n), tuple(b + n), tuple(b - n), tuple(a - n)]


def _overlap(A, B):
    """two convex polygons (lists of (x, y)) overlap: no edge of either separates them"""
    for poly in (A, B):
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            nx, ny = y1 - y2, x2 - x1
            pa = [nx * x + ny * y for x, y in A]
            pb = [nx * x + ny * y for x, y in B]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


class Placer:
    """Finds a place for each lead name: the spot nearest to its via site, in the wanted direction if it is free,
    where the text covers none of the marks (boxes, dots, lines), none of the names placed before and none of the
    board's vias (silkscreen on a via is wiped by the fab), and lies inside the board edges.  The directions around
    the site are tried in the order of their angle from the wanted one, then further out; the vias are given up
    before anything else; if nothing is free the name goes to the wanted spot and that is reported."""
    PAD = 0.15            # the names keep this much from the marks and from each other
    EDGE = 0.3            # and this much from the bore and the outline

    def __init__(self, board, font, height):
        self.board, self.font, self.height = board, font, height
        self.marks = []                                              # polygons of the boxes, dots and lines
        self.names = []                                              # polygons of the names placed so far
        self.vias = [_rect(x, y, d, d) for x, y, d in board.vias]

    def mark(self, poly):
        self.marks.append([tuple(map(float, c)) for c in poly])

    def _on_board(self, rect):
        pts = rect + [((rect[i][0] + rect[(i + 1) % 4][0]) / 2.0, (rect[i][1] + rect[(i + 1) % 4][1]) / 2.0) for i in range(4)]
        for x, y in pts:
            r = math.hypot(x - self.board.cx, y - self.board.cy)
            if self.board.outline is not None and r > self.board.outline - self.EDGE:
                return False
            if self.board.bore is not None and r < self.board.bore + self.EDGE:
                return False
        return True

    def place(self, site, want, label, keep_off):
        """site: the via site;  want: the direction the name should go (unit vector);  keep_off: the distance from
        the site to the near edge of the text.  Returns ((x_left, y_middle), free)."""
        w, h = self.font.width(label, self.height), self.height
        a0 = math.atan2(want[1], want[0])
        rels = sorted(range(-180, 180, 30), key=lambda a: (abs(a), a))
        for allow_vias in (False, True):
            for extra in np.arange(0.0, 2.01, 0.25):
                for rel in rels:
                    a = a0 + math.radians(rel)
                    dx, dy = math.cos(a), math.sin(a)
                    half = w / 2.0 * abs(dx) + h / 2.0 * abs(dy)      # the text's extent in that direction
                    d = keep_off + extra + half
                    cx, cy = site[0] + dx * d, site[1] + dy * d
                    rect = _rect(cx, cy, w, h)
                    padded = _rect(cx, cy, w + 2 * self.PAD, h + 2 * self.PAD)
                    if not self._on_board(rect):
                        continue
                    if any(_overlap(padded, m) for m in self.marks) or any(_overlap(padded, n) for n in self.names):
                        continue
                    if not allow_vias and any(_overlap(rect, v) for v in self.vias):
                        continue
                    self.names.append(rect)
                    return (cx - w / 2.0, cy), True
        half = w / 2.0 * abs(want[0]) + h / 2.0 * abs(want[1])
        cx, cy = site[0] + want[0] * (keep_off + half), site[1] + want[1] * (keep_off + half)
        self.names.append(_rect(cx, cy, w, h))
        return (cx - w / 2.0, cy), False

    def leader(self, site, label, at, near):
        """A line from the via site to the text (placed with its left end at `at`) when the text's nearest point is
        further than `near` from the site; None when it sits next to its dot.  The line is kept as a mark."""
        w, h = self.font.width(label, self.height), self.height
        x0, y0, x1, y1 = at[0], at[1] - h / 2.0, at[0] + w, at[1] + h / 2.0
        c = np.array([min(max(site[0], x0), x1), min(max(site[1], y0), y1)])     # the text's point nearest the site
        d = c - np.asarray(site, float)
        L = float(np.hypot(*d))
        if L <= near:
            return None
        end = c - d / L * 0.12                                               # stop just short of the lettering
        self.marks.append(_thick(site, end, 0.1))
        return np.asarray(site, float), end


# ====================================================================== the step
class Result:
    def __init__(self):
        self.lines = []            # the record / console lines
        self.warnings = []
        self.marks = 0
        self.done = False


def _mm(p):
    return f"({_f(p[0])}, {_f(p[1])})"


def suggest(text, P, settings, font=None):
    """The marks for the written stator text.  Returns (new text or None, Result)."""
    res = Result()
    s = settings
    board = Board(text, P)
    silk = Silk(s, s.SILKSCREEN_SIDES, font)
    need = board.clear
    gap = s.SILKSCREEN_BREAK_VIA_GAP_MM
    if gap < board.via_d + need:
        res.warnings.append(f"SILKSCREEN_BREAK_VIA_GAP_MM = {gap:g} is less than a via plus the clearance "
                            f"({board.via_d + need:g} mm): using {board.via_d + need:g}")
        gap = board.via_d + need
    edge_clear = s.SILKSCREEN_VIA_EDGE_CLEARANCE_MM
    dot_r = s.SILKSCREEN_DOT_RADIUS_MM
    margin = s.SILKSCREEN_BOX_MARGIN_MM
    terminal = {"": float(TERMINAL_DEG)}          # the board is turned so that the TX terminal sits there
    modules = {"": (P, P)}                        # one set: the names carry no set number (SIN_1, TX_2, ...)
    labels = s.SILKSCREEN_LABELS and font is not None
    placer = Placer(board, font, s.SILKSCREEN_TEXT_SIZE_MM) if labels else None
    names = []                      # (site, wanted direction, name, keep-off): placed after all marks are known

    sep = s.SILKSCREEN_BREAK_SEPARATION_MM
    centre = np.array([board.cx, board.cy])
    for k in modules:
        RX, TX = modules[k]
        tx_nid = board.net_id.get(TX.TX_NET)
        end = find_tx_end(board, tx_nid) if tx_nid is not None else None
        avoid = [end[0]] if end is not None else []
        for coil, net_name in (("SIN", RX.RX_NET_PHASE_0_2), ("COS", RX.RX_NET_PHASE_1_3)):
            nid = board.net_id.get(net_name)
            if nid is None:
                res.warnings.append(f"net {net_name!r} is not in the stator file; no break suggested for {coil}{k}")
                continue
            on = sorted(set(board.layer[board.net == nid].tolist()))
            if not any(l in on for l in s.SILKSCREEN_BREAK_LAYERS):
                res.warnings.append(f"net {net_name!r} has no copper on {', '.join(s.SILKSCREEN_BREAK_LAYERS)} "
                                    f"(SILKSCREEN_BREAK_LAYERS); the coil runs on {', '.join(on)}: set "
                                    f"SILKSCREEN_BREAK_LAYERS to its layers. No break suggested for {coil}{k}")
                continue
            br = find_rx_break(board, nid, s.SILKSCREEN_BREAK_LAYERS, terminal[k], s.SILKSCREEN_SEARCH_SPAN_DEG, gap,
                               edge_clear, avoid, sep)
            if br is None:
                res.warnings.append(f"no spot on {net_name} within {s.SILKSCREEN_SEARCH_SPAN_DEG:g} deg of "
                                    f"{terminal[k]:g} deg, {sep:g} mm from the other marks, has room for two vias "
                                    f"(layers {', '.join(s.SILKSCREEN_BREAK_LAYERS)}); widen SILKSCREEN_SEARCH_SPAN_DEG, "
                                    f"lower SILKSCREEN_BREAK_SEPARATION_MM, or cut the coil by hand")
                continue
            p, t = br["p"], br["t"]
            avoid.append(p)
            n = np.array([-t[1], t[0]])
            if float(n @ (p - centre)) > 0:                 # the names go inwards: each TX ring lies outside its RX band
                n = -n
            sites = [p + t * gap / 2.0, p - t * gap / 2.0]
            silk.box(p, t, gap / 2.0 + margin, margin)
            if placer is not None:
                placer.mark(_thick(p - t * (gap / 2.0 + margin), p + t * (gap / 2.0 + margin), margin))
            for i, q in enumerate(sites, 1):
                silk.dot(q, dot_r)
                names.append((q, n, f"{coil}{k}_{i}", margin + 0.2))
            res.marks += 1
            r = math.hypot(p[0] - board.cx, p[1] - board.cy)
            res.lines.append(f"  {coil}{k} ({net_name}): cut the {LAYER_WORD.get(br['layer'], br['layer'])} trace at "
                             f"{_mm(p)} (r = {r:.2f} mm, {br['angle']:.1f} deg); vias {coil}{k}_1 at {_mm(sites[0])} and "
                             f"{coil}{k}_2 at {_mm(sites[1])}, clearance {br['room']:.2f} mm (at least {need:g} needed)")
        # the TX ends
        if tx_nid is None:
            res.warnings.append(f"net {TX.TX_NET!r} is not in the stator file; no via sites suggested for TX{k}")
            continue
        if end is None:
            res.warnings.append(f"the two ends of {TX.TX_NET} were not found stacked on two layers; no via "
                                f"sites suggested for TX{k}")
            continue
        e, layers = end
        sites = find_tx_sites(board, e, s.SILKSCREEN_TX_SITE_REACH_MM, edge_clear)
        if sites is None:
            res.warnings.append(f"no two via sites within {s.SILKSCREEN_TX_SITE_REACH_MM:g} mm of the TX{k} end "
                                f"at {_mm(e)} have room (copper on every layer, the board edge); extend the ends by hand")
            continue
        a, b, room = sites
        for i, (q, lay) in enumerate(zip((a, b), layers), 1):
            silk.dot(q, dot_r)
            silk.line(e, q, dashed=True)
            if placer is not None:
                placer.mark(_rect(q[0], q[1], 2 * dot_r, 2 * dot_r))
                placer.mark(_thick(e, q, s.SILKSCREEN_LINE_WIDTH_MM))
            away = q - e
            away /= (np.linalg.norm(away) + 1e-12)
            names.append((q, away, f"TX{k}_{i} {LABEL_WORD.get(lay, lay)}", dot_r + 0.25))
        res.marks += 1
        res.lines.append(f"  TX{k} ({TX.TX_NET}): both ends at {_mm(e)} (r = {math.hypot(e[0]-board.cx, e[1]-board.cy):.2f} mm, "
                         f"{board.angle_deg(e):.1f} deg), {LAYER_WORD.get(layers[0], layers[0])} and "
                         f"{LAYER_WORD.get(layers[1], layers[1])}; extend the {LAYER_WORD.get(layers[0], layers[0])} end to a via "
                         f"TX{k}_1 at {_mm(a)} and the {LAYER_WORD.get(layers[1], layers[1])} end to a via TX{k}_2 at {_mm(b)}, "
                         f"clearance {room:.2f} mm (at least {need:g} needed)")

    if placer is not None:
        crowded = []
        for site, want, name, keep_off in names:
            at, free = placer.place(site, want, name, keep_off)
            silk.text(at, name)
            leader = placer.leader(site, name, at, keep_off + 0.3)
            if leader is not None:                          # the name had to move away: a thin line ties it to its dot
                silk.line(*leader)
            if not free:
                crowded.append(name)
        if crowded:
            res.warnings.append(f"no free place was found for the name(s) {', '.join(crowded)}: drawn at the default "
                                f"spot, where they may cover other marks or vias")

    if s.SILKSCREEN_DOT_ON_ALL_VIAS:
        for x, y, _size in board.vias:
            silk.dot((x, y), dot_r)
        res.lines.append(f"  a dot on each of the {len(board.vias)} vias of the board (SILKSCREEN_DOT_ON_ALL_VIAS)")

    if not silk.items:
        return None, res
    sides = {"both": "F.SilkS and B.SilkS", "top": "F.SilkS", "bottom": "B.SilkS"}[s.SILKSCREEN_SIDES]
    res.lines.insert(0, f"  marks on {sides}, colour {s.SILKSCREEN_COLOR}, labels {'on' if s.SILKSCREEN_LABELS else 'off'}; "
                        f"a via of the suggestion keeps {need:g} mm from copper on every layer and "
                        f"{edge_clear:g} mm from the board edges")
    end = text.rstrip()
    if not end.endswith(")"):
        res.warnings.append("the stator file does not end with the closing bracket of (kicad_pcb ...); nothing added")
        return None, res
    new = end[:-1].rstrip("\n") + "\n\n" + "\n".join(silk.items) + "\n)\n"
    res.done = True
    return new, res


def add_to_file(path, P, quiet=False):
    """Read the written stator file, add the suggestion, write it back.  Prints what it did.  Returns the Result."""
    settings = Settings()
    res = Result()
    res.warnings += settings.warnings
    font = None
    if settings.SILKSCREEN_SUGGESTION and settings.SILKSCREEN_LABELS:
        font, why = load_font()
        if why:
            res.warnings.append(why)
    if not settings.SILKSCREEN_SUGGESTION:
        res.lines.append(f"  SILKSCREEN_SUGGESTION = False ({PARAMETER_FILE}): no silkscreen added")
        _print(res, quiet)
        return res
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        res.warnings.append(f"the stator file cannot be read ({e}); no silkscreen added")
        _print(res, quiet)
        return res
    try:
        new, r = suggest(text, P, settings, font)
    except Exception as e:                                               # never fail the generation
        res.warnings.append(f"the suggestion failed ({type(e).__name__}: {e}); the stator file is unchanged")
        _print(res, quiet)
        return res
    res.lines += r.lines
    res.warnings += r.warnings
    res.marks, res.done = r.marks, r.done
    if new is not None:
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new)
        except OSError as e:
            res.warnings.append(f"the stator file cannot be written ({e}); the silkscreen was not added")
            res.done = False
    _print(res, quiet)
    return res


def _print(res, quiet):
    if quiet:
        return
    for w in res.warnings:
        print("  " + Colour.yellow(f"WARNING {w}"))
    for line in res.lines:
        print(line)


def record_lines(res):
    out = ["LEAD CUTTING SILKSCREEN SUGGESTION", "-" * 34]
    if res.done:
        out.append(f"  {res.marks} suggestion(s) drawn into the stator file: break each RX coil between its two dots "
                   f"(a via at each dot, down to the bottom layer); extend each TX end to the dot of its name")
    else:
        out.append("  nothing was drawn")
    out += [f"  WARNING {w}" for w in res.warnings] + res.lines
    return out


def append_record(record_path, res):
    """Append the result and a verbatim copy of the settings file to Parameters.txt."""
    lines = record_lines(res) + [""]
    pdir = None
    try:
        import SilkScreenSuggestion_Parameters as M
        pdir = M.__file__
    except Exception:
        pass
    if pdir and os.path.isfile(pdir):
        lines.append(f"########## {PARAMETER_FILE} " + "#" * max(0, 60 - len(PARAMETER_FILE)))
        try:
            with open(pdir, encoding="utf-8") as fh:
                lines.append(fh.read().rstrip("\n"))
        except OSError as e:
            lines.append(f"(could not be read: {e})")
        lines.append("")
    try:
        with open(record_path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass
