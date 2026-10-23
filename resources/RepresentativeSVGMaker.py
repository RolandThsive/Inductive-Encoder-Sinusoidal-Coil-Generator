"""
RepresentativeSVGMaker.py  -  one picture of a generated board: the stator on the left, the rotor on the right.

    python RepresentativeSVGMaker.py <folder>                        the folder holds Stator.kicad_pcb and Rotor.kicad_pcb
    python RepresentativeSVGMaker.py Stator.kicad_pcb Rotor.kicad_pcb
    python RepresentativeSVGMaker.py <folder> --air-gap 1
    python RepresentativeSVGMaker.py <folder> --out picture.svg --title "my own title line"

The picture is an SVG file written into the folder of the two board files and named <folder name>_Representative.svg
(DualCoil_7.25_26.875_1x16_4x4_Representative.svg, Coil_15_27_1_1_3_Single_SteppedDiagonal_Representative.svg).
The generators call make_svg(folder) as their last step, so every Single and Dual run leaves the picture next to
its boards.

Reads the two KiCad files the generator wrote (nothing else) and draws:
    stator : the board ring, every copper trace in the colour of its layer, the vias
    rotor  : the disc with its bore, the copper sectors of the Top layer and, when there are any, of the Bottom layer
    title  : from the stator's title block (loops, TX turns, radii), plus the air gap when given
    legend : the stator layers that carry copper, the via, the rotor copper that exists

Colours (edit COLOUR below):  Top red, Inner 1 green, Inner 2 yellow, Bottom blue.
The TX turns on Inner 2 lie exactly under those on Top (series wiring, same radii), so the copper layers under Top
(Inner 2 and Bottom) are drawn UNDER_TOP_WIDTH times wider: a coloured edge shows on both sides of each Top trace.
Set UNDER_TOP_WIDTH = 1.0 for true widths.
On the rotor the Top copper is filled; the copper of every layer under it lies at the same place and is shown as a
dashed outline in its layer colour, a little heavier for each level further down.

Needs only Python 3 (no third-party package).  The SVG opens in any browser.
"""

import argparse
import math
import os
import re
import sys

# ---- the look ---------------------------------------------------------------------------------------------
COLOUR = {"F.Cu": "#d62828",      # Top        red
          "In1.Cu": "#2a9d3f",    # Inner 1    green
          "In2.Cu": "#e6b800",    # Inner 2    yellow
          "B.Cu": "#1e64c8"}      # Bottom     blue
WORD = {"F.Cu": "Top", "In1.Cu": "Inner 1", "In2.Cu": "Inner 2", "B.Cu": "Bottom"}
DRAW_ORDER = ("B.Cu", "In2.Cu", "In1.Cu", "F.Cu")          # bottom first, Top last (on top)
UNDER_TOP_WIDTH = 1.9                                      # Inner 2 and Bottom drawn this much wider (1.0 = true)
VIA_COLOUR, VIA_EDGE = "#333333", "#444444"
ROTOR_COPPER = {"F.Cu": ("#d62828", "#8a1a1a"),            # the rotor's copper: fill, edge  (Top red)
                "In1.Cu": ("#3f9d6a", "#256b45"),          #                                 (Inner 1 green)
                "In2.Cu": ("#e0a21b", "#9a6d0c"),          #                                 (Inner 2 amber)
                "B.Cu": ("#7a4fc4", "#4a2c80")}            #                                 (Bottom violet)
BOARD_FILL, EDGE_LINE = "#eef3e8", "#555555"
FONT = "Inter, Helvetica, Arial, sans-serif"
SVG_WIDTH_PX = 2240                                        # the size the SVG opens at; it scales without loss

# ---- what is read from the KiCad files --------------------------------------------------------------------
SEG = re.compile(r'\(segment \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\) \(width ([\d.]+)\) '
                 r'\(layer "([^"]+)"\) \(net (\d+)\)')
VIA = re.compile(r'\(via \(at ([-\d.]+) ([-\d.]+)\) \(size ([\d.]+)\)')
NET = re.compile(r'\(net (\d+) "([^"]*)"\)')
CIRCLE = re.compile(r'\(gr_circle \(center ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\) \(layer "([^"]+)"\)')
POLY = re.compile(r'\(gr_poly \(pts ((?:\(xy [-\d.]+ [-\d.]+\) ?)+)\) \(layer "([^"]+)"\)')
XY = re.compile(r'\(xy ([-\d.]+) ([-\d.]+)\)')
TITLE = re.compile(r'\(title "([^"]*)"\)')
COMMENT = re.compile(r'\(comment (\d) "([^"]*)"\)')

STATOR_FILE, ROTOR_FILE = "Stator.kicad_pcb", "Rotor.kicad_pcb"


def read(path):
    """segments, vias, circles, polygons, title, {comment number: text} of one KiCad board file."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    nets = {int(n): name for n, name in NET.findall(text)}
    segs = [(float(a), float(b), float(c), float(d), float(w), lay, nets.get(int(n), ""))
            for a, b, c, d, w, lay, n in SEG.findall(text)]
    vias = [(float(x), float(y), float(s)) for x, y, s in VIA.findall(text)]
    circles = [(float(cx), float(cy), math.hypot(float(ex) - float(cx), float(ey) - float(cy)), lay)
               for cx, cy, ex, ey, lay in CIRCLE.findall(text)]
    polys = [([(float(x), float(y)) for x, y in XY.findall(pts)], lay) for pts, lay in POLY.findall(text)]
    title = TITLE.search(text)
    comments = {int(n): t for n, t in COMMENT.findall(text)}
    return segs, vias, circles, polys, (title.group(1) if title else ""), comments


def edges(circles):
    """(centre x, centre y, outer radius, inner radius) from the Edge.Cuts circles."""
    cuts = [c for c in circles if c[3] == "Edge.Cuts"]
    if not cuts:
        raise ValueError("no Edge.Cuts circle in the file: is this a board the generator wrote?")
    return cuts[0][0], cuts[0][1], max(c[2] for c in cuts), min(c[2] for c in cuts)


def board_values(comments):
    """(loops per set, TX turns per set, outer radius, inner radius) from the stator's title block comments; the
    turns are listed once per set (the title block names each set's turns twice, once per TX layer)."""
    text = " ".join(comments.get(i, "") for i in sorted(comments))
    loops = re.findall(r"Loops: (\d+)", text)
    turns = re.findall(r"Turns: (\d+)", text)
    if loops and len(turns) == 2 * len(loops):
        turns = turns[::2]
    radii = re.search(r"Radius-Outer: ([\d.]+) mm, Radius-Inner: ([\d.]+) mm", text)
    return loops, turns, (radii.group(1) if radii else None), (radii.group(2) if radii else None)


def title_from(stator_title, comments, air_gap):
    """The title line from the stator's title block: loops, TX turns per layer, board radii, air gap."""
    loops, turns, r_out, r_in = board_values(comments)
    parts = []
    if loops:
        parts.append(" + ".join(f"{n}x" for n in loops) + " loops")
    if turns:
        parts.append("TX " + " + ".join(turns) + " turns per layer")
    if r_in and r_out:
        parts.append(f"board r {r_in} to {r_out} mm")
    if air_gap is not None:
        parts.append(f"air gap {air_gap:g} mm")
    if not parts:
        parts.append(stator_title)
    return " · ".join(parts)


def sector_text(rotor_title, n_polys):
    """'16 sectors', '1 + 16 sectors', '1 sector': from the rotor's title ('Dual rotor 1 + 16 sectors'); the number
    of Top polygons when the title says nothing."""
    m = re.search(r"(\d+(?: \+ \d+)*) sectors?", rotor_title)
    counts = m.group(1) if m else str(n_polys)
    return f"{counts} sector" if counts == "1" else f"{counts} sectors"


def picture_path(stator_path):
    """<name of the folder of the stator file>_Representative.svg inside that folder."""
    folder = os.path.dirname(os.path.abspath(stator_path))
    return os.path.join(folder, os.path.basename(folder) + "_Representative.svg")


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def f(x):
    return f"{x:.3f}".rstrip("0").rstrip(".")


def render(stator_path, rotor_path, out=None, title=None, air_gap=None):
    segs, vias, circles, _p, s_title, comments = read(stator_path)
    _s, _v, r_circles, r_polys, r_title, _c = read(rotor_path)
    cx, cy, r_out, r_in = edges(circles)
    rcx, rcy, rr_out, rr_in = edges(r_circles)
    title = title or title_from(s_title, comments, air_gap)
    out = out or picture_path(stator_path)
    R = max(r_out, rr_out) * 1.04                          # half the width of each panel, mm

    # the sheet is measured in mm: two square panels side by side, a title strip above, a legend strip below
    gap, top, bottom = 0.08 * R, 0.55 * R, 0.85 * R
    W, H = 4 * R + 3 * gap, 2 * R + top + bottom
    ox = {"stator": gap + R, "rotor": 2 * gap + 3 * R}     # the panel centres
    oy = top + R
    u = R / 40.0                                           # a unit for text and symbols, scaled with the board

    def pos(panel, x, y, c):                               # KiCad's y axis points down, as in SVG: no flip
        return ox[panel] + (x - c[0]), oy + (y - c[1])

    sc, rc = (cx, cy), (rcx, rcy)
    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {f(W)} {f(H)}" width="{SVG_WIDTH_PX}" '
             f'height="{f(SVG_WIDTH_PX * H / W)}" font-family="{FONT}">')
    o.append(f'<rect width="{f(W)}" height="{f(H)}" fill="white"/>')
    o.append(f'<text x="{f(W / 2)}" y="{f(top * 0.38)}" text-anchor="middle" font-size="{f(u * 1.9)}" '
             f'fill="#333333">{esc(title)}</text>')
    for panel, name in (("stator", "Stator"), ("rotor", "Rotor")):
        o.append(f'<text x="{f(ox[panel])}" y="{f(top * 0.85)}" text-anchor="middle" font-size="{f(u * 2.2)}" '
                 f'fill="#222222">{name}</text>')

    # the stator: the board ring (an even-odd path: outer circle with the bore cut out), the copper layer by layer, the vias
    px, py = pos("stator", cx, cy, sc)
    o.append(f'<path fill="{BOARD_FILL}" fill-rule="evenodd" stroke="{EDGE_LINE}" stroke-width="{f(u * 0.12)}" '
             f'd="M{f(px - r_out)} {f(py)}a{f(r_out)} {f(r_out)} 0 1 0 {f(2 * r_out)} 0a{f(r_out)} {f(r_out)} 0 1 0 '
             f'{f(-2 * r_out)} 0ZM{f(px - r_in)} {f(py)}a{f(r_in)} {f(r_in)} 0 1 0 {f(2 * r_in)} 0a{f(r_in)} {f(r_in)} 0 1 0 '
             f'{f(-2 * r_in)} 0Z"/>')
    present = [lay for lay in DRAW_ORDER if any(s[5] == lay for s in segs)]
    top_present = "F.Cu" in present
    wider_layers = [l for l in present if top_present and l in ("In2.Cu", "B.Cu")]
    for lay in present:
        wide = UNDER_TOP_WIDTH if lay in wider_layers else 1.0
        o.append(f'<g stroke="{COLOUR[lay]}" stroke-linecap="round" fill="none">')
        for a, b, c, d, w, l, _n in segs:
            if l != lay:
                continue
            x1, y1 = pos("stator", a, b, sc)
            x2, y2 = pos("stator", c, d, sc)
            o.append(f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" stroke-width="{f(max(w * wide, u * 0.12))}"/>')
        o.append('</g>')
    if vias:
        o.append(f'<g fill="{VIA_COLOUR}" stroke="{VIA_EDGE}" stroke-width="{f(u * 0.06)}">')
        for x, y, s in vias:
            vx, vy = pos("stator", x, y, sc)
            o.append(f'<circle cx="{f(vx)}" cy="{f(vy)}" r="{f(s / 2)}"/>')
        o.append('</g>')

    # the rotor: the disc and its bore around the rotor's own centre, then the copper, Bottom first
    rx, ry = pos("rotor", rcx, rcy, rc)
    o.append(f'<circle cx="{f(rx)}" cy="{f(ry)}" r="{f(rr_out)}" fill="white" stroke="{EDGE_LINE}" stroke-width="{f(u * 0.15)}"/>')
    o.append(f'<circle cx="{f(rx)}" cy="{f(ry)}" r="{f(rr_in)}" fill="white" stroke="{EDGE_LINE}" stroke-width="{f(u * 0.15)}"/>')
    rotor_layers = [lay for lay in reversed(DRAW_ORDER) if any(l == lay for _p2, l in r_polys)]    # Top first
    rlevel = {lay: n for n, lay in enumerate(rotor_layers)}      # 0 = Top
    for lay in reversed(rotor_layers):                     # deepest first, Top last
        fill, edge = ROTOR_COPPER[lay]
        k = rlevel[lay]
        if k == 0:
            o.append(f'<g fill="{fill}" stroke="{edge}" stroke-width="{f(u * 0.08)}" stroke-linejoin="round">')
        else:                                              # copper under Top: a dashed outline, heavier the deeper it lies
            o.append(f'<g fill="none" stroke="{fill}" stroke-width="{f(u * (0.4 + 0.3 * (k - 1)))}" '
                     f'stroke-dasharray="{f(u * 0.9)} {f(u * 0.6)}" stroke-dashoffset="{f(u * 0.4 * k)}" stroke-linejoin="round">')
        for pts, l in r_polys:
            if l == lay:
                o.append('<polygon points="' + " ".join(
                    f"{f(x)},{f(y)}" for x, y in (pos("rotor", px_, py_, rc) for px_, py_ in pts)) + '"/>')
        o.append('</g>')

    # the legend: only what the pictures show
    items = [("line", COLOUR[l], WORD[l]) for l in COLOUR if l in present]
    if vias:
        items.append(("via", VIA_COLOUR, "Via"))
    for lay in rotor_layers:
        n = sum(1 for _p2, l in r_polys if l == lay)
        label = f"Rotor copper, {WORD[lay]} ({sector_text(r_title, n) if lay == 'F.Cu' else sector_text('', n)})"
        items.append(("patch", ROTOR_COPPER[lay][0], label))
    rows = ([i for i in items if i[0] != "patch"], [i for i in items if i[0] == "patch"])   # stator row, rotor row
    for row, ly in zip(rows, (H - bottom * 0.86, H - bottom * 0.58)):
        widths = [u * (4.5 + 0.95 * len(label)) + u * 3 for _k, _c, label in row]
        x = (W - sum(widths)) / 2
        for (kind, colour, label), w in zip(row, widths):
            if kind == "line":
                o.append(f'<line x1="{f(x)}" y1="{f(ly)}" x2="{f(x + u * 2.6)}" y2="{f(ly)}" stroke="{colour}" '
                         f'stroke-width="{f(u * 0.45)}" stroke-linecap="round"/>')
            elif kind == "via":
                o.append(f'<circle cx="{f(x + u * 1.3)}" cy="{f(ly)}" r="{f(u * 0.7)}" fill="{colour}" stroke="{VIA_EDGE}" '
                         f'stroke-width="{f(u * 0.06)}"/>')
            else:
                o.append(f'<rect x="{f(x)}" y="{f(ly - u * 0.8)}" width="{f(u * 2.6)}" height="{f(u * 1.6)}" fill="{colour}"/>')
            o.append(f'<text x="{f(x + u * 3.6)}" y="{f(ly + u * 0.65)}" font-size="{f(u * 1.9)}" fill="#222222">{esc(label)}</text>')
            x += w

    order = list(COLOUR)
    rx_on = sorted({s[5] for s in segs if not s[6].startswith("TX")}, key=order.index)
    tx_on = sorted({s[5] for s in segs if s[6].startswith("TX")}, key=order.index)
    note = f"RX on {' + '.join(WORD[l] for l in rx_on)}, TX on {' + '.join(WORD[l] for l in tx_on)}"
    if UNDER_TOP_WIDTH != 1.0 and wider_layers:
        names = " and ".join(WORD[l] for l in wider_layers)
        note += f"; {names} {'is' if len(wider_layers) == 1 else 'are'} drawn wider, so the traces under Top show an edge"
    o.append(f'<text x="{f(W / 2)}" y="{f(H - bottom * 0.14)}" text-anchor="middle" font-size="{f(u * 1.7)}" '
             f'fill="#555555">{esc(note)}</text>')
    o.append('</svg>')
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(o) + "\n")
    return out


def make_svg(folder, out=None, title=None, air_gap=None):
    """The picture of the board in a generator's output folder (Stator.kicad_pcb + Rotor.kicad_pcb); returns its path."""
    return render(os.path.join(folder, STATOR_FILE), os.path.join(folder, ROTOR_FILE), out, title, air_gap)


def main(argv=None):
    ap = argparse.ArgumentParser(description="One picture of a board: stator left, rotor right.")
    ap.add_argument("paths", nargs="+", help="the folder with Stator.kicad_pcb and Rotor.kicad_pcb, or the two files "
                                             "(stator first)")
    ap.add_argument("--out", help="the picture to write (default: <folder name>_Representative.svg in the folder of the stator)")
    ap.add_argument("--title", help="your own title line (default: from the stator's title block)")
    ap.add_argument("--air-gap", type=float, help="air gap in mm, added to the title line")
    a = ap.parse_args(argv)
    try:
        if len(a.paths) == 1 and os.path.isdir(a.paths[0]):
            print("wrote", make_svg(a.paths[0], a.out, a.title, a.air_gap))
        elif len(a.paths) == 2:
            print("wrote", render(a.paths[0], a.paths[1], a.out, a.title, a.air_gap))
        else:
            ap.error("give one folder, or the stator file and the rotor file")
    except (OSError, ValueError) as e:
        raise SystemExit(f"cannot draw the picture: {e}")


if __name__ == "__main__":
    main(sys.argv[1:])
