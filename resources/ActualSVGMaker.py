"""
ActualSVGMaker.py  -  the copper of a generated board as it is, in one SVG: the stator on the left, the rotor on the right.

    python ActualSVGMaker.py <folder>                         the folder holds Stator.kicad_pcb and Rotor.kicad_pcb
    python ActualSVGMaker.py Stator.kicad_pcb Rotor.kicad_pcb
    python ActualSVGMaker.py <folder> --out board.svg

The SVG is written into the folder of the two board files and named <folder name>_Actual.svg.

Nothing is made to look better: no title, no text, no legend, no widened traces.  Every item is drawn at its true size
in mm (the SVG is 1:1, its width and height are in mm) with the coordinates copied from the KiCad file:
    traces    (segment ...) : a line of the trace's width with round ends, as KiCad draws a track
    vias      (via ...)     : a copper ring (size, with the drill as a hole) on every copper layer the via passes through
    copper    (gr_poly ...) on a copper layer : the filled polygon (the rotor sectors)
    outline   (gr_circle ...) on Edge.Cuts : the board edge, as a line of its own width
Silkscreen, solder mask and anything else that is not copper or the board edge is left out.

Each board is one group (Stator, Rotor) holding one group per layer, labelled F_Cu, Inner_1, Inner_2, B_Cu and
Edge_Cuts (only the layers the board has copper on).  The groups are Inkscape layers, so Inkscape shows and hides them
one by one; a browser simply draws them.  The layers are stacked as on the board: B_Cu at the bottom, F_Cu on top.
The rotor is moved to the right of the stator by a translation of its group; nothing inside it is changed.

Needs only Python 3 (no third-party package).
"""

import argparse
import math
import os
import re
import sys

LAYER_ID = {"F.Cu": "F_Cu", "In1.Cu": "Inner_1", "In2.Cu": "Inner_2", "B.Cu": "B_Cu"}
STACK = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")              # top to bottom
COLOUR = {"F.Cu": "#d62828", "In1.Cu": "#2a9d3f", "In2.Cu": "#e6b800", "B.Cu": "#1e64c8"}
EDGE_COLOUR = "#555555"
GAP_MM = 5.0                                               # between the stator's and the rotor's outline
MARGIN_MM = 1.0                                            # around both

N = r"(-?[\d.]+)"
SEG = re.compile(rf'\(segment \(start {N} {N}\) \(end {N} {N}\) \(width {N}\) \(layer "([^"]+)"\)')
VIA = re.compile(rf'\(via \(at {N} {N}\) \(size {N}\) \(drill {N}\) \(layers "([^"]+)" "([^"]+)"\)')
POLY = re.compile(r'\(gr_poly \(pts ((?:\(xy -?[\d.]+ -?[\d.]+\) ?)+)\)(.*?)\(layer "([^"]+)"\)')
XY = re.compile(rf'\(xy {N} {N}\)')
CIRCLE = re.compile(rf'\(gr_circle \(center {N} {N}\) \(end {N} {N}\)(.*?)\(layer "([^"]+)"\)')
WIDTH = re.compile(rf'\(width {N}\)')
BOARD_LAYERS = re.compile(r'\(\d+ "((?:F|In\d+|B)\.Cu)" signal\)')
NOT_DRAWN = re.compile(r'\((arc|zone|footprint) ')

STATOR_FILE, ROTOR_FILE = "Stator.kicad_pcb", "Rotor.kicad_pcb"


def read(path):
    """The copper and the board edge of one KiCad file, with every number kept as the text in the file."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    board = [l for l in STACK if l in set(BOARD_LAYERS.findall(text))] or list(STACK)
    segs = SEG.findall(text)
    vias = VIA.findall(text)
    polys = [(XY.findall(pts), lay) for pts, _rest, lay in POLY.findall(text) if lay in LAYER_ID]
    edges = []
    for cx, cy, ex, ey, rest, lay in CIRCLE.findall(text):
        if lay == "Edge.Cuts":
            w = WIDTH.search(rest)
            edges.append((cx, cy, math.hypot(float(ex) - float(cx), float(ey) - float(cy)), w.group(1) if w else "0.05"))
    if not edges:
        raise ValueError(f"no Edge.Cuts circle in {path}: is this a board the generator wrote?")
    skipped = sorted({k for k in NOT_DRAWN.findall(text)})
    return board, segs, vias, polys, edges, skipped


def via_layers(board, a, b):
    """The copper layers a via from layer a to layer b passes through (a through via: all of the board's layers)."""
    i, j = sorted((STACK.index(a), STACK.index(b)))
    return [l for l in STACK[i:j + 1] if l in board]


def ring(cx, cy, size, drill):
    """A via's copper: a disc of the via size with the drill as a hole (even-odd fill)."""
    x, y, r, h = float(cx), float(cy), float(size) / 2, float(drill) / 2
    disc = lambda q: f"M{x - q:g} {y:g}a{q:g} {q:g} 0 1 0 {2 * q:g} 0a{q:g} {q:g} 0 1 0 {-2 * q:g} 0Z"
    return f'<path d="{disc(r)}{disc(h)}"/>'


def board_group(name, data, transform=""):
    board, segs, vias, polys, edges, _skipped = data
    out = [f'<g id="{name}" inkscape:groupmode="layer" inkscape:label="{name}"{transform}>']
    for lay in reversed(STACK):                            # B_Cu first, F_Cu last (on top)
        items = []
        for x1, y1, x2, y2, w, l in segs:
            if l == lay:
                items.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke-width="{w}"/>')
        fills = [f'<polygon points="{" ".join(f"{x},{y}" for x, y in pts)}"/>' for pts, l in polys if l == lay]
        fills += [ring(x, y, s, d) for x, y, s, d, a, b in vias if lay in via_layers(board, a, b)]
        if not items and not fills:
            continue
        lid = LAYER_ID[lay]
        out.append(f'<g id="{name}_{lid}" inkscape:groupmode="layer" inkscape:label="{lid}">')
        if items:
            out.append(f'<g fill="none" stroke="{COLOUR[lay]}" stroke-linecap="round">')
            out += items
            out.append('</g>')
        if fills:
            out.append(f'<g fill="{COLOUR[lay]}" fill-rule="evenodd" stroke="none">')
            out += fills
            out.append('</g>')
        out.append('</g>')
    out.append(f'<g id="{name}_Edge_Cuts" inkscape:groupmode="layer" inkscape:label="Edge_Cuts" fill="none" '
               f'stroke="{EDGE_COLOUR}">')
    out += [f'<circle cx="{cx}" cy="{cy}" r="{r:g}" stroke-width="{w}"/>' for cx, cy, r, w in edges]
    out.append('</g>')
    out.append('</g>')
    return out


def render(stator_path, rotor_path, out=None):
    stator, rotor = read(stator_path), read(rotor_path)
    s_out = max(stator[4], key=lambda e: e[2])
    r_out = max(rotor[4], key=lambda e: e[2])
    scx, scy, sr = float(s_out[0]), float(s_out[1]), s_out[2]
    rcx, rcy, rr = float(r_out[0]), float(r_out[1]), r_out[2]
    dx = (scx + sr + GAP_MM + rr) - rcx                    # the rotor's centre goes this far right of where it is
    dy = scy - rcy
    x0, y0 = scx - sr - MARGIN_MM, scy - max(sr, rr) - MARGIN_MM
    W = 2 * sr + GAP_MM + 2 * rr + 2 * MARGIN_MM
    H = 2 * max(sr, rr) + 2 * MARGIN_MM
    out = out or os.path.join(os.path.dirname(os.path.abspath(stator_path)),
                              os.path.basename(os.path.dirname(os.path.abspath(stator_path))) + "_Actual.svg")
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
         f'width="{W:g}mm" height="{H:g}mm" viewBox="{x0:g} {y0:g} {W:g} {H:g}">']
    o += board_group("Stator", stator)
    o += board_group("Rotor", rotor, f' transform="translate({dx:g} {dy:g})"')
    o.append('</svg>')
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(o) + "\n")
    for path, data in ((stator_path, stator), (rotor_path, rotor)):
        if data[5]:
            print(f"note: {os.path.basename(path)} has {', '.join(data[5])} items, which are not drawn", file=sys.stderr)
    return out


def make_svg(folder, out=None):
    """The SVG of the board in a generator's output folder (Stator.kicad_pcb + Rotor.kicad_pcb); returns its path."""
    return render(os.path.join(folder, STATOR_FILE), os.path.join(folder, ROTOR_FILE), out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="The copper of a board as it is, in one SVG: stator left, rotor right.")
    ap.add_argument("paths", nargs="+", help="the folder with Stator.kicad_pcb and Rotor.kicad_pcb, or the two files "
                                             "(stator first)")
    ap.add_argument("--out", help="the SVG to write (default: <folder name>_Actual.svg in the folder of the stator)")
    a = ap.parse_args(argv)
    try:
        if len(a.paths) == 1 and os.path.isdir(a.paths[0]):
            print("wrote", make_svg(a.paths[0], a.out))
        elif len(a.paths) == 2:
            print("wrote", render(a.paths[0], a.paths[1], a.out))
        else:
            ap.error("give one folder, or the stator file and the rotor file")
    except (OSError, ValueError) as e:
        raise SystemExit(f"cannot write the SVG: {e}")


if __name__ == "__main__":
    main(sys.argv[1:])
