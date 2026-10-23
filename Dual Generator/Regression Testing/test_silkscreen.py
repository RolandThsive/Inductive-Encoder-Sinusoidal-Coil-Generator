"""
test_silkscreen.py  -  the dual lead-cutting silkscreen suggestion
(Dual_Generator/Stator/Dual_LeadCutting_SilkscreenSuggestion.py): what it draws into the written dual stator,
measured on the file, and its parts on their own.  Two sets: six suggestions (two RX breaks and the TX ends of
each set), names that carry the set number (SIN1_1 ... TX2_2 IN2), the breaks of set 1 near TERMINAL_1_DEG and
of set 2 near TERMINAL_2_DEG.
"""

import math
import os
import unittest

import numpy as np

import harness as H
import RegressionTools as RT
from Dual_Generator.Stator import Dual_LeadCutting_SilkscreenSuggestion as LCS


def silk_items(board, layer):
    return [l for l in board.lines if l["layer"] == layer], [c for c in board.circles if c["layer"] == layer]


class DrawnIntoTheFile(unittest.TestCase):
    def test_six_suggestions_on_both_sides(self):
        res = H.board("default")
        b = res.stator
        self.assertIn("6 suggestion(s) drawn into the stator file", res.record)
        fl, fc = silk_items(b, "F.SilkS")
        bl, bc = silk_items(b, "B.SilkS")
        self.assertEqual((len(fl), len(fc)), (len(bl), len(bc)))
        self.assertEqual(len(fc), 12, "two dots per RX break (4 breaks) and one per TX end (4 ends)")
        self.assertEqual(sorted((c["centre"], round(c["radius"], 4)) for c in fc),
                         sorted((c["centre"], round(c["radius"], 4)) for c in bc))
        dashed = [l for l in fl if l["type"] == "dash"]
        self.assertEqual(len(dashed), 4 * 4 + 2 * 2, "four dashed boxes and two dashed lines per TX end pair")
        self.assertFalse(res.has("no free place was found"), "every name found a free place on the default board")
        self.assertFalse(res.has("no spot on"), "every coil got a break")

    def test_breaks_near_each_sets_terminal(self):
        """Set 1's RX breaks lie within SILKSCREEN_SEARCH_SPAN_DEG of TERMINAL_1_DEG (the left), set 2's of
        TERMINAL_2_DEG (the right): the record names the angles and the dots confirm them."""
        for case in ("default", "terminals_90_270"):
            res = H.board(case)
            span = res.p("SILK", "SILKSCREEN_SEARCH_SPAN_DEG")
            for k in (1, 2):
                want = res.p("BOARD", f"TERMINAL_{k}_DEG")
                for coil in ("SIN", "COS", "TX"):
                    m = None
                    for line in res.record.splitlines():
                        if line.strip().startswith(f"{coil}{k} ("):
                            m = line
                    self.assertIsNotNone(m, f"{coil}{k} in the record of {case}")
                    angle = float(m.split(" deg)")[0].rsplit(", ", 1)[1])
                    if coil == "TX":
                        self.assertAlmostEqual(LCS._dang(angle, want), 0.0, 1, f"the TX{k} ends at the terminal ({case})")
                    else:
                        self.assertLessEqual(LCS._dang(angle, want), span, f"{coil}{k} at {angle} deg, terminal at {want} ({case})")

    def test_names_carry_the_set_number(self):
        res = H.board("default")
        for name in ("SIN1_1", "SIN1_2", "COS1_1", "COS1_2", "TX1_1", "TX1_2", "SIN2_1", "SIN2_2", "COS2_1", "COS2_2", "TX2_1", "TX2_2"):
            self.assertIn(name, res.record)

    def test_marks_on_the_board_and_off_the_bore(self):
        for case in H.BOARD_CASES:
            with self.subTest(case=case):
                b = H.board(case).stator
                cx, cy = b.centre
                for l in b.lines:
                    for p in (l["start"], l["end"]):
                        r = math.hypot(p[0] - cx, p[1] - cy)
                        self.assertLess(r, b.outer_radius)
                        self.assertGreater(r, b.inner_radius)
                for c in b.circles:
                    r = math.hypot(c["centre"][0] - cx, c["centre"][1] - cy)
                    self.assertLess(r + c["radius"], b.outer_radius)
                    self.assertGreater(r - c["radius"], b.inner_radius)

    def test_suggested_via_sites_have_room_on_every_layer(self):
        res = H.board("default")
        b = res.stator
        need = res.p("BOARD", "MIN_CLEARANCE_MM")
        via_r = res.p("BOARD", "VIA_DIAMETER_MM") / 2.0
        _l, dots = silk_items(b, "F.SilkS")
        for c in dots:
            p = np.array(c["centre"])
            P = np.repeat(p[None, :], len(b.seg), axis=0)
            d = RT.point_segment_distance(P, b.seg[:, 0:2], b.seg[:, 2:4]) - b.seg[:, 4] / 2.0 - via_r
            near = d < need
            own = np.zeros(len(b.seg), dtype=bool)
            if near.any():
                nets = set(b.seg_net[near].tolist())
                self.assertEqual(len(nets), 1, f"a dot at {c['centre']} is within {need} mm of nets {nets}")
                own = b.seg_net == nets.pop()
            self.assertGreaterEqual(float(d[~own].min()), need - 1e-6, f"dot at {c['centre']}")
            dv = np.hypot(b.via[:, 0] - p[0], b.via[:, 1] - p[1]) - b.via[:, 2] / 2.0 - via_r
            self.assertGreaterEqual(float(dv.min()), need - 1e-6, f"dot at {c['centre']} too close to a via")

    def test_lettering_keeps_off_the_vias(self):
        res = H.board("default")
        b = res.stator
        w = res.p("SILK", "SILKSCREEN_TEXT_STROKE_MM")
        strokes = [l for l in b.lines if l["layer"] == "F.SilkS" and abs(l["width"] - w) < 1e-9]
        self.assertGreater(len(strokes), 100)
        A = np.array([l["start"] for l in strokes])
        B = np.array([l["end"] for l in strokes])
        for v in b.via:
            P = np.repeat(np.array([v[:2]]), len(A), axis=0)
            d = RT.point_segment_distance(P, A, B)
            self.assertGreater(float(d.min()), v[2] / 2.0, f"a letter stroke crosses the via at {v[:2]}")

    def test_bottom_only_no_labels_dots_on_all_vias(self):
        res = H.board("silkscreen_bottom_no_labels")
        b = res.stator
        self.assertEqual(silk_items(b, "F.SilkS"), ([], []))
        bl, bc = silk_items(b, "B.SilkS")
        self.assertEqual(len(bc), 12 + len(b.via))
        w = res.p("SILK", "SILKSCREEN_TEXT_STROKE_MM")
        self.assertEqual([l for l in bl if abs(l["width"] - w) < 1e-9], [], "no lettering")
        self.assertIn("labels off", res.record)

    def test_off_leaves_the_file_as_written(self):
        res = H.board("silkscreen_off")
        self.assertEqual((res.stator.lines, res.stator.circles), ([], []))
        self.assertNotIn("(gr_line", res.text("Stator.kicad_pcb"))


class SettingsAndFont(unittest.TestCase):
    def setUp(self):
        H.restore()

    def tearDown(self):
        H.restore()

    def test_file_values_are_read(self):
        s = LCS.Settings()
        self.assertEqual(s.warnings, [])
        self.assertEqual(s.SILKSCREEN_BREAK_LAYERS, ["F.Cu", "In1.Cu"], "a dual board breaks the RX on its two RX layers")
        self.assertEqual(s.SILKSCREEN_SIDES, "both")

    def test_bad_values_fall_back_with_a_warning(self):
        bad = {"SILKSCREEN_SIDES": 3, "SILKSCREEN_COLOR": "#FFF", "SILKSCREEN_LABELS": 1, "SILKSCREEN_BOX_MARGIN_MM": 0,
               "SILKSCREEN_BREAK_LAYERS": "F.Cu"}
        H.apply({"SILK." + k: v for k, v in bad.items()})
        s = LCS.Settings()
        self.assertEqual(len(s.warnings), len(bad))
        for name in bad:
            self.assertEqual(getattr(s, name), LCS.DEFAULTS[name])
            self.assertTrue(any(name in w and "Dual_SilkScreenSuggestion_Parameters.py" in w for w in s.warnings), name)

    def test_unknown_and_missing_names(self):
        H.apply({"SILK.SILKSCREEN_FOO": 1, "SILK.SILKSCREEN_DOT_RADIUS_MM": H.DELETE})
        s = LCS.Settings()
        self.assertEqual(len(s.warnings), 1)
        self.assertIn("SILKSCREEN_FOO", s.warnings[0])
        self.assertEqual(s.SILKSCREEN_DOT_RADIUS_MM, LCS.DEFAULTS["SILKSCREEN_DOT_RADIUS_MM"])

    def test_font_is_the_shared_one(self):
        font, why = LCS.load_font()
        self.assertIsNone(why)
        self.assertEqual(os.path.normcase(os.path.abspath(LCS.FONT_FILE)),
                         os.path.normcase(os.path.join(H.RESOURCES, "SilkscreenFont.py")))
        self.assertGreater(len(font.layout("TX2_1 IN2", 0, 0, 0.5)), 20)


class Parts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = H.board("default")
        cls.text = cls.res.text("Stator.kicad_pcb")
        H.restore()
        cls.board = LCS.Board(cls.text, H.P)

    def test_board_reads_the_file(self):
        b = self.board
        self.assertEqual((b.bore, b.outline), (7.25, 26.875))
        self.assertEqual(len(b.seg), len(self.res.stator.seg))
        self.assertEqual(set(b.net_name.values()), {"", "TX_1", "COS_1", "SIN_1", "TX_2", "COS_2", "SIN_2"})

    def test_angle_follows_the_generator(self):
        b = self.board
        self.assertAlmostEqual(b.angle_deg((b.cx + 5.0, b.cy)), 0.0)
        self.assertAlmostEqual(b.angle_deg((b.cx, b.cy + 5.0)), 90.0)
        self.assertAlmostEqual(b.angle_deg((b.cx - 5.0, b.cy)), 180.0)

    def test_tx_ends_of_both_sets(self):
        p1, l1 = LCS.find_tx_end(self.board, self.board.net_id["TX_1"])
        p2, l2 = LCS.find_tx_end(self.board, self.board.net_id["TX_2"])
        self.assertEqual(l1, ["F.Cu", "In2.Cu"])
        self.assertEqual(l2, ["F.Cu", "In2.Cu"])
        self.assertLess(p1[0], 100.0, "set 1's terminal on the left (180 deg)")
        self.assertGreater(p2[0], 100.0, "set 2's terminal on the right (0 deg)")
        self.assertAlmostEqual(p1[1], 100.0, 4)
        self.assertAlmostEqual(p2[1], 100.0, 4)

    def test_rx_break_on_the_inner_rx_layers(self):
        b = self.board
        br = LCS.find_rx_break(b, b.net_id["SIN_2"], ["F.Cu", "In1.Cu"], 0.0, 30.0, 1.2, 0.25)
        self.assertIsNotNone(br)
        self.assertIn(br["layer"], ("F.Cu", "In1.Cu"))
        self.assertGreaterEqual(br["room"], b.clear)

    def test_suggest_is_pure(self):
        s = LCS.Settings()
        font, _ = LCS.load_font()
        new, r = LCS.suggest(self.text, H.P, s, font)
        self.assertTrue(r.done)
        self.assertEqual(r.marks, 6)
        self.assertEqual(r.warnings, [])
        self.assertTrue(new.endswith(")\n"))
        self.assertTrue(RT.brackets_balanced(new))


if __name__ == "__main__":
    unittest.main()
