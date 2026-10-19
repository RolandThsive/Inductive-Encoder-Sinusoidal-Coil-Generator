"""
Dual_StatorAssembler.py  -  puts the dual stator together from two finished Single Generator stators: set 1 (inner)
and set 2 (outer), each built by the Single Generator's own chain from its own parameter set
(Dual_SetParameters), on one board with one bore and one outline.

    stator1 = build_set(P1, TERMINAL_1_DEG)      the Single Generator's chain: RX -> TX -> assemble -> clearances
    stator2 = build_set(P2, TERMINAL_2_DEG)
    dual = assemble(P, layout, stator1, stator2)  the gap between the sets measured on the copper (Dual_DesignChecks)
    dual.write(path)                              one KiCad file: six nets, both sets' copper, bore and outline

The Single Generator turns every stator so that its TX terminal sits at StatorAssembly.TERMINAL_DEG, a constant of
that module.  The dual generator sets that constant to the set's own angle while the set is built (and while its
summary is printed) and puts it back afterwards; the Single Generator's file is not changed.

The Single Generator's Stator.write makes a file of its own, so the dual stator writes the copper itself from the
stators' public lists (rx_segments, tx_segments, rx_vias, tx_vias), with the same lines Stator.write uses.
Nothing to edit here.
"""

import contextlib
import math

from Generator.Checks import DesignChecks
from Generator.Core import Layers
from Generator.Core.KiCadWriter import KiCadBoard, page_size
from Generator.Stator import StatorAssembly
from Generator.Stator.RX import RX_Builder
from Generator.Stator.TX import TX_Builder

from Dual_Generator.Checks import Dual_DesignChecks


@contextlib.contextmanager
def terminal_at(deg):
    """StatorAssembly.TERMINAL_DEG = deg while the block runs."""
    old = StatorAssembly.TERMINAL_DEG
    StatorAssembly.TERMINAL_DEG = float(deg)
    try:
        yield
    finally:
        StatorAssembly.TERMINAL_DEG = old


def build_set(Pk, terminal_deg):
    """One set, by the Single Generator's own chain, turned so that its TX ends sit at terminal_deg."""
    with terminal_at(terminal_deg):
        rx = RX_Builder.build_rx(Pk)
        tx = TX_Builder.build_tx(rx)
        DesignChecks.check_tx_terminal(tx)
        stator = StatorAssembly.assemble(Pk, rx, tx)
        DesignChecks.check_stator_clearances(stator)
    stator.terminal_deg = float(terminal_deg)
    return stator


def set_summary(stator):
    """The Single Generator's summary of one set, with the set's own terminal angle in its text."""
    with terminal_at(getattr(stator, "terminal_deg", 0.0)):
        return stator.summary()


def assemble(P, layout, stator1, stator2):
    return DualStator(P, layout, stator1, stator2)


class DualStator:
    """The finished dual stator: the two sets, the one bore and outline, and what was measured between them."""

    def __init__(self, P, layout, stator1, stator2):
        self.P, self.layout = P, layout
        self.sets = (stator1, stator2)
        self.cx, self.cy = stator1.cx, stator1.cy
        self.bore, self.outline = float(layout.bore), float(layout.outline)
        self.extent1 = Dual_DesignChecks.copper_extent(stator1)      # (innermost, outermost) copper of set 1
        self.extent2 = Dual_DesignChecks.copper_extent(stator2)
        self.gap = self.extent2[0] - self.extent1[1]                 # free ring between the sets (built copper)
        self.page_mm = page_size(P.BOARD, self.cx, self.cy, self.outline)

    def nets(self):
        out = []
        for st in self.sets:
            out += [st.P.TX_NET, st.P.RX_NET_PHASE_1_3, st.P.RX_NET_PHASE_0_2]
        return out

    # ------------------------------------------------------------- output
    def write(self, path):
        """Write the dual stator to `path` (Dual_RunCoilGenerator.py chooses it: Dual_OutputFolders.py)."""
        B = self.P.BOARD
        if not path:
            raise ValueError("DualStator.write needs the file path; boards are written by Dual_RunCoilGenerator.py")
        title, comments = self.title_block()
        board = KiCadBoard(title=title, comments=comments, page=self.page_mm, thickness=B.PCB_THICKNESS_MM,
                           copper_layers=4)
        for net in self.nets():
            board.net(net)
        for st in self.sets:                       # (the same lines as the Single Generator's Stator.write)
            Pk = st.P
            for s in st.rx_segments:
                board.segment(s.a, s.b, Pk.RX_TRACE_WIDTH_MM, s.layer, s.net)
            for s in st.tx_segments:
                board.segment(s.a, s.b, Pk.TX_TRACE_WIDTH_MM, s.layer, Pk.TX_NET)
            for v in st.rx_vias:
                board.via(v.at, Pk.VIA_DIAMETER_MM, Pk.VIA_DRILL_MM, v.net)
            for v in st.tx_vias:
                board.via(v.at, Pk.VIA_DIAMETER_MM, Pk.VIA_DRILL_MM, Pk.TX_NET)
        board.circle((self.cx, self.cy), self.bore, "Edge.Cuts", B.EDGE_LINE_WIDTH_MM)
        board.circle((self.cx, self.cy), self.outline, "Edge.Cuts", B.EDGE_LINE_WIDTH_MM)
        board.save(path)
        return path

    def title_block(self):
        """(title, comment lines) for the KiCad title block: one line per set, the radii, the generator."""
        w = lambda l: Layers.LAYER_WORDS.get(l, l)
        f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
        s1, s2 = self.sets
        title = f"Dual stator {s1.N}x{s2.N} loops"
        lines = []
        for k, st in ((1, s1), (2, s2)):
            Pk = st.P
            lines.append(f"Set {k}: Loops: {st.N}, RX Band: {f(st.ri)} ... {f(st.ro)} mm, SIN: Net {Pk.RX_NET_PHASE_0_2}, "
                         f"COS: Net {Pk.RX_NET_PHASE_1_3}, Rising: {w(st.rising_layer)}, Falling: {w(st.falling_layer)}, "
                         f"TX: Net {Pk.TX_NET}, {str(Pk.TX_WIRING).strip().capitalize()}, Turns: {int(Pk.TX_TURNS)} "
                         f"{w(st.tx_layer_p)} {int(Pk.TX_TURNS)} {w(st.tx_layer_q)}, Ends at {f(st.terminal_deg)} deg")
        comments = [
            lines[0],                                                                          # Comment1 (bottom)
            lines[1],
            f"Radius-Outer: {f(self.outline)} mm, Radius-Inner: {f(self.bore)} mm, Gap between the sets: "
            f"{f(self.gap)} mm (r = {f(self.extent1[1])} ... {f(self.extent2[0])} mm)",
            f"Width-TX: {f(float(s1.P.TX_TRACE_WIDTH_MM))} / {f(float(s2.P.TX_TRACE_WIDTH_MM))} mm, Width-RX: "
            f"{f(float(s1.P.RX_TRACE_WIDTH_MM))} / {f(float(s2.P.RX_TRACE_WIDTH_MM))} mm, "
            f"Layers: {int(s1.P.PCB_LAYERS)}",                                                     # Comment4
            "Generator: Dual_StatorAssembler.py (each set built by the Single Generator)",
        ]
        return title, comments

    def summary(self):
        f = lambda v: f"{v:.3f}".rstrip("0").rstrip(".")
        lines = [f"Dual stator: set 1 (inner) {self.sets[0].N} loop(s), set 2 (outer) {self.sets[1].N} loop(s); "
                 f"bore r = {f(self.bore)} mm, outline r = {f(self.outline)} mm"]
        lines += ["  " + ln for ln in self.layout.lines()]
        lines.append(f"  on the built copper: set 1 r = {f(self.extent1[0])} ... {f(self.extent1[1])} mm, set 2 r = "
                     f"{f(self.extent2[0])} ... {f(self.extent2[1])} mm, {f(self.gap)} mm free between them")
        for k, st in ((1, self.sets[0]), (2, self.sets[1])):
            lines.append(f"Set {k} ({'inner' if k == 1 else 'outer'}), TX ends at {st.terminal_deg:g} deg, RX pattern "
                         f"zero at {st.rotation_deg:.2f} deg:")
            lines += ["  " + ln for ln in set_summary(st).split("\n")]
        return "\n".join(lines)
