"""
test_invariants.py  -  what must hold for EVERY board the generator writes, measured on the written files with
RegressionTools (not with the generator's own geometry code), for every case of harness.BOARD_CASES:

    the file     KiCad 7 header, balanced brackets, nothing the parser does not know, the page, the layer table,
                 the nets, the thickness
    the copper   every segment on a copper layer of the board, inside the outline and outside the bore, with the
                 trace width of its net; every via with the via size and drill; copper of different nets at least
                 MIN_CLEARANCE_MM apart unless the run warned about it
    the nets     each RX coil one connected piece whose only free ends sit on its layer-swap vias; the TX one piece
                 whose only free ends are the terminal at 0 deg (the right)
    the rotor    one sector per loop on each copper layer, each the right angle wide, inside the disc, mask
                 openings only when asked for, the disc edges those of the stator
    the record   every parameter with its value, the sections, the silkscreen section when it was drawn
"""

import math
import re
import unittest

import numpy as np

import harness as H
import RegressionTools as RT

TOL = 1e-6


def cases():
    return list(H.BOARD_CASES)


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
                    self.assertGreaterEqual(b.page[1], res.params["PAGE_SIZE_MM"][0])
                    self.assertGreaterEqual(b.page[2], res.params["PAGE_SIZE_MM"][1])
                    self.assertEqual(b.nets[0], "", "net 0 is the empty net")
                    self.assertTrue(b.title, f"{which}: a title")
                    self.assertEqual(len(b.edges), 2, f"{which}: bore and outline on Edge.Cuts")
                    self.assertTrue(b.text.endswith(")\n"), f"{which}: the file ends with the closing bracket")

    def test_layer_table_matches_pcb_layers(self):
        for case in cases():
            with self.subTest(case=case):
                res = H.board(case)
                n = res.params["PCB_LAYERS"]
                self.assertEqual(len(res.stator.copper_layers), n)
                self.assertEqual(res.stator.copper_layers, ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"] if n == 4 else ["F.Cu", "B.Cu"])
                self.assertEqual(res.stator.thickness, res.params["PCB_THICKNESS_MM"])
                self.assertEqual(len(res.rotor.copper_layers), 2, "the rotor is a 2-layer board")
                want = res.params.get("ROTOR_PCB_THICKNESS_MM") or res.params["PCB_THICKNESS_MM"]
                self.assertEqual(res.rotor.thickness, want)

    def test_nets_declared_and_used(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                names = {res.params["TX_NET"], res.params["RX_NET_PHASE_0_2"], res.params["RX_NET_PHASE_1_3"]}
                self.assertEqual(set(b.nets.values()) - {""}, names)
                self.assertEqual(b.nets_used(), set(b.nets) - {0}, "every declared net carries copper, no copper on net 0")
                self.assertEqual(set(b.seg_layer), set(b.seg_layer) & set(b.copper_layers), "segments only on copper layers")
                self.assertEqual(set(b.via_layers), {("F.Cu", "B.Cu")}, "every via goes through the board")

    def test_outline(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                cx, cy = res.params["CENTER_X_MM"], res.params["CENTER_Y_MM"]
                for ex, ey, _r in b.edges:
                    self.assertAlmostEqual(ex, cx, 6)
                    self.assertAlmostEqual(ey, cy, 6)
                self.assertLess(b.inner_radius, b.outer_radius)
                if res.params["INNER_EDGE_RADIUS_MM"] is not None:
                    self.assertAlmostEqual(b.inner_radius, res.params["INNER_EDGE_RADIUS_MM"], 6)
                if res.params["OUTER_EDGE_RADIUS_MM"] is not None:
                    self.assertAlmostEqual(b.outer_radius, res.params["OUTER_EDGE_RADIUS_MM"], 6)
                self.assertTrue(re.search(rf"bore r = {b.inner_radius:g} mm, outer r = {b.outer_radius:g} mm", res.record))


class Copper(unittest.TestCase):
    def test_copper_inside_the_board(self):
        for case in cases():
            with self.subTest(case=case):
                b = H.board(case).stator
                for layer, (lo, hi) in RT.copper_extent(b).items():
                    self.assertGreater(lo, b.inner_radius, f"{layer}: copper reaches into the bore")
                    self.assertLess(hi, b.outer_radius, f"{layer}: copper reaches past the outline")

    def test_trace_widths_and_via_sizes(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                tx = b.net_id[res.params["TX_NET"]]
                widths = {n: set(np.round(b.seg[b.seg_net == n, 4], 6).tolist()) for n in b.nets if n}
                self.assertEqual(widths[tx], {res.params["TX_TRACE_WIDTH_MM"]}, "TX width")
                for n in b.nets:
                    if n and n != tx:
                        self.assertEqual(widths[n], {res.params["RX_TRACE_WIDTH_MM"]}, f"RX width of net {b.nets[n]!r}")
                self.assertEqual(set(np.round(b.via[:, 2], 6).tolist()), {res.params["VIA_DIAMETER_MM"]})
                self.assertEqual(set(np.round(b.via[:, 3], 6).tolist()), {res.params["VIA_DRILL_MM"]})

    def test_clearance_between_nets(self):
        """Copper of different nets keeps MIN_CLEARANCE_MM, or the run said so (a WARNING or ERROR about it)."""
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                need = res.params["MIN_CLEARANCE_MM"]
                d, where = RT.min_clearance(b, max_interest=need + 0.5)
                if d < need - TOL:
                    self.assertTrue(res.has(r"WARNING.*(clearance|from other copper)"),
                                    f"{d:.4f} mm between {where}, below {need} mm, and the run did not warn")
                else:
                    self.assertGreaterEqual(d, need - TOL, where)

    def test_no_zero_length_segments(self):
        for case in cases():
            with self.subTest(case=case):
                s = H.board(case).stator.seg
                L = np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1])
                self.assertGreater(float(L.min()), 1e-6, "a segment of zero length")


class Nets(unittest.TestCase):
    def test_rx_coils_are_closed_through_their_vias(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                for name in (res.params["RX_NET_PHASE_0_2"], res.params["RX_NET_PHASE_1_3"]):
                    c = RT.connectivity(b, b.net_id[name])
                    self.assertEqual(c["components"], 1, f"net {name!r} is in {c['components']} pieces")
                    self.assertEqual(c["loose_ends"], [], f"net {name!r}: free ends not on a via: {c['loose_ends'][:3]}")
                    self.assertEqual(len(c["free_ends"]), 2 * c["vias"], f"net {name!r}: two segment ends per via")
                    self.assertGreater(c["vias"], 0)

    def test_tx_is_one_piece_with_its_terminal_at_zero_degrees(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                c = RT.connectivity(b, b.net_id[res.params["TX_NET"]])
                self.assertEqual(c["components"], 1, "the TX is in pieces")
                spots = {(round(x, 4), round(y, 4)) for x, y, _l in c["loose_ends"]}
                self.assertEqual(len(spots), 1, f"the TX has free ends at {sorted(spots)}: only the terminal may be free")
                (x, y), = spots
                cx, cy = res.params["CENTER_X_MM"], res.params["CENTER_Y_MM"]
                self.assertAlmostEqual(y, cy, 4, "the terminal sits on the horizontal axis")
                self.assertGreater(x, cx, "the terminal sits to the right of the centre (0 deg)")
                self.assertEqual(len(c["loose_ends"]), 2, "one end on each of the two terminal layers")
                self.assertEqual(len({l for _x, _y, l in c["loose_ends"]}), 2)

    def test_rx_coils_share_vias_count_and_length(self):
        """The sine and the cosine coil are the same coil turned: the same number of segments, vias and copper."""
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                a, c = (b.net_id[res.params[n]] for n in ("RX_NET_PHASE_0_2", "RX_NET_PHASE_1_3"))
                self.assertEqual(int((b.seg_net == a).sum()), int((b.seg_net == c).sum()))
                self.assertEqual(int((b.via_net == a).sum()), int((b.via_net == c).sum()))
                self.assertAlmostEqual(b.length_of(a), b.length_of(c), 3)

    def test_symmetry_of_the_rx_pattern(self):
        """Each RX coil's copper is spread evenly around the centre: the centroid of its segment midpoints lies at
        the board centre (within a fraction of the trace width), on every layer."""
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).stator
                cx, cy = res.params["CENTER_X_MM"], res.params["CENTER_Y_MM"]
                for name in (res.params["RX_NET_PHASE_0_2"], res.params["RX_NET_PHASE_1_3"]):
                    for layer in set(b.seg_layer[b.seg_net == b.net_id[name]]):
                        s = b.seg[(b.seg_net == b.net_id[name]) & (b.seg_layer == layer)]
                        L = np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1])
                        mx = float(np.sum((s[:, 0] + s[:, 2]) / 2 * L) / L.sum())
                        my = float(np.sum((s[:, 1] + s[:, 3]) / 2 * L) / L.sum())
                        tabs = str(res.params["RX_TABS"]).lower() != "none"
                        limit = 2.0 if tabs else 0.25          # the fingers sit on one side and pull the centroid
                        self.assertLess(math.hypot(mx - cx, my - cy), limit, f"net {name!r} on {layer}: centroid off by "
                                        f"({mx - cx:.3f}, {my - cy:.3f})")


class Rotor(unittest.TestCase):
    def _sectors(self, res):
        b = res.rotor
        return [(l, p) for l, p, f in b.polys if l.endswith(".Cu")]

    def test_sector_count_and_layers(self):
        for case in cases():
            with self.subTest(case=case):
                res = H.board(case)
                custom = str(res.params["ROTOR_MODE"]).lower() == "custom"
                n = res.params["ROTOR_CUSTOM_SECTORS"] if custom else res.params["LOOPS"]
                layers = res.params["ROTOR_CUSTOM_COPPER_LAYERS" if custom else "ROTOR_AUTO_COPPER_LAYERS"]
                sectors = self._sectors(res)
                self.assertEqual(len(sectors), n * len(layers))
                self.assertEqual(sorted({l for l, _p in sectors}), sorted(layers))
                for l, p in sectors:
                    self.assertGreaterEqual(len(p), 4)

    def test_sector_angles_and_radii(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).rotor
                custom = str(res.params["ROTOR_MODE"]).lower() == "custom"
                n = res.params["ROTOR_CUSTOM_SECTORS"] if custom else res.params["LOOPS"]
                duty = res.params["ROTOR_CUSTOM_DUTY" if custom else "ROTOR_AUTO_DUTY"]
                want = 360.0 / n * duty
                centre = b.centre
                for l, p in self._sectors(res):
                    span = RT.polygon_angular_span(p, centre)
                    self.assertAlmostEqual(span, want, 2, f"a sector on {l} spans {span:.3f} deg, wanted {want:.3f}")
                    lo, hi = RT.polygon_radii(p, centre)
                    self.assertGreater(lo, b.inner_radius, "rotor copper in the bore")
                    self.assertLess(hi, b.outer_radius, "rotor copper past the outline")
                    if not custom:
                        clear = res.params["ROTOR_AUTO_EDGE_CLEARANCE_MM"]
                        self.assertGreaterEqual(lo - b.inner_radius, clear - 1e-3)
                        self.assertGreaterEqual(b.outer_radius - hi, clear - 1e-3)
                    self.assertGreater(RT.polygon_area(p), 0.0)
                    if n > 1:
                        continue
                m = re.search(r"copper r = ([\d.]+) \.\.\. ([\d.]+) mm", res.record)
                self.assertIsNotNone(m, "the record names the rotor copper radii")
                lo = min(RT.polygon_radii(p, centre)[0] for _l, p in self._sectors(res))
                hi = max(RT.polygon_radii(p, centre)[1] for _l, p in self._sectors(res))
                self.assertAlmostEqual(lo, float(m.group(1)), 1)
                self.assertAlmostEqual(hi, float(m.group(2)), 1)

    def test_sectors_are_evenly_spaced(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).rotor
                centre = b.centre
                by_layer = {}
                for l, p in self._sectors(res):
                    a = np.degrees(np.arctan2(p[:, 1] - centre[1], p[:, 0] - centre[0]))
                    by_layer.setdefault(l, []).append(float(np.mod(np.degrees(np.arctan2(np.mean(np.sin(np.radians(a))),
                                                                                           np.mean(np.cos(np.radians(a))))), 360)))
                for l, mids in by_layer.items():
                    mids.sort()
                    n = len(mids)
                    if n > 1:
                        gaps = np.diff(mids + [mids[0] + 360.0])
                        self.assertTrue(np.allclose(gaps, 360.0 / n, atol=1e-2), f"{l}: sector middles {gaps}")

    def test_mask_openings_only_when_asked(self):
        for case in cases():
            with self.subTest(case=case):
                res, b = H.board(case), H.board(case).rotor
                e = res.params["ROTOR_SOLDER_MASK_EXPANSION_MM"]
                masks = [(l, p) for l, p, f in b.polys if l.endswith(".Mask")]
                if e is None or float(e) < 0:
                    self.assertEqual(masks, [], "no mask opening wanted")
                else:
                    sectors = self._sectors(res)
                    self.assertEqual(len(masks), len(sectors), "one mask opening per sector")
                    self.assertEqual(sorted(l.split(".")[0] for l, _p in masks), sorted(l.split(".")[0] for l, _p in sectors))
                    for (_l, m), (_k, s) in zip(masks, sectors):
                        lo_m, hi_m = RT.polygon_radii(m, b.centre)
                        lo_s, hi_s = RT.polygon_radii(s, b.centre)
                        self.assertAlmostEqual(hi_m - hi_s, float(e), 3)
                        self.assertAlmostEqual(lo_s - lo_m, float(e), 3)

    def test_rotor_edges_follow_the_stator(self):
        for case in cases():
            with self.subTest(case=case):
                res = H.board(case)
                custom = str(res.params["ROTOR_MODE"]).lower() == "custom"
                if custom:
                    self.assertAlmostEqual(res.rotor.outer_radius, res.params["ROTOR_CUSTOM_OUTLINE_RADIUS_MM"], 6)
                    self.assertAlmostEqual(res.rotor.inner_radius, res.params["ROTOR_CUSTOM_BORE_RADIUS_MM"], 6)
                else:
                    self.assertAlmostEqual(res.rotor.outer_radius, res.stator.outer_radius, 6)
                    self.assertAlmostEqual(res.rotor.inner_radius, res.stator.inner_radius, 6)
                self.assertEqual(res.rotor.centre, res.stator.centre)
                self.assertEqual(len(res.rotor.seg), 0, "a rotor has no tracks")
                self.assertEqual(len(res.rotor.via), 0, "a rotor has no vias")


class Record(unittest.TestCase):
    SECTIONS = ("COIL GENERATION RECORD", "STATOR", "ROTOR", "ELECTRICAL ESTIMATE", "PARAMETER VALUES USED",
                "PARAMETER FILES (verbatim copies)")

    def test_sections_and_values(self):
        for case in cases():
            with self.subTest(case=case):
                res = H.board(case)
                rec = res.record
                for s in self.SECTIONS:
                    self.assertIn(s, rec)
                self.assertIn(f"files       Stator.kicad_pcb, Rotor.kicad_pcb", rec)
                self.assertIn(f"folder      {res.folder}", rec)
                for name, value in H.BOARD_CASES[case].items():
                    if "." in name or value is H.DELETE:
                        continue
                    self.assertTrue(re.search(rf"^  {re.escape(name)}\s+= {re.escape(repr(value))}", rec, re.M),
                                    f"{name} = {value!r} is not in the record as used")
                for f in ("Board_Parameters.py", "RX_Parameters.py", "TX_Parameters.py", "Rotor_Parameters.py", "IC_Parameters.py"):
                    self.assertIn(f"########## {f} ", rec)
                self.assertEqual(rec.count("\r"), 0, "the record is written with LF line ends")

    def test_silkscreen_section(self):
        for case in cases():
            with self.subTest(case=case):
                res = H.board(case)
                on = res.silk["SILKSCREEN_SUGGESTION"]
                self.assertIn("LEAD CUTTING SILKSCREEN SUGGESTION", res.record)
                if on:
                    self.assertTrue(re.search(r"\d+ suggestion\(s\) drawn into the stator file", res.record))
                    self.assertIn("########## SilkScreenSuggestion_Parameters.py ", res.record)
                else:
                    self.assertIn("nothing was drawn", res.record)

    def test_warnings_of_the_run_are_recorded(self):
        for case in cases():
            with self.subTest(case=case):
                res = H.board(case)
                warned = [w for w in res.warnings if not w.startswith("WARNING no spot") and "SILKSCREEN" not in w
                          and "no free place" not in w]
                if warned:
                    self.assertIn("WARNINGS OF THIS RUN", res.record)
                    for w in warned:
                        head = re.sub(r"^WARNING\s+", "", w)[:40]
                        self.assertIn(head, res.record, f"warning not recorded: {w[:80]}")


class Determinism(unittest.TestCase):
    def test_same_input_same_files(self):
        """Two runs with the same values write identical boards (no time stamps, no randomness in the geometry)."""
        a = H.board("default")
        b = H.write({}, subdir="again")
        self.assertEqual(b.rc, 0)
        self.assertEqual(a.text("Stator.kicad_pcb"), b.text("Stator.kicad_pcb"))
        self.assertEqual(a.text("Rotor.kicad_pcb"), b.text("Rotor.kicad_pcb"))
        self.assertEqual(a.normalised_record, b.normalised_record)

    def test_second_run_gets_a_new_folder(self):
        a = H.write({}, subdir="twice")
        b = H.write({"OUTPUT_DIR": a.out_dir}, subdir="twice")
        self.assertEqual((a.rc, b.rc), (0, 0))
        self.assertEqual(b.made, [a.made[0], a.made[0] + "__1"])

    def test_stator_only_and_rotor_only(self):
        s = H.write({}, args=["--stator", "--no-color"], subdir="stator_only")
        r = H.write({}, args=["--rotor", "--no-color"], subdir="rotor_only")
        self.assertEqual((s.rc, r.rc), (0, 0))
        import os
        self.assertEqual(sorted(os.listdir(s.folder)), ["Parameters.txt", "Stator.kicad_pcb"])
        self.assertEqual(sorted(os.listdir(r.folder)), ["Parameters.txt", "Rotor.kicad_pcb"])
        full = H.board("default")
        self.assertEqual(s.text("Stator.kicad_pcb"), full.text("Stator.kicad_pcb"), "--stator writes the same stator")
        self.assertEqual(r.text("Rotor.kicad_pcb"), full.text("Rotor.kicad_pcb"), "--rotor writes the same rotor")
        self.assertIn("files       Stator.kicad_pcb\n", s.record)
        self.assertIn("files       Rotor.kicad_pcb\n", r.record)
        self.assertTrue(s.has(r"SUCCESS: 1 board file\(s\)"))


if __name__ == "__main__":
    unittest.main()
