"""
RX_Builder.py  -  builds the RX coils of the stator: the band and the layers, the radius law (RX_Profiles.py), the
curves with their sub-coils and junction vias (RX_Coils.py), and the fingers (RX_Fingers.py).

    rx = build_rx(P)

leaves the RX copper in rx.rx_segments and rx.rx_vias (Segment / Via records, Core/Copper.py) and
rx.tab_segments (the finger pieces).  The RX reads only the parameters: nothing of the TX.  Nothing to edit here.
"""

import math
import sys

from Generator.Core import BoardLayout, Layers
from Generator.Core.Conflict import ParameterConflict
from Generator.Stator.RX import RX_Coils, RX_Fingers, RX_Profiles


def build_rx(P):
    """The RX coils for these parameters."""
    return RXBuilder(P).build()


class RXBuilder:
    """The RX coils under construction: band, layers, curves, junctions, fingers and the copper made so far."""

    def __init__(self, P):
        self.P = P

    def build(self):
        P = self.P
        self.tx_lay = Layers.layer_plan(P)                 # the finger layer (and the RX layers)
        resolve_layers(self)
        self.N = int(P.LOOPS)
        self.cx, self.cy = float(P.CENTER_X_MM), float(P.CENTER_Y_MM)
        self.band = BoardLayout.rx_band(P)
        self.ri, self.ro, self.inner_edge_radius = self.band["ri"], self.band["ro"], self.band["hole"]
        self.L = 2.0 * math.pi / self.N                       # one loop (rad)
        # the finger legs reach exactly RX_TAB_LENGTH_MM past the band (the checks make sure that clears the TX); the
        # straight middle piece between the legs dips a little inside that radius (RX_Fingers.finger_starts caps it)
        self.tab_end_radius = self.ro + float(P.RX_TAB_LENGTH_MM) if RX_Fingers.fingers_on(self) else None

        RX_Profiles.radius_law(self)
        S0 = RX_Coils.pick_steps(self)
        tries = [S0]
        if P.STEPS_PER_LOOP == "auto" and int(P.RX_SUBCOILS) > 1:
            # The sub-coil split is a whole number of node pairs, and the junctions need enough nodes
            # to fit their stubs: take the smallest resolution >= the automatic one that reproduces the
            # requested split (within 0.3 deg) and lets every junction fit.
            def split_error(S):
                unit = 720.0 / S
                return abs(max(1, round(P.RX_SUBCOIL_SPLIT_ELEC_DEG / unit)) * unit - P.RX_SUBCOIL_SPLIT_ELEC_DEG)
            tries = [S for S in range(S0, 6 * S0 + 1, 8) if split_error(S) <= 0.3] or [S0]
        for attempt, S in enumerate(tries):
            self.S = S
            try:
                RX_Coils.setup_subcoils(self)
                RX_Coils.phase_nodes(self)
                RX_Coils.assign_layers(self)
                break
            except ParameterConflict:                    # the junction vias do not fit at this resolution
                if attempt == len(tries) - 1:
                    raise
        # the tip vias are kept clear of the crossings (RX_Coils.assign_layers): say so when that moved them
        self.via_deg = self._tip * 360.0 / self.S
        if abs(self.via_deg - float(P.RX_VIA_ELECTRICAL_DEG)) > 180.0 / self.S + 1e-9:
            print(f"WARNING: RX_VIA_ELECTRICAL_DEG = {P.RX_VIA_ELECTRICAL_DEG:g} is too close to the crossings for "
                  f"{self.S} segments per period; the vias sit at {self.via_deg:.1f} electrical degrees (at this resolution "
                  f"they can only sit at about {45 + 720.0 / self.S:.1f} ... {135 - 720.0 / self.S:.1f}: raise STEPS_PER_LOOP or "
                  f"use \"auto\")", file=sys.stderr)
        # the fingers: every outer tip, one neighbouring pair of tips (RX_TABS = "single"), or none
        self.single_tabs = []
        tab_starts, self.tab_q = RX_Fingers.finger_starts(self)
        starts_of = {k: tab_starts for k in range(self.ncurves)}
        if RX_Fingers.fingers_single(self):
            starts_of = RX_Fingers.single_pair(self, tab_starts, self.tab_q)
        RX_Coils.emit_copper(self, starts_of, self.tab_q)
        return self

    def inner_edge_clear(self):
        """Distance from the inner-tip vias to the centre hole (mm; negative = they run over its edge)."""
        P = self.P
        return (self.ri - P.VIA_DIAMETER_MM / 2.0) - self.inner_edge_radius


def resolve_layers(rx):
    """Copper layers used by the RX coils (rising / falling edges) and the bridging fingers (Layers.layer_plan)."""
    rx.rising_layer, rx.falling_layer = Layers.rx_layer_names(rx.P)
    rx.tab_layer = rx.tx_lay["tab_layer"]
