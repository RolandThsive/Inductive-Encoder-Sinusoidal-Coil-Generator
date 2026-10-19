"""
RX_Fingers.py  -  the bridging fingers of the RX coils (RX_TABS): at the outer tip of a lobe the trace leaves the
RX band radially on the finger layer, runs across the TX ring to rx.tab_end_radius and returns, so the coil can be
broken out outside the TX turns.  "all" = a finger at every outer tip, "single" = one finger per coil on two
neighbouring tips, "none" = no fingers.  The functions take the RX builder (`rx`, RX_Builder.py).  Nothing to edit here.
"""

import math
import sys

import numpy as np




def fingers_on(rx):
    """Bridging fingers at all: RX_TABS = "all" (every outer tip) or "single" (one per coil)."""
    return str(rx.P.RX_TABS).lower() in ("all", "single")


def fingers_single(rx):
    return str(rx.P.RX_TABS).lower() == "single"

# ------------------------------------------------------------ finger positions



def finger_starts(rx):
    """Where the fingers may start: the set of start nodes (one per outer tip of every lobe, the finger centred on the
    tip) and q, the number of nodes between the two legs of a finger (RX_TAB_WIDTH_MM snapped to the polyline).
    Returns (tab_starts, q); sets rx.tab_q."""
    P, N, S = rx.P, rx.N, rx.S
    tab_starts, q = set(), 0
    if fingers_on(rx):
        tip0 = S // 4
        ds = float(np.hypot(*(rx.nodes[0][tip0 + 1] - rx.nodes[0][tip0])))
        q = max(1, int(math.ceil(P.RX_TAB_WIDTH_MM / ds - 1e-9)))
        qmax = 2 * (S // 8 - 2)                         # about 90 electrical degrees
        why = "the legs may span at most about 90 electrical degrees around the tip"
        # the middle piece of a finger is ONE straight chord between the leg ends at rx.tab_end_radius: it must not
        # dip back into the RX band, where it would cross the other coil's traces on the finger layer (half the
        # angle between the legs at most acos(clear / tab_end_radius))
        clear = rx.ro + float(P.RX_TRACE_WIDTH_MM) + float(P.MIN_CLEARANCE_MM)
        if rx.tab_end_radius > clear:
            q_chord = int(math.floor(2.0 * math.acos(clear / rx.tab_end_radius) / (rx.L / S)))
            if 1 <= q_chord < qmax:
                qmax = q_chord
                why = "the straight middle piece would dip back into the RX band"
        if q > qmax:
            q = qmax
            a = tip0 - q // 2
            legs = float(np.hypot(*(rx.nodes[0][a + q] - rx.nodes[0][a])))       # the real spacing of the legs
            print(f"WARNING: RX_TAB_WIDTH_MM too wide for this loop count and finger length ({why}); using legs "
                  f"{legs:.2f} mm apart", file=sys.stderr)
        a0 = tip0 - q // 2
        tab_starts = {m * S + a0 for m in range(N)}
    rx.tab_q = q
    return tab_starts, q


def outward(rx):
    """outward(p): the point at the finger tip radius (rx.tab_end_radius) on the ray from the centre through p."""
    rend = rx.tab_end_radius

    def _outward(p):
        v = np.asarray(p) - (rx.cx, rx.cy)
        return np.array([rx.cx, rx.cy]) + v / np.hypot(*v) * rend
    return _outward


def single_pair(rx, tab_starts, q):
    """RX_TABS = "single": one finger per coil on two neighbouring outer tips: the sin+ tip of the first loop (phase 0
    of sub-coil 0, start node min(tab_starts)) and the cos+ tip that follows it (phase 1, the same node: phase 1 is
    a quarter loop behind phase 0).  Returns {curve: {start node}} for every curve; records rx.single_tabs."""
    j0 = min(tab_starts)
    starts_of = {k: set() for k in range(rx.ncurves)}
    for k, net in ((0, rx.P.RX_NET_PHASE_0_2), (1, rx.P.RX_NET_PHASE_1_3)):
        starts_of[k] = {j0}
        mid = rx.nodes[k][(j0 + q // 2) % rx.NS]
        rx.single_tabs.append(dict(net=net, curve=k, angle_deg=math.degrees(math.atan2(mid[1] - rx.cy, mid[0] - rx.cx))))
    return starts_of
