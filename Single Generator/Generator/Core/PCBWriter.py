"""
PCBWriter.py  -  writes a board as a KiCad 7 .kicad_pcb file (readable by KiCad 7, 8, 9 and 10): nets, track
segments, vias, circles and filled polygons, the title block and the page.  Used by the stator and the rotor.
Nothing to edit here.
"""

import math


class KiCadBoard:
    _COPPER2 = """\
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)"""
    _COPPER4 = """\
    (0 "F.Cu" signal)
    (1 "In1.Cu" signal)
    (2 "In2.Cu" signal)
    (31 "B.Cu" signal)"""
    _LAYERS = """\
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user "B.Mask")
    (39 "F.Mask" user "F.Mask")
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)"""

    def __init__(self, title="Inductive sensor", page=(200, 200), thickness=1.6, copper_layers=2, comments=None):
        """comments: up to 9 lines for the comment fields of the title block (KiCad: Comment1 ... Comment9;
        its default drawing sheet shows Comment1 ... Comment4, Comment1 at the bottom)."""
        self.copper_layers = int(copper_layers)
        self.title, self.page, self.thickness = title, page, thickness
        self.comments = list(comments) if comments else []
        self.nets = {"": 0}
        self.body = []

    def net(self, name):
        if name not in self.nets:
            self.nets[name] = len(self.nets)
        return self.nets[name]

    @staticmethod
    def _q(s):
        """Text for the file: no double quotes, backslashes or line breaks."""
        return str(s).replace("\\", "/").replace('"', "'").replace("\n", " ")

    @staticmethod
    def _f(v):
        s = f"{v:.6f}".rstrip("0").rstrip(".")
        return "0" if s in ("", "-0") else s

    def segment(self, p, q, width, layer, net):
        f = self._f
        self.body.append(
            f'  (segment (start {f(p[0])} {f(p[1])}) (end {f(q[0])} {f(q[1])}) '
            f'(width {f(width)}) (layer "{layer}") (net {self.net(net)}))')

    def via(self, p, size, drill, net):
        f = self._f
        self.body.append(
            f'  (via (at {f(p[0])} {f(p[1])}) (size {f(size)}) (drill {f(drill)}) '
            f'(layers "F.Cu" "B.Cu") (net {self.net(net)}))')

    def circle(self, c, radius, layer, width):
        f = self._f
        self.body.append(
            f'  (gr_circle (center {f(c[0])} {f(c[1])}) (end {f(c[0])} {f(c[1] + radius)}) '
            f'(layer "{layer}") (width {f(width)}) (fill none))')

    def polygon(self, points, layer):
        f = self._f
        pts = " ".join(f"(xy {f(x)} {f(y)})" for x, y in points)
        self.body.append(f'  (gr_poly (pts {pts}) (layer "{layer}") (width 0) (fill solid))')

    def text(self):
        out = ["(kicad_pcb (version 20221018) (generator coil_generator)", "",
               f"  (general (thickness {self._f(self.thickness)}))", "",
               f'  (paper "User" {self.page[0]} {self.page[1]})',
               "  (title_block (title \"" + self._q(self.title) + "\")"
               + "".join(f' (comment {i} "{self._q(c)}")' for i, c in enumerate(self.comments[:9], 1)) + ")", "",
               "  (layers", self._COPPER4 if self.copper_layers == 4 else self._COPPER2,
               self._LAYERS, "  )", "",
               "  (setup (pad_to_mask_clearance 0))", ""]
        for name, idx in sorted(self.nets.items(), key=lambda kv: kv[1]):
            out.append(f'  (net {idx} "{name}")')
        out.append("")
        out.extend(self.body)
        out.append(")")
        return "\n".join(out) + "\n"

    def save(self, path):
        with open(path, "w", newline="\n") as fh:
            fh.write(self.text())


# KiCad's default drawing sheet (KiCad 7 ... 9): a frame 10 mm and 12 mm inside the page edge, and the title block
# 108 x 32 mm in the bottom right corner of the inner frame
SHEET_FRAME_MM = 12.0
TITLE_BLOCK_MM = (108.0, 32.0)
PAGE_GAP_MM = 3.0                   # free space between the board and the frame / the title block


def page_size(P, cx, cy, radius):
    """KiCad page size (width, height, mm) for a round board of `radius` (its outer edge) centred at (cx, cy) on the
    page: at least PAGE_SIZE_MM, grown (right and down, so the board keeps its position) until the board stays
    PAGE_GAP_MM clear of the right and bottom side of the drawing frame and of the title block.  Of the sizes that do
    that, the one with the smallest area.  Only the right and bottom sides are handled: the top and left side
    depend on CENTER_X_MM / CENTER_Y_MM, which DesignChecks.check_design checks (for the stator and the rotor)."""
    w0, h0 = (float(v) for v in P.PAGE_SIZE_MM)
    R = float(radius) + float(P.EDGE_LINE_WIDTH_MM) / 2.0 + PAGE_GAP_MM
    fr = SHEET_FRAME_MM
    tw, th = TITLE_BLOCK_MM
    w_min = max(w0, math.ceil(cx + R + fr))
    h_min = max(h0, math.ceil(cy + R + fr))

    def clear(w, h):
        # distance from the board centre to the title block rectangle
        x0, x1, y0, y1 = w - fr - tw, w - fr, h - fr - th, h - fr
        dx = max(x0 - cx, 0.0, cx - x1)
        dy = max(y0 - cy, 0.0, cy - y1)
        return math.hypot(dx, dy) >= R

    best = None
    w = w_min
    while True:
        h = h_min
        while not clear(w, h):
            h += 1.0
        if best is None or w * h < best[0] * best[1] - 1e-9:
            best = (w, h)
        if h == h_min:                     # (wider pages cannot make it any smaller)
            break
        w += 1.0
    return best
