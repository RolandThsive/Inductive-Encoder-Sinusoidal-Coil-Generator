"""
test_silkscreen.py  -  the lead-cutting silkscreen suggestion (Generator/Stator/LeadCutting_SilkscreenSuggestion.py):
what it draws into the written stator, measured on the file, and its parts on their own (the settings with their
fallbacks, the font, the search for the TX end, the name placer that keeps names off the marks and the vias).
"""

import math
import os
import shutil
import tempfile
import unittest

import numpy as np

import harness as H
import RegressionTools as RT
from Generator.Stator import LeadCutting_SilkscreenSuggestion as LCS

SILK_LAYERS = ("F.SilkS", "B.SilkS")


def silk_items(board, layer):
    return [l for l in board.lines if l["layer"] == layer], [c for c in board.circles if c["layer"] == layer]


class DrawnIntoTheFile(unittest.TestCase):
    def test_both_sides_mirror_each_other(self):
        """With SILKSCREEN_SIDES = "both" every box, dot and tie line is on F.SilkS and on B.SilkS alike; the
        lettering has the same number of strokes on each side (mirrored on the bottom)."""
        for case in ("default", "cosine_r_loops_4", "stepped_arc_tx"):
            with self.subTest(case=case):
                b = H.board(case).stator
                fl, fc = silk_items(b, "F.SilkS")
                bl, bc = silk_items(b, "B.SilkS")
                self.assertEqual(len(fl), len(bl))
                self.assertEqual(len(fc), len(bc))
                self.assertGreater(len(fc), 0)
                top = sorted((c["centre"], round(c["radius"], 4)) for c in fc)
                bottom = sorted((c["centre"], round(c["radius"], 4)) for c in bc)
                self.assertEqual(top, bottom, "the dots sit at the same places on both sides")

    def test_marks_match_the_record(self):
        """The record names each suggestion; the file carries two dots per RX break and one per TX end."""
        res = H.board("default")
        b = res.stator
        self.assertTrue(res.has(r"3 suggestion\(s\) drawn into the stator file") or
                        "3 suggestion(s) drawn into the stator file" in res.record)
        _l, dots = silk_items(b, "F.SilkS")
        self.assertEqual(len(dots), 2 + 2 + 2, "SIN break (2 dots), COS break (2 dots), TX ends (2 dots)")
        for c in dots:
            self.assertEqual(c["fill"], "solid")
            self.assertAlmostEqual(c["radius"], res.silk["SILKSCREEN_DOT_RADIUS_MM"], 6)
            self.assertEqual(c["color"], (255, 255, 255))
        dashed = [l for l in b.lines if l["type"] == "dash" and l["layer"] == "F.SilkS"]
        self.assertEqual(len(dashed), 4 + 4 + 2, "two dashed boxes (4 lines each) and two dashed lines to the TX ends")

    def test_marks_sit_on_the_board_and_off_the_bore(self):
        for case in H.BOARD_CASES:
            with self.subTest(case=case):
                b = H.board(case).stator
                cx, cy = b.centre
                for l in b.lines:
                    for p in (l["start"], l["end"]):
                        r = math.hypot(p[0] - cx, p[1] - cy)
                        self.assertLess(r, b.outer_radius, "silkscreen past the outline")
                        self.assertGreater(r, b.inner_radius, "silkscreen in the bore")
                for c in b.circles:
                    r = math.hypot(c["centre"][0] - cx, c["centre"][1] - cy)
                    self.assertLess(r + c["radius"], b.outer_radius)
                    self.assertGreater(r - c["radius"], b.inner_radius)

    def test_suggested_via_sites_have_room(self):
        """Each dot (a suggested via) keeps MIN_CLEARANCE_MM from every copper of another net than its own coil
        and from every existing via, as the record claims; measured on the file."""
        res = H.board("default")
        b = res.stator
        need = res.params["MIN_CLEARANCE_MM"]
        via_r = res.params["VIA_DIAMETER_MM"] / 2.0
        _l, dots = silk_items(b, "F.SilkS")
        for c in dots:
            p = np.array(c["centre"])
            P = np.repeat(p[None, :], len(b.seg), axis=0)
            d = RT.point_segment_distance(P, b.seg[:, 0:2], b.seg[:, 2:4]) - b.seg[:, 4] / 2.0 - via_r
            # the trace being cut (own net, within a via gap of the dot) does not count
            own = np.zeros(len(b.seg), dtype=bool)
            near = d < need
            if near.any():
                nets = set(b.seg_net[near].tolist())
                self.assertEqual(len(nets), 1, f"a dot at {c['centre']} is within {need} mm of nets {nets}")
                own = b.seg_net == nets.pop()
            self.assertGreaterEqual(float(d[~own].min()), need - 1e-6, f"dot at {c['centre']}")
            if len(b.via):
                dv = np.hypot(b.via[:, 0] - p[0], b.via[:, 1] - p[1]) - b.via[:, 2] / 2.0 - via_r
                self.assertGreaterEqual(float(dv.min()), need - 1e-6, f"dot at {c['centre']} too close to a via")

    def test_top_only_with_dots_on_every_via(self):
        res = H.board("silkscreen_top_dots_on_all")
        b = res.stator
        self.assertEqual(silk_items(b, "B.SilkS"), ([], []))
        _l, dots = silk_items(b, "F.SilkS")
        self.assertEqual(len(dots), 6 + len(b.via), "the suggestion's six dots plus one on every via")
        for c in dots:
            self.assertEqual(c["color"], (255, 204, 0), "SILKSCREEN_COLOR #FFCC00")
        on_vias = {tuple(np.round(v[:2], 4)) for v in b.via}
        dot_at = {tuple(np.round(c["centre"], 4)) for c in dots}
        self.assertTrue(on_vias <= dot_at)
        self.assertIn(f"a dot on each of the {len(b.via)} vias of the board", res.record)

    def test_off_leaves_the_file_as_written(self):
        res = H.board("silkscreen_off")
        b = res.stator
        self.assertEqual((b.lines, b.circles), ([], []))
        self.assertIn("SILKSCREEN_SUGGESTION = False", res.out)
        self.assertNotIn("(gr_line", res.text("Stator.kicad_pcb"))

    def test_names_are_drawn_and_do_not_cover_vias(self):
        """The lettering (strokes of SILKSCREEN_TEXT_STROKE_MM) is there, and no stroke crosses a via."""
        res = H.board("default")
        b = res.stator
        strokes = [l for l in b.lines if l["layer"] == "F.SilkS" and abs(l["width"] - res.silk["SILKSCREEN_TEXT_STROKE_MM"]) < 1e-9]
        self.assertGreater(len(strokes), 50, "lettering strokes")
        for l in strokes:
            for v in b.via:
                d = RT.point_segment_distance(np.array([v[:2]]), np.array([l["start"]]), np.array([l["end"]]))[0]
                self.assertGreater(d, v[2] / 2.0, f"a letter stroke crosses the via at {v[:2]}")
        self.assertFalse(res.has("no free place was found"), "every name found a free place on the default board")

    def test_bottom_lettering_is_mirrored(self):
        res = H.board("default")
        b = res.stator
        w = res.silk["SILKSCREEN_TEXT_STROKE_MM"]
        top = sorted((round(l["start"][0] + l["end"][0], 3), round(l["start"][1] + l["end"][1], 3)) for l in b.lines
                     if l["layer"] == "F.SilkS" and abs(l["width"] - w) < 1e-9)
        bot = sorted((round(l["start"][0] + l["end"][0], 3), round(l["start"][1] + l["end"][1], 3)) for l in b.lines
                     if l["layer"] == "B.SilkS" and abs(l["width"] - w) < 1e-9)
        self.assertEqual(len(top), len(bot))
        self.assertNotEqual(top, bot, "the bottom lettering is mirrored, not a copy")
        self.assertEqual(sorted(y for _x, y in top), sorted(y for _x, y in bot), "mirrored about a vertical line: same y")


class Settings(unittest.TestCase):
    def setUp(self):
        H.restore()

    def tearDown(self):
        H.restore()

    def test_file_values_are_read(self):
        s = LCS.Settings()
        self.assertEqual(s.warnings, [])
        for name, default in LCS.DEFAULTS.items():
            self.assertEqual(getattr(s, name), getattr(H.SILK, name) if not isinstance(default, str) else getattr(H.SILK, name).lower()
                             if name == "SILKSCREEN_SIDES" else getattr(H.SILK, name))
        self.assertEqual(s.rgb, (255, 255, 255))

    def test_bad_values_fall_back_with_a_warning(self):
        bad = {"SILKSCREEN_SIDES": "left", "SILKSCREEN_COLOR": "white", "SILKSCREEN_LABELS": "yes",
               "SILKSCREEN_LINE_WIDTH_MM": -1, "SILKSCREEN_TEXT_SIZE_MM": "big", "SILKSCREEN_BREAK_LAYERS": ["X.Cu"],
               "SILKSCREEN_DOT_RADIUS_MM": True, "SILKSCREEN_SEARCH_SPAN_DEG": float("nan")}
        H.apply({"SILK." + k: v for k, v in bad.items()})
        s = LCS.Settings()
        self.assertEqual(len(s.warnings), len(bad))
        for name in bad:
            self.assertEqual(getattr(s, name), LCS.DEFAULTS[name])
            self.assertTrue(any(name in w and "using" in w for w in s.warnings), name)

    def test_unknown_name_is_reported(self):
        H.apply({"SILK.SILKSCREEN_FOO": 1})
        s = LCS.Settings()
        self.assertEqual(len(s.warnings), 1)
        self.assertIn("SILKSCREEN_FOO", s.warnings[0])
        self.assertIn("ignored", s.warnings[0])

    def test_missing_name_uses_the_default(self):
        H.apply({"SILK.SILKSCREEN_TX_SITE_REACH_MM": H.DELETE})
        s = LCS.Settings()
        self.assertEqual(s.warnings, [])
        self.assertEqual(s.SILKSCREEN_TX_SITE_REACH_MM, LCS.DEFAULTS["SILKSCREEN_TX_SITE_REACH_MM"])

    def test_sides_and_colour_are_normalised(self):
        H.apply({"SILK.SILKSCREEN_SIDES": " Top ", "SILK.SILKSCREEN_COLOR": "#ffcc00"})
        s = LCS.Settings()
        self.assertEqual((s.SILKSCREEN_SIDES, s.SILKSCREEN_COLOR, s.rgb), ("top", "#FFCC00", (255, 204, 0)))


class Font(unittest.TestCase):
    def test_font_loads_from_resources(self):
        font, why = LCS.load_font()
        self.assertIsNone(why)
        self.assertTrue(os.path.isfile(LCS.FONT_FILE))
        self.assertEqual(os.path.basename(os.path.dirname(LCS.FONT_FILE)), "resources")
        self.assertTrue(hasattr(font, "layout") and hasattr(font, "width"))

    def test_width_and_layout(self):
        font, _ = LCS.load_font()
        self.assertEqual(font.width("", 1.0), 0.0)
        self.assertGreater(font.width("AB", 1.0), font.width("A", 1.0))
        self.assertAlmostEqual(font.width("AB", 2.0), 2 * font.width("AB", 1.0))
        strokes = font.layout("HH", 10.0, 20.0, 0.5)
        self.assertGreater(len(strokes), 4)
        xs = [p[0] for a, b in strokes for p in (a, b)]
        ys = [p[1] for a, b in strokes for p in (a, b)]
        self.assertAlmostEqual(min(xs), 10.0, 6, "starts at x")
        self.assertAlmostEqual(max(xs) - min(xs), font.width("HH", 0.5), 6, "H fills its cell: the extent is the width")
        narrow = font.layout("SIN_1", 10.0, 20.0, 0.5)
        nx = [p[0] for a, b in narrow for p in (a, b)]
        self.assertLessEqual(max(nx) - min(nx), font.width("SIN_1", 0.5) + 1e-9, "the width is never less than the extent")
        self.assertAlmostEqual((min(ys) + max(ys)) / 2.0, 20.0, 6, "vertically centred on y")
        self.assertAlmostEqual(max(ys) - min(ys), 0.5, 6, "a capital is the height")

    def test_mirror_and_anchor(self):
        font, _ = LCS.load_font()
        plain = font.layout("TX1", 0.0, 0.0, 1.0)
        mirrored = font.layout("TX1", 0.0, 0.0, 1.0, mirror=True)
        w = font.width("TX1", 1.0)
        back = sorted((round(w - a[0], 6), round(a[1], 6), round(w - b[0], 6), round(b[1], 6)) for a, b in mirrored)
        self.assertEqual(back, sorted((round(a[0], 6), round(a[1], 6), round(b[0], 6), round(b[1], 6)) for a, b in plain))
        right = font.layout("TXH", 5.0, 0.0, 1.0, anchor="right")
        self.assertAlmostEqual(max(p[0] for a, b in right for p in (a, b)), 5.0, 6)

    def test_lower_case_and_unknown_glyphs(self):
        font, _ = LCS.load_font()
        self.assertEqual(font.layout("abc", 0, 0, 1.0), font.layout("ABC", 0, 0, 1.0), "lower case is drawn as capitals")
        box = font.layout("~", 0, 0, 1.0)
        self.assertEqual(len(box), 4, "an unknown character is a box of four strokes")


class Parts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = H.board("default")
        cls.text = cls.res.text("Stator.kicad_pcb")
        H.restore()
        cls.board = LCS.Board(cls.text, H.P)

    def test_board_reads_the_file(self):
        b = self.board
        self.assertEqual((b.bore, b.outline), (15.0, 27.0))
        self.assertEqual(len(b.seg), len(self.res.stator.seg))
        self.assertEqual(len(b.vias), len(self.res.stator.via))
        self.assertEqual(set(b.net_name.values()), {"", "TX", "1", "2"})

    def test_tx_end_is_the_terminal(self):
        p, layers = LCS.find_tx_end(self.board, self.board.net_id["TX"])
        self.assertEqual(layers, ["F.Cu", "B.Cu"])
        self.assertAlmostEqual(p[1], 100.0, 4)
        self.assertAlmostEqual(math.hypot(p[0] - 100, p[1] - 100), 26.3, 3, "at the end of the tail")

    def test_rx_break_has_room_and_sits_near_the_terminal_angle(self):
        b = self.board
        br = LCS.find_rx_break(b, b.net_id["2"], ["F.Cu", "B.Cu"], 0.0, 30.0, 1.2, 0.25)
        self.assertIsNotNone(br)
        self.assertGreaterEqual(br["room"], b.clear)
        self.assertLessEqual(LCS._dang(br["angle"], 0.0), 30.0)
        none = LCS.find_rx_break(b, b.net_id["2"], ["F.Cu"], 0.0, 0.0001, 1.2, 0.25)
        self.assertIsNone(none, "no spot within a zero span")

    def test_overlap_of_polygons(self):
        A = LCS._rect(0, 0, 2, 1)
        self.assertTrue(LCS._overlap(A, LCS._rect(0.5, 0.2, 2, 1)))
        self.assertFalse(LCS._overlap(A, LCS._rect(3, 0, 1, 1)))
        self.assertFalse(LCS._overlap(A, LCS._rect(0, 2, 10, 1)))
        tilted = LCS._thick((0, 1.2), (1.2, 0), 0.05)              # crosses the corner region of A
        self.assertTrue(LCS._overlap(A, tilted))
        self.assertFalse(LCS._overlap(A, LCS._thick((0, 3), (3, 0), 0.05)))

    def test_placer_keeps_names_apart(self):
        font, _ = LCS.load_font()
        pl = LCS.Placer(self.board, font, 0.5)
        site = np.array([118.0, 100.0])
        want = np.array([0.0, -1.0])
        at1, free1 = pl.place(site, want, "SIN_1", 0.5)
        at2, free2 = pl.place(site, want, "SIN_2", 0.5)
        self.assertTrue(free1 and free2)
        r1, r2 = pl.names
        self.assertFalse(LCS._overlap(r1, r2), "the second name does not cover the first")
        for rect in (r1, r2):
            self.assertFalse(any(LCS._overlap(rect, v) for v in pl.vias), "a name on a via")

    def test_placer_gives_up_cleanly_when_nothing_is_free(self):
        font, _ = LCS.load_font()
        pl = LCS.Placer(self.board, font, 0.5)
        pl.mark(LCS._rect(100, 100, 80, 80))                      # a mark that covers the whole board
        at, free = pl.place(np.array([118.0, 100.0]), np.array([1.0, 0.0]), "TX_1", 0.5)
        self.assertFalse(free)
        self.assertEqual(len(pl.names), 1)

    def test_leader_only_when_the_name_moved_away(self):
        font, _ = LCS.load_font()
        pl = LCS.Placer(self.board, font, 0.5)
        site = (118.0, 100.0)
        self.assertIsNone(pl.leader(site, "A", (118.3, 100.0), 0.5))
        lead = pl.leader(site, "A", (121.0, 100.0), 0.5)
        self.assertIsNotNone(lead)
        self.assertEqual(len(pl.marks), 1, "the tie line itself becomes a mark")

    def test_suggest_twice_adds_twice(self):
        """suggest() is a pure function of the text: run on its own output it draws again (the run script calls
        it once per written file)."""
        H.restore()
        s = LCS.Settings()
        font, _ = LCS.load_font()
        new, r = LCS.suggest(self.text, H.P, s, font)
        self.assertTrue(r.done and r.marks == 3 and r.warnings == [])
        again, r2 = LCS.suggest(new, H.P, s, font)
        self.assertTrue(r2.done)
        self.assertGreater(len(again), len(new))

    def test_add_to_file_handles_bad_files(self):
        H.restore()
        d = tempfile.mkdtemp(dir=H.temp_root())
        try:
            r = LCS.add_to_file(os.path.join(d, "missing.kicad_pcb"), H.P, quiet=True)
            self.assertFalse(r.done)
            self.assertTrue(any("cannot be read" in w for w in r.warnings))
            p = os.path.join(d, "cut.kicad_pcb")
            with open(p, "w") as fh:
                fh.write(self.text.rstrip() + "\n(unfinished")
            r = LCS.add_to_file(p, H.P, quiet=True)
            self.assertFalse(r.done)
            self.assertTrue(any("closing bracket" in w for w in r.warnings))
            p = os.path.join(d, "empty.kicad_pcb")
            with open(p, "w") as fh:
                fh.write("(kicad_pcb (version 20221018) (generator coil_generator)\n)\n")
            r = LCS.add_to_file(p, H.P, quiet=True)
            self.assertFalse(r.done)
            self.assertTrue(any("not in the stator file" in w for w in r.warnings), r.warnings)
        finally:
            shutil.rmtree(d, True)

    def test_record_lines(self):
        r = LCS.Result()
        self.assertIn("nothing was drawn", "\n".join(LCS.record_lines(r)))
        r.done, r.marks = True, 3
        r.warnings.append("w1")
        text = "\n".join(LCS.record_lines(r))
        self.assertIn("3 suggestion(s) drawn", text)
        self.assertIn("WARNING w1", text)


if __name__ == "__main__":
    unittest.main()
