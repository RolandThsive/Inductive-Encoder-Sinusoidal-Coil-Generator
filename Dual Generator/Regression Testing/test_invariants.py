"""
test_invariants.py  -  what must hold for EVERY dual board the generator writes, measured on the written files
with RegressionTools (not with the generator's own geometry code), for every case of harness.BOARD_CASES:

    the file     KiCad 7 header, balanced brackets, nothing the parser does not know, four copper layers, six
                 nets, the page, the thickness
    the copper   every segment on the layer its set asked for, inside the outline and outside the bore, with the
                 trace width of its set; every via with the via size and drill; copper of different nets at least
                 MIN_CLEARANCE_MM apart unless the run warned about it; the two sets apart by the gap the record
                 names, set 1 inside set 2
    the nets     each RX coil one connected piece whose only free ends sit on its layer-swap vias; each TX one piece
                 whose only free ends are its terminal, set 1 at TERMINAL_1_DEG and set 2 at TERMINAL_2_DEG
    the rotor    ring 1 with set 1's sectors, ring 2 with set 2's, ring 1 inside ring 2 by ROTOR_TRACK_GAP_MM,
                 inside the disc, the disc edges those of the stator
    the record   the layout, every parameter with its value, the two sets as handed to the Single Generator
"""

import math
import re
import unittest

import numpy as np

import harness as H
import RegressionTools as RT

TOL = 1e-6
LAYER = {1: "F.Cu", 2: "In1.Cu", 3: "In2.Cu", 4: "B.Cu"}


def cases():
    return list(H.BOARD_CASES)


def set_nets(res, k):
    """{"TX": id, "SIN": id, "COS": id} of set k in the written stator."""
    b = res.stator
    return {"TX": b.net_id[res.p(f"TX{k}", "TX_NET")], "SIN": b.net_id[res.p(f"RX{k}", "RX_NET_PHASE_0_2")],
            "COS": b.net_id[res.p(f"RX{k}", "RX_NET_PHASE_1_3")]}


def set_extent(res, k):
    """(innermost, outermost) copper radius of set k, from the file."""
    b = res.stator
    cx, cy = b.centre
    ids = set(set_nets(res, k).values())
    m = np.isin(b.seg_net, list(ids))
    s = b.seg[m]
    C = np.repeat(np.array([[cx, cy]]), len(s), axis=0)
    lo = float((RT.point_segment_distance(C, s[:, 0:2], s[:, 2:4]) - s[:, 4] / 2.0).min())
    hi = float((np.maximum(np.hypot(s[:, 0] - cx, s[:, 1] - cy), np.hypot(s[:, 2] - cx, s[:, 3] - cy)) + s[:, 4] / 2.0).max())
    v = b.via[np.isin(b.via_net, list(ids))]
    if len(v):
        r = np.hypot(v[:, 0] - cx, v[:, 1] - cy)
        lo, hi = min(lo, float((r - v[:, 2] / 2).min())), max(hi, float((r + v[:, 2] / 2).max()))
    return lo, hi


class FileFormat(unittest.TestCase):
    def test_header_and_structure(self):
        for case in cases():
            with self.subTest(case=case):
                res = H.board(case)
                for which in ("stator", "rotor"):
                    b = getattr(res, which)
                    self.assertEqual((b.version, b.generator), (20221018, "coil_generator"), which)
                    self.assertTrue(RT.brackets_balanced(b.text), f"{which}: brackets")
                    self.assertEqual(b.unknown, [], f"{which}: lines the parser does not know: {b.unknown[:3]}")
                    self.assertEqual(b.page[0], "User")
                    self.assertGreaterEqual(b.page[1], res.p("BOARD", "PAGE_SIZE_MM")[0])
                    self.assertGreaterEqual(b.page[2], res.p("BOARD", "PAGE_SIZE_MM")[1])
                    self.assertEqual(len(b.edges), 2, f"{which}: bore and outline on Edge.Cuts")
                    self.assertTrue(b.title, f"{which}: a title")
                self.assertEqual(res.stator.copper_layers, ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"], "a dual board has 4 layers")
                self.assertEqual(res.stator.thickness, res.p("BOARD", "PCB_THICKNESS_MM"))
                want = res.p("BOARD", "ROTOR_PCB_THICKNESS_MM") or res.p("BOARD", "PCB_THICKNESS_MM")
                self.assertEqual(res.rotor.thickness, want)

    def test_six_nets(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                names = {res.p(m, n) for m, n in (("TX1", "TX_NET"), ("TX2", "TX_NET"), ("RX1", "RX_NET_PHASE_0_2"),
                                                 ("RX1", "RX_NET_PHASE_1_3"), ("RX2", "RX_NET_PHASE_0_2"), ("RX2", "RX_NET_PHASE_1_3"))}
                self.assertEqual(len(names), 6)
                self.assertEqual(set(b.nets.values()) - {""}, names)
                self.assertEqual(b.nets_used(), set(b.nets) - {0})
                if str(res.p("BOARD", "VIA_TYPE")).lower() != "blind":
                    self.assertEqual(set(b.via_layers), {("F.Cu", "B.Cu")}, "every via goes through the board")

    def test_outline_and_centre(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                cx, cy = res.p("BOARD", "CENTER_X_MM"), res.p("BOARD", "CENTER_Y_MM")
                for ex, ey, _r in b.edges:
                    self.assertAlmostEqual(ex, cx, 6)
                    self.assertAlmostEqual(ey, cy, 6)
                m = re.search(r"bore r = ([\d.]+) mm \(.*\), outline r = ([\d.]+) mm", res.record)
                self.assertIsNotNone(m)
                self.assertAlmostEqual(b.inner_radius, float(m.group(1)), 3)
                self.assertAlmostEqual(b.outer_radius, float(m.group(2)), 3)
                if res.p("BOARD", "INNER_EDGE_RADIUS_MM") is not None:
                    self.assertAlmostEqual(b.inner_radius, res.p("BOARD", "INNER_EDGE_RADIUS_MM"), 6)
                if res.p("BOARD", "OUTER_EDGE_RADIUS_MM") is not None:
                    self.assertAlmostEqual(b.outer_radius, res.p("BOARD", "OUTER_EDGE_RADIUS_MM"), 6)


class Copper(unittest.TestCase):
    def test_copper_inside_the_board(self):
        for case in cases():
            with self.subTest(case=case):
                b = H.board(case).stator
                for layer, (lo, hi) in RT.copper_extent(b).items():
                    self.assertGreater(lo, b.inner_radius, f"{layer}: copper reaches into the bore")
                    self.assertLess(hi, b.outer_radius, f"{layer}: copper reaches past the outline")

    def test_each_net_on_the_layers_its_set_asked_for(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                for k in (1, 2):
                    nets = set_nets(res, k)
                    rx_layers = {LAYER[res.p(f"RX{k}", "RX_LAYER_A")], LAYER[res.p(f"RX{k}", "RX_LAYER_B")]}
                    tx_layers = {LAYER[res.p(f"TX{k}", "TX_LAYER_A")], LAYER[res.p(f"TX{k}", "TX_LAYER_B")]}
                    for coil in ("SIN", "COS"):
                        self.assertEqual(set(b.seg_layer[b.seg_net == nets[coil]]), rx_layers, f"set {k} {coil}")
                    self.assertEqual(set(b.seg_layer[b.seg_net == nets["TX"]]), tx_layers, f"set {k} TX")

    def test_trace_widths_and_via_sizes(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                for k in (1, 2):
                    nets = set_nets(res, k)
                    for coil in ("SIN", "COS"):
                        self.assertEqual(set(np.round(b.seg[b.seg_net == nets[coil], 4], 6).tolist()),
                                         {res.p(f"RX{k}", "RX_TRACE_WIDTH_MM")}, f"set {k} {coil} width")
                    self.assertEqual(set(np.round(b.seg[b.seg_net == nets["TX"], 4], 6).tolist()),
                                     {res.p(f"TX{k}", "TX_TRACE_WIDTH_MM")}, f"set {k} TX width")
                self.assertEqual(set(np.round(b.via[:, 2], 6).tolist()), {res.p("BOARD", "VIA_DIAMETER_MM")})
                self.assertEqual(set(np.round(b.via[:, 3], 6).tolist()), {res.p("BOARD", "VIA_DRILL_MM")})

    def test_clearance_between_nets(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                need = res.p("BOARD", "MIN_CLEARANCE_MM")
                d, where = RT.min_clearance(b, max_interest=need + 0.5)
                if d < need - TOL:
                    self.assertTrue(res.has(r"WARNING.*(clearance|from other copper)"),
                                    f"{d:.4f} mm between {where}, below {need} mm, and the run did not warn")

    def test_set_1_inside_set_2_with_the_recorded_gap(self):
        for case in cases():
            with self.subTest(case=case):
                res = H.board(case)
                lo1, hi1 = set_extent(res, 1)
                lo2, hi2 = set_extent(res, 2)
                self.assertLess(hi1, lo2, "set 1's copper reaches into set 2")
                gap = lo2 - hi1
                m = re.search(r"gap between the sets on the built copper: set 1 reaches r = ([\d.]+) mm, set 2 starts at "
                              r"r = ([\d.]+) mm, ([\d.]+) mm free", res.out)
                self.assertIsNotNone(m, "the run reports the gap it measured")
                self.assertAlmostEqual(hi1, float(m.group(1)), 3)
                self.assertAlmostEqual(lo2, float(m.group(2)), 3)
                self.assertAlmostEqual(gap, float(m.group(3)), 3)
                self.assertGreaterEqual(gap, res.p("BOARD", "MIN_CLEARANCE_MM") - 1e-3)
                if res.p("BOARD", "TRACK_GAP_MM") is not None:
                    self.assertGreaterEqual(gap, res.p("BOARD", "TRACK_GAP_MM") - res.p("BOARD", "LAYOUT_TOLERANCE_MM") - 1e-3)

    def test_no_zero_length_segments(self):
        for case in cases():
            with self.subTest(case=case):
                s = H.board(case).stator.seg
                L = np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1])
                self.assertGreater(float(L.min()), 1e-6)


class Nets(unittest.TestCase):
    def test_rx_coils_are_closed_through_their_vias(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                for k in (1, 2):
                    nets = set_nets(res, k)
                    for coil in ("SIN", "COS"):
                        c = RT.connectivity(b, nets[coil])
                        self.assertEqual(c["components"], 1, f"set {k} {coil} is in {c['components']} pieces")
                        self.assertEqual(c["loose_ends"], [], f"set {k} {coil}: free ends not on a via")
                        self.assertEqual(len(c["free_ends"]), 2 * c["vias"])
                    a, c2 = RT.connectivity(b, nets["SIN"]), RT.connectivity(b, nets["COS"])
                    self.assertEqual((a["segments"], a["vias"]), (c2["segments"], c2["vias"]), f"set {k}: sine and cosine alike")

    def test_tx_terminals_at_their_angles(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                cx, cy = res.p("BOARD", "CENTER_X_MM"), res.p("BOARD", "CENTER_Y_MM")
                for k in (1, 2):
                    c = RT.connectivity(b, set_nets(res, k)["TX"])
                    self.assertEqual(c["components"], 1, f"TX{k} is in pieces")
                    spots = {(round(x, 4), round(y, 4)) for x, y, _l in c["loose_ends"]}
                    self.assertEqual(len(spots), 1, f"TX{k} free ends at {sorted(spots)}")
                    (x, y), = spots
                    want = res.p("BOARD", f"TERMINAL_{k}_DEG")
                    angle = math.degrees(math.atan2(y - cy, x - cx)) % 360.0      # the generator's convention
                    self.assertAlmostEqual(angle, want % 360.0, 2, f"TX{k} terminal at {angle:.3f} deg, wanted {want}")
                    self.assertEqual(len(c["loose_ends"]), 2, "one end on each TX layer")

    def test_rx_pattern_centred(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                cx, cy = res.p("BOARD", "CENTER_X_MM"), res.p("BOARD", "CENTER_Y_MM")
                for k in (1, 2):
                    for coil, nid in set_nets(res, k).items():
                        if coil == "TX":
                            continue
                        s = b.seg[b.seg_net == nid]
                        L = np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1])
                        mx = float(np.sum((s[:, 0] + s[:, 2]) / 2 * L) / L.sum())
                        my = float(np.sum((s[:, 1] + s[:, 3]) / 2 * L) / L.sum())
                        self.assertLess(math.hypot(mx - cx, my - cy), 0.25, f"set {k} {coil} centroid off")


class Vias(unittest.TestCase):
    """VIA_TYPE (Dual_Board_Parameters.py, both sets).  A through via is written with F.Cu and B.Cu; with "blind" every
    via carries KiCad's blind token and the two layers that carry its net's copper there (top-most first), except a via
    between Top and Bottom, which stays a through via."""

    def test_via_layers_follow_the_via_type(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                blind = str(res.p("BOARD", "VIA_TYPE")).lower() == "blind"
                self.assertGreater(len(b.via), 0)
                if not blind:
                    self.assertFalse(b.via_blind.any(), "a blind via on a board of through vias")
                    self.assertEqual(set(b.via_layers), {("F.Cu", "B.Cu")})
                    continue
                radius = res.p("BOARD", "VIA_DIAMETER_MM") / 2.0
                n_blind = 0
                for i in range(len(b.via)):
                    pair, centre = b.via_layers[i], b.via[i, :2]
                    self.assertLess(RT.LAYER_INDEX[pair[0]], RT.LAYER_INDEX[pair[1]], f"via {i}: {pair} not top-most first")
                    m = b.seg_net == b.via_net[i]
                    d = RT.point_segment_distance(np.repeat(centre[None, :], int(m.sum()), axis=0), b.seg[m, 0:2], b.seg[m, 2:4])
                    touching = {b.seg_layer[j] for j, k in zip(np.flatnonzero(m), d <= radius + 1e-3) if k}
                    self.assertEqual(set(pair), touching, f"via {i} at {centre.tolist()}: written as {pair}, the copper of "
                                                          f"its net there is on {sorted(touching)}")
                    if set(pair) == {"F.Cu", "B.Cu"}:
                        self.assertFalse(b.via_blind[i], f"via {i}: Top + Bottom is a through via")
                    else:
                        self.assertTrue(b.via_blind[i], f"via {i}: {pair} must carry the blind token")
                        n_blind += 1
                self.assertEqual(n_blind, int(b.via_blind.sum()))
                self.assertGreater(n_blind, 0, "a blind board with no blind via")


class Rotor(unittest.TestCase):
    def _rings(self, res):
        """Sectors of ring 1 and ring 2 (by radius: ring 1 lies inside ring 2)."""
        b = res.rotor
        centre = b.centre
        sectors = [(l, p, RT.polygon_radii(p, centre)) for l, p, f in b.polys if l.endswith(".Cu")]
        if len(sectors) < 2:
            return sectors, []
        radii = sorted({round(r[1], 3) for _l, _p, r in sectors})
        split = (radii[0] + radii[-1]) / 2.0 if len(radii) > 1 else radii[0] + 1
        return [s for s in sectors if s[2][1] <= split], [s for s in sectors if s[2][1] > split]

    def test_ring_sectors(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).rotor
                custom = str(res.p("BOARD", "ROTOR_MODE")).lower() == "custom"
                r1, r2 = self._rings(res)
                for k, ring in ((1, r1), (2, r2)):
                    n = res.p(f"ROTOR{k}", "ROTOR_CUSTOM_SECTORS") if custom else res.p(f"RX{k}", "LOOPS")
                    layers = res.p(f"ROTOR{k}", "ROTOR_CUSTOM_COPPER_LAYERS" if custom else "ROTOR_AUTO_COPPER_LAYERS")
                    duty = res.p(f"ROTOR{k}", "ROTOR_CUSTOM_DUTY" if custom else "ROTOR_AUTO_DUTY")
                    self.assertEqual(len(ring), n * len(layers), f"ring {k}: {len(ring)} sectors")
                    for l, p, (lo, hi) in ring:
                        self.assertIn(l, layers)
                        self.assertAlmostEqual(RT.polygon_angular_span(p, b.centre), 360.0 / n * duty, 2)
                        self.assertGreater(lo, b.inner_radius)
                        self.assertLess(hi, b.outer_radius)
                hi1 = max(r[1] for _l, _p, r in r1)
                lo2 = min(r[0] for _l, _p, r in r2)
                self.assertLess(hi1, lo2, "ring 1 reaches into ring 2")
                m = re.search(r"ring 1 ends at r = ([\d.]+) mm, ring 2 starts at r = ([\d.]+) mm, ([\d.]+) mm bare", res.out)
                self.assertIsNotNone(m)
                self.assertAlmostEqual(hi1, float(m.group(1)), 2)
                self.assertAlmostEqual(lo2, float(m.group(2)), 2)
                self.assertGreaterEqual(lo2 - hi1, res.p("BOARD", "ROTOR_TRACK_GAP_MM") - 1e-3)

    def test_disc_edges_and_no_tracks(self):
        for case in cases():
            with self.subTest(case=case):
                res = H.board(case)
                custom = str(res.p("BOARD", "ROTOR_MODE")).lower() == "custom"
                if custom:
                    self.assertAlmostEqual(res.rotor.outer_radius, res.p("BOARD", "ROTOR_CUSTOM_OUTLINE_RADIUS_MM"), 6)
                    self.assertAlmostEqual(res.rotor.inner_radius, res.p("BOARD", "ROTOR_CUSTOM_BORE_RADIUS_MM"), 6)
                else:
                    self.assertAlmostEqual(res.rotor.outer_radius, res.stator.outer_radius, 6)
                    self.assertAlmostEqual(res.rotor.inner_radius, res.stator.inner_radius, 6)
                self.assertEqual(res.rotor.centre, res.stator.centre)
                self.assertEqual((len(res.rotor.seg), len(res.rotor.via)), (0, 0))
                e = res.p("BOARD", "ROTOR_SOLDER_MASK_EXPANSION_MM")
                masks = [l for l, _p, _f in res.rotor.polys if l.endswith(".Mask")]
                self.assertEqual(bool(masks), e is not None and float(e) >= 0)


class Record(unittest.TestCase):
    SECTIONS = ("DUAL COIL GENERATION RECORD", "LAYOUT (what the generator computed)", "STATOR", "ROTOR",
                "SET 1: ELECTRICAL ESTIMATE", "SET 2: ELECTRICAL ESTIMATE", "PARAMETER VALUES USED",
                "THE TWO SETS AS HANDED TO THE SINGLE GENERATOR (its names)", "PARAMETER FILES (verbatim copies)",
                "LEAD CUTTING SILKSCREEN SUGGESTION")
    FILES = ("Dual_Board_Parameters.py", "Dual_RX1_Parameters.py", "Dual_RX2_Parameters.py", "Dual_TX1_Parameters.py",
             "Dual_TX2_Parameters.py", "Dual_Rotor1_Parameters.py", "Dual_Rotor2_Parameters.py", "Dual_IC1_Parameters.py",
             "Dual_IC2_Parameters.py", "Dual_Fixed_Parameters.py")

    def test_sections_values_and_copies(self):
        for case in cases():
            with self.subTest(case=case):
                res = H.board(case)
                rec = res.record
                for s in self.SECTIONS:
                    self.assertIn(s, rec, s)
                for f in self.FILES:
                    self.assertIn(f"########## {f} ", rec, f)
                self.assertIn("files       Stator.kicad_pcb, Rotor.kicad_pcb", rec)
                for name, value in H.BOARD_CASES[case].items():
                    module, attr = name.split(".")
                    if module == "SILK" or value is H.DELETE:
                        continue
                    self.assertTrue(re.search(rf"^  {re.escape(attr)}\s+= {re.escape(repr(value))}", rec, re.M),
                                    f"{name} = {value!r} is not in the record as used")
                self.assertTrue(re.search(r"^\[set 1\]\n(  .*\n)*  LOOPS\s+= " + str(res.p("RX1", "LOOPS")), rec, re.M))
                self.assertTrue(re.search(r"^\[set 2\]\n(  .*\n)*  LOOPS\s+= " + str(res.p("RX2", "LOOPS")), rec, re.M))
                self.assertEqual(rec.count("\r"), 0)
                if res.silk_on():
                    self.assertIn("########## Dual_SilkScreenSuggestion_Parameters.py ", rec)
                    self.assertTrue(re.search(r"\d+ suggestion\(s\) drawn into the stator file", rec))
                else:
                    self.assertIn("nothing was drawn", rec)


class Determinism(unittest.TestCase):
    def test_same_input_same_files(self):
        a = H.board("default")
        b = H.write({}, subdir="again")
        self.assertEqual(b.rc, 0)
        self.assertEqual(a.text("Stator.kicad_pcb"), b.text("Stator.kicad_pcb"))
        self.assertEqual(a.text("Rotor.kicad_pcb"), b.text("Rotor.kicad_pcb"))
        self.assertEqual(a.normalised_record, b.normalised_record)

    def test_second_run_gets_a_new_folder(self):
        a = H.write(H.MODE1_BASE, subdir="twice")
        b = H.write(dict(H.MODE1_BASE, **{"BOARD.OUTPUT_DIR": a.out_dir}), subdir="twice")
        self.assertEqual((a.rc, b.rc), (0, 0))
        self.assertEqual(b.made, [a.made[0], a.made[0] + "__1"])

    def test_stator_only_and_rotor_only(self):
        import os
        s = H.write(H.MODE1_BASE, args=["--stator", "--no-color"], subdir="stator_only")
        r = H.write(H.MODE1_BASE, args=["--rotor", "--no-color"], subdir="rotor_only")
        self.assertEqual((s.rc, r.rc), (0, 0))
        self.assertEqual(sorted(os.listdir(s.folder)), ["Parameters.txt", "Stator.kicad_pcb"])
        self.assertEqual(sorted(os.listdir(r.folder)), ["Parameters.txt", "Rotor.kicad_pcb"])
        full = H.board("mode1_fitted_bands")
        self.assertEqual(s.text("Stator.kicad_pcb"), full.text("Stator.kicad_pcb"))
        self.assertEqual(r.text("Rotor.kicad_pcb"), full.text("Rotor.kicad_pcb"))
        self.assertTrue(s.has(r"SUCCESS: 1 board file\(s\)"))


if __name__ == "__main__":
    unittest.main()
