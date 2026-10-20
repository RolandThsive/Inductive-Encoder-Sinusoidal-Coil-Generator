"""
StatorAssembly.py  -  puts the stator together: the RX coils (RX_Builder.py) and the TX coil (TX_Builder.py) become
one board, with its edges, its title block and its KiCad file.

    rx = RX_Builder.build_rx(P)          RX coils, fingers
    tx = TX_Builder.build_tx(rx)         TX coil, its terminal where it fits best
    stator = assemble(P, rx, tx)         the board, turned so that the terminal sits at 0 deg (the right)

THE LINKS BETWEEN RX AND TX, ALL OF THEM:
  * THE RX READS ONLY THE PARAMETERS.  NOTHING OF THE TX.
  * THE TX IS BUILT AFTER THE RX AND READS FROM IT THE CENTRE, THE RX OUTSIDE RADIUS, THE FINGERS (FOR ITS
    WINDOWS) AND THE RX COPPER (TO FIND THE PLACE FOR ITS TERMINAL, AND FOR THE CLEARANCE CHECKS).
  * NOTHING GOES BACKWARDS, AND NOTHING IS ESTIMATED.

Nothing to edit here.
"""

import math

from Generator.Core import BoardLayout, Layers
from Generator.Core.BoardLayout import outer_edge_room
from Generator.Core.Geometry import chord_tolerance
from Generator.Core.KiCadWriter import KiCadBoard, page_size
from Generator.Stator.TX import TX_Builder


TERMINAL_DEG = 0.0             # where the TX terminal ends up on the finished board (the right, horizontal axis)


def assemble(P, rx, tx):
    """The stator: RX and TX put together and turned so that the TX terminal sits at TERMINAL_DEG."""
    return Stator(P, rx, tx)


def rotate_copper(segments, vias, cx, cy, deg):
    """The same records turned by deg about (cx, cy)."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))

    def rot(p):
        x, y = p[0] - cx, p[1] - cy
        return (cx + c * x - s * y, cy + s * x + c * y)
    return ([sg._replace(a=rot(sg.a), b=rot(sg.b)) for sg in segments], [v._replace(at=rot(v.at)) for v in vias])


class Stator:
    """The finished stator: everything of the RX builder and the TX builder on one object, plus the board edges."""

    TX_RESULTS = ("tx_segments", "tx_vias", "tx_parallel_length_mm", "tx_parallel_saving_mm", "tx_base_layer",
                  "tx_other_layer", "tx_tail_layer", "tx_window_list", "terminal_via_shift", "terminal_via_clearance",
                  "tx_arc_gap", "tx_arc_gap_pieces", "angle_deg", "tx_steps", "tx_first_radius", "tx_radii",
                  "tx_outer_radius", "tx_tail_end_radius", "tx_shape", "tx_mode", "tx_lay", "tx_goaround",
                  "tx_windows_on", "tx_layer_p", "tx_layer_q")

    def __init__(self, P, rx, tx):
        self.P, self.rx, self.tx = P, rx, tx
        self.__dict__.update({k: v for k, v in rx.__dict__.items() if k != "P"})
        for name in self.TX_RESULTS:
            if hasattr(tx, name):
                setattr(self, name, getattr(tx, name))
        # the whole board is turned so that the TX terminal ends up at TERMINAL_DEG
        self.rotation_deg = (TERMINAL_DEG - tx.angle_deg) % 360.0
        self.rx_segments, self.rx_vias = rotate_copper(rx.rx_segments, rx.rx_vias, self.cx, self.cy, self.rotation_deg)
        self.tx_segments, self.tx_vias = rotate_copper(tx.tx_segments, tx.tx_vias, self.cx, self.cy, self.rotation_deg)
        tabs = {id(s) for s in rx.tab_segments}
        self.tab_segments = [t for s, t in zip(rx.rx_segments, self.rx_segments) if id(s) in tabs]
        self.tx_window_list = [((lo + self.rotation_deg) % 360.0, (hi + self.rotation_deg) % 360.0, t, k)
                               for lo, hi, t, k in tx.tx_window_list]
        for t in self.single_tabs:
            t["angle_deg"] = (t["angle_deg"] + self.rotation_deg) % 360.0
        self.angle_deg = TERMINAL_DEG
        self.tx_inner_edge = BoardLayout.tx_ring(P, self.ro)["inner_edge"]
        edge_formula = self.ro + P.OUTER_EDGE_OFFSET_MM
        if self.band["outer_edge"] is not None:
            self.outer_edge_radius = float(self.band["outer_edge"])
        else:
            self.outer_edge_radius = max(edge_formula,
                                         self.tx_tail_end_radius + P.OUTER_EDGE_TAIL_MARGIN_MM)
            if self.tab_end_radius is not None:
                self.outer_edge_radius = max(self.outer_edge_radius,
                                             self.tab_end_radius + P.RX_TRACE_WIDTH_MM / 2.0
                                             + P.OUTER_EDGE_TAIL_MARGIN_MM)

    def inner_edge_clear(self):
        return self.rx.inner_edge_clear()

    # ------------------------------------------------------------- output
    def write(self, path):
        """Write the stator to `path` (RunCoilGenerator.py chooses it: OutputFolders.py)."""
        P = self.P
        if not path:
            raise ValueError("Stator.write needs the file path; boards are written by RunCoilGenerator.py")
        title, comments = self.title_block()
        self.page_mm = page_size(P, self.cx, self.cy, self.outer_edge_radius)
        board = KiCadBoard(title=title, comments=comments, page=self.page_mm, thickness=P.PCB_THICKNESS_MM,
                           copper_layers=P.PCB_LAYERS)
        for net in (P.TX_NET, P.RX_NET_PHASE_1_3, P.RX_NET_PHASE_0_2):
            board.net(net)
        for s in self.rx_segments:
            board.segment(s.a, s.b, P.RX_TRACE_WIDTH_MM, s.layer, s.net)
        for s in self.tx_segments:
            board.segment(s.a, s.b, P.TX_TRACE_WIDTH_MM, s.layer, P.TX_NET)
        for v in self.rx_vias:
            board.via(v.at, P.VIA_DIAMETER_MM, P.VIA_DRILL_MM, v.net)
        for v in self.tx_vias:
            board.via(v.at, P.VIA_DIAMETER_MM, P.VIA_DRILL_MM, P.TX_NET)
        board.circle((self.cx, self.cy), self.inner_edge_radius, "Edge.Cuts", P.EDGE_LINE_WIDTH_MM)
        board.circle((self.cx, self.cy), self.outer_edge_radius, "Edge.Cuts", P.EDGE_LINE_WIDTH_MM)
        board.save(path)
        return path

    LAYER_WORDS = Layers.LAYER_WORDS

    def title_block(self):
        """(title, comment lines) for the KiCad title block (the frame of the drawing; File > Page Settings), as
        "Keyword: value" pairs.  KiCad's default drawing sheet shows Comment1 ... Comment4 (Comment1 at the
        bottom); the rest are kept in the file."""
        P = self.P
        w = lambda l: self.LAYER_WORDS.get(l, l)
        f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
        loops = f"{self.N} loop" + ("s" if self.N != 1 else "")
        subs = "no sub-coils" if self.n_sub == 1 else f"{self.n_sub} sub-coils"
        title = f"Stator {loops}, {subs}"
        lay = self.tx_lay
        T = int(P.TX_TURNS)
        if self.tx_mode == "series":
            tx = f"TX: Series, Turns: {T} {w(self.tx_layer_p)} {T} {w(self.tx_layer_q)}"
        elif self.tx_mode == "parallel":
            tx = f"TX: Parallel, Turns: {T} {w(lay['layers'][0])} {T} {w(lay['layers'][1])}"
        else:
            tx = f"TX: Single Layer, Turns: {T} {w(lay['base_layer'])}, Tail: {w(lay['tail_layer'])}"
        if self.tx_windows_on:
            tx += ", Style: " + ("Around the Finger" if self.tx_goaround else "Stitched")
        n_f = len(self.tab_segments) // 3
        kind = {"all": "Every Outer Tip", "single": "One per Coil"}.get(str(P.RX_TABS).lower(), "")
        fingers = f"Fingers: {n_f} {w(self.tab_layer)}, Style: {kind}" if n_f else "Fingers: None"
        comments = [
            tx,                                                                              # Comment1 (bottom)
            f"Loops: {self.N}, SIN: Net {P.RX_NET_PHASE_0_2}, Phase 0 (+) / 2 (-), "
            f"COS: Net {P.RX_NET_PHASE_1_3}, Phase 1 (+) / 3 (-)",
            f"RX: Rising: {w(self.rising_layer)}, Falling: {w(self.falling_layer)}, {fingers}",
            f"Radius-Outer: {f(self.outer_edge_radius)} mm, Radius-Inner: {f(self.inner_edge_radius)} mm, "
            f"Width-TX: {f(float(P.TX_TRACE_WIDTH_MM))} mm, Width-RX: {f(float(P.RX_TRACE_WIDTH_MM))} mm",  # Comment4
            f"RX Band: Radius-Inner: {f(self.ri)} mm, Radius-Outer: {f(self.ro)} mm, Sub-Coils: {self.n_sub}"
            + (f", Split: {f(self.split_deg)} el. deg" if self.n_sub > 1 else ""),
            "Generator: StatorAssembly.py",
        ]
        return title, comments

    def summary(self):
        P = self.P
        lines = [
            f"Stator: {self.N} loop(s) -> {self.N} electrical period(s) per turn, "
            f"unique range {360.0 / self.N:g} deg",
            f"  RX band r = {self.ri:g} ... {self.ro:g} mm, profile = {P.RX_PROFILE}, "
            f"{self.S} segments per period (RX chord tolerance {chord_tolerance(P, 'RX'):g} mm); "
            f"TX {self.tx_steps} points per turn",
            f"  PCB layers {P.PCB_LAYERS}: RX rising edges on {self.rising_layer}, falling edges on {self.falling_layer}, "
            f"layer-swap vias at {self.rx.via_deg:.1f} electrical deg (RX_VIA_ELECTRICAL_DEG {P.RX_VIA_ELECTRICAL_DEG:g})",
            (f"  RX sub-coils per coil: {self.n_sub}, split {self.split_deg:g} electrical deg "
             f"(requested {P.RX_SUBCOIL_SPLIT_ELEC_DEG:g}), {len(self.junction)} junctions"
             if self.n_sub > 1 else "  RX sub-coils per coil: 1"),
            TX_Builder.summary(self.tx),
            f"  RX segments {len(self.rx_segments)}, RX vias {len(self.rx_vias)} "
            f"(+{len(self.tx_vias)} TX), TX segments {len(self.tx_segments)}",
            f"  RX bridging fingers: {'none' if not self.tab_segments else str(len(self.tab_segments) // 3) + ' (3 segments each on %s), tip radius %.2f mm' % (self.tab_layer, self.tab_end_radius)}"
            + ("".join(f"\n    {t['net']}: one finger at {t['angle_deg']:.1f} deg, "
                       f"{abs((t['angle_deg'] - self.angle_deg + 180.0) % 360.0 - 180.0):.1f} deg from the TX tail"
                       for t in self.single_tabs) if self.single_tabs else ""),
            f"  TX ring r = {self.tx_first_radius:g} ... {self.tx_radii[-1]:g} mm (tail end "
            f"{self.tx_tail_end_radius:g} mm)"
            + (f"; terminal via {abs(self.terminal_via_shift):g} mm "
               f"{'inside' if self.terminal_via_shift > 0 else 'outside'} the first turn (TX_INSIDE_VIA_DISTANCE_MM), "
               f"{self.terminal_via_clearance:.3f} mm from the other turns"
               if getattr(self, "terminal_via_shift", 0.0) and getattr(self, "terminal_via_clearance", None) is not None
               else (f"; terminal via on the first turn (the centre of the arcs), {self.terminal_via_clearance:.3f} mm "
                     f"from the other turns"
                     if self.tx_shape == "arc" and getattr(self, "terminal_via_clearance", None) is not None else "")),
            f"  board edge: bore r = {self.inner_edge_radius:g} mm, outer r = {self.outer_edge_radius:g} mm",
            f"  TX terminal: found at {self.tx.angle_deg:.2f} deg of the RX pattern ({self.tx.terminal_search_gap:.3f} mm "
            f"from the nearest RX copper); the board is turned by {self.rotation_deg:.2f} deg so that it sits at "
            f"{TERMINAL_DEG:g} deg (the right, horizontal axis); the RX pattern's zero is at {self.rotation_deg:.2f} deg",
        ]
        b = self.band
        if b["mode"] != "radii" or b["inner_from"] != "band" or b["outer_from"] != "band":
            parts = []
            if b["mode"] == "centre":
                parts.append(f"RX band = RX_R_BASE_MM {(b['ri'] + b['ro']) / 2:g} +- RX_A_MM {(b['ro'] - b['ri']) / 2:g}")
            if b["inner_from"] == "edge":
                parts.append(f"the RX inside radius by INNER_EDGE_RADIUS_MM (+ INNER_EDGE_INSET_MM {P.INNER_EDGE_INSET_MM:g})")
            if b["outer_from"] == "edge":
                parts.append(f"the RX outside radius by OUTER_EDGE_RADIUS_MM (- {outer_edge_room(P):g} mm for the TX turns, "
                             f"tail and margins)")
            given = [n for n, how in (("bore", b["inner_from"]), ("outer edge", b["outer_from"])) if how == "both"]
            if given:
                parts.append(f"board {' and '.join(given)} as given (RX band and board edge both set)")
            lines.append("  set from the board edge: " + "; ".join(parts) if b["mode"] == "board" or
                         "edge" in (b["inner_from"], b["outer_from"]) else "  " + "; ".join(parts))
        if self.min_via_clearance is not None:
            lines.append(f"  smallest via-to-copper clearance {self.min_via_clearance:.3f} mm")
        return "\n".join(lines)
