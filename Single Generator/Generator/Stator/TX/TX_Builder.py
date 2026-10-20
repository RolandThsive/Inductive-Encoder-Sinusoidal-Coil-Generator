"""
TX_Builder.py  -  builds the TX coil of the stator: the turns (TX_Shapes.py), their wiring over the layers
(TX_Wiring.py), the windows for the RX fingers (TX_Windows.py) and the terminal via (TX_Terminal.py).

    tx = build_tx(rx)

reads the RX result (centre, RX outside radius, fingers, RX copper) and leaves the TX copper in tx.tx_segments and
tx.tx_vias (Segment / Via records with the turn and the kind of every piece, Core/Copper.py); StatorAssembly.Stator
copies them.  Nothing to
edit here.
"""

import math

from Generator.Core import BoardLayout, Layers
from Generator.Core.Copper import Segment, Via
from Generator.Stator.TX import TX_Shapes, TX_Terminal, TX_Windows, TX_Wiring


def build_tx(rx):
    """The TX coil for these RX coils: a probe built at 0 deg without finger windows shows the terminal's copper,
    TX_Terminal.find_terminal_angle sweeps it around the ring, and the TX is built there."""
    probe = TXBuilder(rx, 0.0, fingers=False).build()
    target = None
    if rx.single_tabs:                                 # RX_TABS = "single": as close to the two fingers as it fits
        a, b = (t["angle_deg"] for t in rx.single_tabs)
        target = a + ((b - a + 180.0) % 360.0 - 180.0) / 2.0
    angle, gap, note = TX_Terminal.find_terminal_angle(rx, probe, target)
    tx = TXBuilder(rx, angle).build()
    tx.terminal_search_gap, tx.terminal_search_note = gap, note
    return tx


class TXBuilder:
    """The TX coil under construction: its geometry (radii, layers, windows) and the copper made so far."""

    def __init__(self, rx, angle_deg, fingers=True):
        """`rx`: the RX result (centre, RX outside radius, fingers, RX copper); `angle_deg`: where the terminal goes
        (azimuth in the RX's frame); fingers=False builds the TX as if the RX had no fingers (no windows for them).
        Everything about the TX itself comes from the parameters."""
        P = self.P = rx.P
        self.angle_deg = float(angle_deg)
        self.cx, self.cy, self.ro = rx.cx, rx.cy, rx.ro
        ring = BoardLayout.tx_ring(P, self.ro)
        self.tx_radii, self.tx_first_radius = ring["radii"], ring["first"]
        self.tx_outer_radius, self.tx_tail_end_radius = ring["outer"], ring["tail_end"]
        self.tx_shape = BoardLayout.tx_shape(P)            # "diagonal" | "arc" | "spiral"
        # (a spiral's last turn reaches one pitch farther out than tx_outer_radius)
        self.tx_steps = TX_Shapes.points_per_turn(
            P, self.tx_outer_radius + (float(P.TX_PITCH_MM) if self.tx_shape == "spiral" else 0.0))
        lay = self.tx_lay = Layers.layer_plan(P)
        self.tx_mode, self.tx_goaround, self.tx_windows_on = lay["mode"], lay["goaround"], lay["windows_on"]
        self.tx_layer_p = self.tx_layer_q = None
        if self.tx_mode == "series":
            self.tx_layer_p, self.tx_layer_q = lay["layers"]   # spiral run inwards (from the terminal) / outwards
        self.tab_segments = rx.tab_segments if fingers else []
        self.tab_layer, self.tab_end_radius = rx.tab_layer, rx.tab_end_radius
        self.rx_segments = rx.rx_segments
        self.tx_segments, self.tx_vias = [], []
        self.terminal_via_shift, self.terminal_via_clearance = 0.0, None
        self.terminal_pieces_added = 0

    def build(self):
        build_placed(self)
        TX_Terminal.place_terminal_via(self)
        return self

    def start(self):
        """Azimuth (deg) of the TX terminal (tail and via) in the RX's frame."""
        return self.angle_deg

    def pt(self, th, r):
        """Point at the local angle th (rad, from the TX start angle) and radius r."""
        return (self.cx + math.cos(th + self.rot) * r, self.cy + math.sin(th + self.rot) * r)


    def r_nom(self, n, th):
        """Nominal radius of turn n at the local angle th: a circle, or a spiral growing one pitch per turn."""
        return self.r0 + self.pitch * (n + th / (2.0 * math.pi)) if self.spiral else self.r0 + n * self.pitch


    def add_poly(self, pts, layer, turn, kind):
        """Append the pieces of a polyline (turn = TX turn id or -1; kind = turn | arc | step | stub | bracket | tail)."""
        for a, b in zip(pts[:-1], pts[1:]):
            if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-9:
                self.segs.append(Segment(a, b, layer, turn=turn, kind=kind))


    def add_via(self, p, turn):
        self.vias.append(Via(p, turn=turn))


def build_placed(tx):
    """The TX copper for every layout (Layers.layer_plan) and shape ("stepped_diagonal", "stepped_arc" or
    "spiral").
      single   : the turns on one layer (TX_LAYER_A), the inner tail on the underpass layer.
      series   : two layers in series (two mirrored spirals joined by a via at the inner end).
      parallel : the full spiral on one TX layer; on the other one the same turns run in parallel as arcs that
                 end at a via on each side of the TX terminal (and, "stitched", of every finger on that layer),
                 where they join the turn of the same radius.
    Go-around (Layers / BoardLayout): around a finger on its own layer every turn of that layer runs out, parallel to
    the finger, to a via just outside the TX ring - the outer turns farther from the finger than the inner
    ones - and a bracket on the underpass layer (series: TX_SERIES_UNDERPASS_LAYER / the other TX layer;
    parallel: the full-spiral layer) carries it around the finger to the matching via on the other side.
    The pieces are written in the order they are made: tails, turns, steps and windows turn by turn."""
    prepare(tx)
    if tx.mode == "series":
        TX_Wiring.emit_series(tx)
    else:
        TX_Wiring.emit_single_or_parallel(tx)
    tx.tx_segments, tx.tx_vias = tx.segs, tx.vias
    tx.tx_parallel_length_mm = tx.parallel_len
    tx.tx_parallel_saving_mm = tx.parallel_saving
    tx.tx_base_layer, tx.tx_other_layer, tx.tx_tail_layer = tx.base, tx.other, tx.tail_inner
    rot = tx.rot
    tx.tx_window_list = [(math.degrees(lo + rot), math.degrees(hi + rot), t, k) for lo, hi, t, k in tx.windows]


def prepare(tx):
    """Everything the emission needs: geometry, windows, the stitching vias and the jogs next to them."""
    lay = tx.tx_lay
    tx.mode = lay["mode"]
    tx.parallel = tx.mode == "parallel"
    g = tx.g = TX_Windows.tx_geometry(tx, check=tx.parallel)
    tx.ga = TX_Windows.go_geometry(tx) if tx.tx_goaround else None
    tx.T, tx.steps, tx.pitch, tx.r0 = g["T"], g["steps"], g["pitch"], g["r0"]
    tx.spiral, tx.step = g["spiral"], g["step"]
    tx.rot = math.radians(tx.start())
    tx.base = lay["base_layer"]
    tx.other = lay["arc_layer"] if tx.parallel else None
    tx.blayer = lay["bracket_layer"]
    tx.windows = TX_Windows.tx_windows(tx, g, tx.ga) if (tx.tx_windows_on or tx.parallel) else []
    tx.st_windows = [(lo, hi, t) for lo, hi, t, k in tx.windows if k == "stitch"]
    tx.go_windows = [(lo, hi) for lo, hi, _t, k in tx.windows if k == "go"]
    # stitched windows: k = 0 (outermost turn) next to the obstacle, the inner turns farther away
    two_pi = 2.0 * math.pi
    tx.win_vias = []                     # per window: {n: (th_in, th_out)}
    for lo, hi, _t in tx.st_windows:
        vv = {}
        for n in range(tx.T):
            k = tx.T - 1 - n
            off = g["d0"] + k * g["stag"]
            vv[n] = (lo - off / tx.r_nom(n, lo % two_pi), hi + off / tx.r_nom(n, hi % two_pi))
        tx.win_vias.append(vv)
    # jogs: next to a stitching via of turn m, turn m+1 bends outwards and turn m-1 inwards
    tx.bumps = {}                        # (turn, layer) -> [(theta, sign)]
    for vv in tx.win_vias:
        for m, (a, b) in vv.items():
            for th in (a, b):
                for n, layer, sgn in ((m + 1, tx.other, +1), (m + 1, tx.base, +1), (m - 1, tx.base, -1)):
                    if 0 <= n < tx.T and g["delta"] > 0:
                        tx.bumps.setdefault((n, layer), []).append((th, sgn))
    tx.plan = TX_Shapes.step_plan(tx)
    tx.arc = TX_Shapes.arc_plan(tx)
    tx.arc_polys = []                    # "stepped_arc": (layer, sigma, n, points) of every arc
    tx.segs, tx.vias = [], []
    tx.parallel_len = 0.0
    tx.parallel_saving = 0.0             # mm of summed copper length that the parallel paths save (TX_Electrics)
    tx.tail_inner = None
    tx.tail_end = tx.pt(0.0, tx.tx_tail_end_radius)

# ------------------------------------------------------------ summary text


def summary(tx):
    P = tx.P
    lay, T = tx.tx_lay, int(P.TX_TURNS)
    shape = str(P.TX_SHAPE).lower()
    if tx.tx_mode == "series":
        txt = (f"  TX (series): {T} turns on {tx.tx_layer_p} + {T} turns on {tx.tx_layer_q}, joined by a via "
               f"at the inner end, {shape} turns")
    elif tx.tx_mode == "single":
        txt = f"  TX (single layer): {T} turns on {lay['base_layer']}, inner tail on {lay['tail_layer']}, {shape} turns"
    else:
        txt = (f"  TX (parallel): {T} turns on {lay['base_layer']} and the same turns in parallel on "
               f"{lay['arc_layer']}, stitched through vias around the TX terminal; inner tail on {lay['arc_layer']}, "
               f"outer tail on {lay['base_layer']}")
    wl = getattr(tx, "tx_window_list", None)
    if wl:
        n_f = len(tx.tab_segments) // 3
        go = [w for w in wl if w[3] == "go"]
        st = [w for w in wl if w[3] == "stitch" and not w[2]]
        if go:
            txt += (f"\n  TX go-around: {len(go)} window(s) around the {n_f} finger(s) on {tx.tab_layer} "
                    f"(neighbouring fingers share one): every turn runs out to a via just outside the TX ring "
                    f"and around the finger on {lay['bracket_layer']}; finger tips at r = {tx.tab_end_radius:.2f} mm")
        if st:
            txt += (f"\n  TX windows: {len(st)} around the {n_f} finger(s) on {tx.tab_layer}, the turns on "
                    f"{tx.tab_layer} stitched to {lay['base_layer']}")
        txt += f"; {len(tx.tx_vias) - 1} TX vias besides the terminal via"
    arc = TX_Shapes.arc_plan(tx)
    if arc is not None:
        txt += (f"\n  TX arcs: {T} around the terminal via (stepped_arc), radius {arc['rho'][0]:.3f} ... "
                f"{arc['rho'][-1]:.3f} mm" + (" (TX_STEPPED_ARC_RADIUS_MM = auto)" if arc["auto"] else "")
                + (f", smallest gap to other TX copper {tx.tx_arc_gap:.3f} mm"
                   if getattr(tx, "tx_arc_gap", None) is not None else "")
                + f"; the outer tail starts at r = {arc['apex']:.3f} mm")
    plan = TX_Shapes.step_plan(tx)
    if plan is not None:
        txt += (f"\n  TX steps: {math.degrees(plan['theta']):g} deg to the turns (TX_STEPPED_ANGLE_DEG), "
                f"{plan['run']:.2f} mm along the turn each, {plan['gap']:.3f} mm between neighbouring steps")
        if plan["stagger"] > 0:
            txt += f", each step {plan['stagger']:.2f} mm before the one inside it"
    if hasattr(tx, "min_tx_self_clearance"):
        gap, via_rx = tx.min_tx_self_clearance, getattr(tx, "min_tx_via_rx_clearance", None)
        parts = [f"smallest gap between different turns {gap:.3f} mm" if gap is not None else
                 f"gap between different turns not measured (no window or stitching via; the nominal pitch gives "
                 f"{float(P.TX_PITCH_MM) - float(P.TX_TRACE_WIDTH_MM):.3f} mm)"]
        if via_rx is not None:
            parts.append(f"TX via to RX copper {via_rx:.3f} mm")
        txt += "\n  TX copper: " + ", ".join(parts)
    return txt
