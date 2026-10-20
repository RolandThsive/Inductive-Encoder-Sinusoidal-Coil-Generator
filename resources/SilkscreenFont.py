"""
SilkscreenFont.py  -  the stroke font of the silkscreen suggestions: the lead names (SIN1_1, TX2_2 TOP, ...) are
drawn as plain lines on the silkscreen, not as KiCad text, so a board file carries no font and every viewer and
every fab draws exactly the same strokes.

The glyphs are this repository's own design (drawn for it, no outside font data): capital letters, digits and a
few signs on a 4 x 6 grid, each a few straight strokes.  Lowercase letters are drawn as capitals.  The file lives
in `resources` at the root of the repository, outside the generators, so that every generator can use it; it is
under the repository's licence (LICENSE.md).  Used by
Dual Generator/Dual_Generator/Stator/Dual_LeadCutting_SilkscreenSuggestion.py, which loads it by its path.

    segments = layout("SIN1_1", x, y, height_mm, anchor="left", mirror=False)
        -> [((x1, y1), (x2, y2)), ...] in board coordinates (KiCad: y grows downwards), the text's vertical middle
           at y;  anchor "left": the text starts at x, "right": it ends at x;  mirror=True flips the text about
           its own middle, for the bottom silkscreen (it then reads right when the board is seen from below and
           keeps the same place on the page)
    width("SIN1_1", height_mm) -> the width of the text (mm)
"""

# every glyph: a list of polylines on a grid x = 0 ... 4, y = 0 ... 6 (y up, 0 = baseline)
GLYPHS = {
    "A": [[(0, 0), (0, 4), (2, 6), (4, 4), (4, 0)], [(0, 3), (4, 3)]],
    "B": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    "C": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1)]],
    "D": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 1), (3, 0), (0, 0)]],
    "E": [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    "F": [[(0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    "G": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (2, 3)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(1, 0), (3, 0)], [(2, 0), (2, 6)], [(1, 6), (3, 6)]],
    "J": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 6)]],
    "K": [[(0, 0), (0, 6)], [(4, 6), (0, 2)], [(1, 3), (4, 0)]],
    "L": [[(0, 6), (0, 0), (4, 0)]],
    "M": [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]],
    "N": [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    "O": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)]],
    "P": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)]],
    "Q": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)], [(2, 2), (4, 0)]],
    "R": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(1, 3), (4, 0)]],
    "S": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "T": [[(0, 6), (4, 6)], [(2, 6), (2, 0)]],
    "U": [[(0, 6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)]],
    "V": [[(0, 6), (2, 0), (4, 6)]],
    "W": [[(0, 6), (1, 0), (2, 4), (3, 0), (4, 6)]],
    "X": [[(0, 0), (4, 6)], [(0, 6), (4, 0)]],
    "Y": [[(0, 6), (2, 3), (4, 6)], [(2, 3), (2, 0)]],
    "Z": [[(0, 6), (4, 6), (0, 0), (4, 0)]],
    "0": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)], [(0, 1), (4, 5)]],
    "1": [[(1, 5), (2, 6), (2, 0)], [(1, 0), (3, 0)]],
    "2": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (0, 0), (4, 0)]],
    "3": [[(0, 6), (4, 6), (2, 4), (3, 4), (4, 3), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "4": [[(3, 0), (3, 6), (0, 2), (4, 2)]],
    "5": [[(4, 6), (0, 6), (0, 3), (3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    "6": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)]],
    "7": [[(0, 6), (4, 6), (1, 0)]],
    "8": [[(1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (1, 3), (0, 2), (0, 1), (1, 0), (3, 0),
           (4, 1), (4, 2), (3, 3)]],
    "9": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (4, 3)]],
    "_": [[(0, 0), (4, 0)]],
    "-": [[(0, 3), (4, 3)]],
    "+": [[(2, 1), (2, 5)], [(0, 3), (4, 3)]],
    ".": [[(2, 0), (2, 0.6)]],
    ":": [[(2, 1), (2, 1.6)], [(2, 4), (2, 4.6)]],
    "/": [[(0, 0), (4, 6)]],
    " ": [],
}
GRID_W, GRID_H, ADVANCE = 4.0, 6.0, 5.0        # glyph width, height and pitch on the grid
UNKNOWN = [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)]]   # a box for a character the font does not have


def _glyph(ch):
    return GLYPHS.get(ch.upper(), UNKNOWN)


def width(text, height):
    """the width of the text in mm (the last glyph without its trailing gap)"""
    n = len(text)
    return 0.0 if n == 0 else (ADVANCE * (n - 1) + GRID_W) * height / GRID_H


def layout(text, x, y, height, anchor="left", mirror=False):
    """The strokes of `text` as segments ((x1, y1), (x2, y2)) in board coordinates: `height` = the height of a
    capital (mm); the text's vertical middle at y; it starts at x (anchor "left") or ends at x ("right").
    mirror=True flips it about its own vertical middle line (for the bottom silkscreen)."""
    s = height / GRID_H
    w = width(text, height)
    x0 = x if anchor == "left" else x - w
    xm = x0 + w / 2.0
    out = []
    for i, ch in enumerate(text):
        gx = x0 + i * ADVANCE * s
        for poly in _glyph(ch):
            pts = []
            for u, v in poly:
                px = gx + u * s
                if mirror:
                    px = 2.0 * xm - px
                py = y - (v - GRID_H / 2.0) * s           # y down on the board; the middle of the glyph at y
                pts.append((px, py))
            out += [(pts[j], pts[j + 1]) for j in range(len(pts) - 1)]
    return out
