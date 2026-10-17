"""
TX_Wiring.py  -  how the TX layers are wired (TX_WIRING): one layer with the inner tail on the underpass layer
("single"), two layers in series joined by a via at the inner end ("series"), or the same turns on two layers in
parallel, stitched together through vias ("parallel").  Each function writes the copper of one wiring into the TX
builder (`tx`, TX_Builder.py), turn by turn.  Nothing to edit here.
"""

import math

from Generator.Core.Copper import Via
from Generator.Stator.TX import TX_Shapes, TX_Windows


def emit_series(tx):
    """Two layers in series: layer P runs inwards from the terminal (mirror image, sigma = -1), layer Q outwards;
    one via at the inner end joins them."""
    two_pi, T = 2.0 * math.pi, tx.T
    p_layer, q_layer = tx.tx_lay["layers"]
    for layer, sigma, id0 in ((p_layer, -1, 0), (q_layer, +1, T)):
        gos = []
        if layer == tx.tab_layer:
            gos = [(lo, hi) if sigma > 0 else (two_pi - hi, two_pi - lo) for lo, hi in tx.go_windows]
        for n in range(T):
            TX_Windows.emit_turn(tx, n, id0 + n, layer, sigma, *TX_Shapes.turn_span(tx, n), gos, "turn")
            TX_Shapes.emit_step(tx, n, layer, sigma)
        tx.add_poly([tx.pt(0.0, TX_Shapes.outer_tail_start(tx)), tx.tail_end], layer, -1, "tail")
    tx.vias.insert(0, Via(tx.pt(0.0, tx.r0), turn=0))      # joins the two spirals inside


def emit_single_or_parallel(tx):
    """One TX layer (the inner tail on the underpass layer), or the same turns in parallel on a second layer,
    stitched to the first one through vias on each side of every window."""
    T, r0 = tx.T, tx.r0
    tx.tail_inner = tx.tx_lay["tail_layer"]
    # terminal: inner tail and the via joining it to the start of the spiral
    tx.add_poly([tx.pt(0.0, r0), tx.tail_end], tx.tail_inner, -1, "tail")
    if tx.spiral:
        # a little way up the spiral, so that the via sits clear of the inner tail's own corner
        tx.add_via(tx.pt(0.15 * tx.step, r0 + tx.pitch * 0.15 / tx.steps), 0)
    else:
        tx.add_via(tx.pt(0.0, r0), 0)                             # on the trace ends
    for n in range(T):
        TX_Windows.emit_turn(tx, n, n, tx.base, +1, *TX_Shapes.turn_span(tx, n), [] if tx.parallel else tx.go_windows, "turn")
        TX_Shapes.emit_step(tx, n, tx.base, +1)
        if tx.parallel:
            emit_parallel_arcs(tx, n)
    tx.add_poly([tx.pt(0.0, TX_Shapes.outer_tail_start(tx)), tx.tail_end], tx.base, -1, "tail")


def emit_parallel_arcs(tx, n):
    """The parallel copy of turn n on the other TX layer: arcs between the stitched windows, each ending at a via
    that joins it to the turn on the base layer."""
    two_pi, other = 2.0 * math.pi, tx.other
    order = sorted(range(len(tx.st_windows)), key=lambda i: tx.st_windows[i][0])
    for idx, i in enumerate(order):
        j = order[(idx + 1) % len(order)]
        a = tx.win_vias[i][n][1]
        b = tx.win_vias[j][n][0] + (two_pi if idx + 1 == len(order) else 0.0)
        if b - a <= 1e-6:
            continue
        gos = [(lo + sh, hi + sh) for lo, hi in tx.go_windows for sh in (-two_pi, 0.0, two_pi)
               if a < lo + sh and hi + sh < b]
        if not gos:
            pts = TX_Windows.sample(tx, n, a, b, other)
            tx.add_poly(pts, other, n, "arc")
            tx.parallel_len += TX_Windows.plen(pts)
            tx.add_via(pts[0], n)
            tx.add_via(pts[-1], n)
        else:
            tx.parallel_len += TX_Windows.emit_turn(tx, n, n, other, +1, a, b, gos, "arc")
            tx.add_via(tx.pt(a, tx.r_nom(n, a)), n)
            tx.add_via(tx.pt(b, tx.r_nom(n, b)), n)
