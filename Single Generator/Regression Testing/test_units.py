"""
test_units.py  -  the small building blocks of the Single Generator on their own: the output folder names, the
KiCad writer, the report and colour classes, the parameter helpers, the geometry helpers.  Fast, no board written.
"""

import io
import contextlib
import os
import tempfile
import types
import unittest

import numpy as np

import harness as H
import RegressionTools as RT
from Generator.Checks import DesignChecks
from Generator.Core import BoardLayout, Geometry, Layers
from Generator.Core.Conflict import Colour, ParameterConflict, Report, conflict_title
from Generator.Core.PCBWriter import KiCadBoard, page_size
from Generator.Run import OutputFolders as OF


class OutputFolderNames(unittest.TestCase):
    def test_numbers_in_names(self):
        self.assertEqual(OF._num(15.0), "15")
        self.assertEqual(OF._num(36.8), "36.8")
        self.assertEqual(OF._num(28.2), "28.2")
        self.assertEqual(OF._num(8), "8")
        self.assertEqual(OF._num(1.23456), "1.235")

    def test_folder_name_pattern(self):
        H.restore()
        stator = types.SimpleNamespace(inner_edge_radius=15.0, outer_edge_radius=27.0)
        self.assertEqual(OF.folder_name(stator, H.P), "Coil_15_27_1_1_3_Single_SteppedDiagonal")
        H.apply({"TX_WIRING": "parallel", "TX_SHAPE": "stepped_arc", "LOOPS": 16, "RX_SUBCOILS": 3, "TX_TURNS": 7})
        try:
            self.assertEqual(OF.folder_name(stator, H.P), "Coil_15_27_16_3_7_Parallel_SteppedArc")
            H.apply({"TX_SHAPE": "spiral", "TX_WIRING": "series"})
            self.assertEqual(OF.folder_name(stator, H.P), "Coil_15_27_16_3_7_Series_Spiral")
            H.apply({"TX_SHAPE": "weird", "TX_WIRING": "odd"})
            self.assertEqual(OF.tx_words(stator, H.P), ("Odd", "Weird"), "bad values still make a name; the checks report them")
        finally:
            H.restore()

    def test_output_dir_relative_and_absolute(self):
        H.restore()
        self.assertEqual(OF.output_dir(H.P), os.path.join(H.PROJECT, "Output"))
        self.assertEqual(OF.project_folder(), H.PROJECT)
        H.apply({"OUTPUT_DIR": tempfile.gettempdir()})
        try:
            self.assertEqual(OF.output_dir(H.P), tempfile.gettempdir())
        finally:
            H.restore()

    def test_create_output_folder_never_reuses(self):
        H.restore()
        d = tempfile.mkdtemp(dir=H.temp_root())
        H.apply({"OUTPUT_DIR": d})
        try:
            stator = types.SimpleNamespace(inner_edge_radius=15.0, outer_edge_radius=27.0)
            a = OF.create_output_folder(stator, H.P)
            b = OF.create_output_folder(stator, H.P)
            c = OF.create_output_folder(stator, H.P)
            self.assertEqual([os.path.basename(x) for x in (a, b, c)],
                             ["Coil_15_27_1_1_3_Single_SteppedDiagonal", "Coil_15_27_1_1_3_Single_SteppedDiagonal__1",
                              "Coil_15_27_1_1_3_Single_SteppedDiagonal__2"])
            OF.remove_if_empty(c)
            self.assertFalse(os.path.isdir(c))
            with open(os.path.join(b, "x.txt"), "w") as fh:
                fh.write("x")
            OF.remove_if_empty(b)
            self.assertTrue(os.path.isdir(b), "a folder with files is never removed")
        finally:
            H.restore()


class Writer(unittest.TestCase):
    def test_number_format(self):
        f = KiCadBoard._f
        self.assertEqual(f(1.0), "1")
        self.assertEqual(f(0.1 + 0.2), "0.3")
        self.assertEqual(f(-0.0), "0")
        self.assertEqual(f(-0.0000001), "0")
        self.assertEqual(f(123.4567891), "123.456789")
        self.assertEqual(f(-15.25), "-15.25")

    def test_quoting(self):
        q = KiCadBoard._q
        self.assertEqual(q('a "b" c\\d\ne'), "a 'b' c/d e")

    def test_nets_and_body(self):
        b = KiCadBoard(title="t", page=(200, 200), thickness=1.6, copper_layers=2, comments=["c1", "c2"])
        self.assertEqual(b.net(""), 0)
        self.assertEqual(b.net("TX"), 1)
        self.assertEqual(b.net("1"), 2)
        self.assertEqual(b.net("TX"), 1, "a net keeps its number")
        b.segment((0, 0), (1, 1), 0.2, "F.Cu", "TX")
        b.via((1, 1), 0.8, 0.4, "1")
        b.circle((0, 0), 5, "Edge.Cuts", 0.05)
        b.polygon([(0, 0), (1, 0), (1, 1)], "F.Cu")
        text = b.text()
        self.assertTrue(text.startswith("(kicad_pcb (version 20221018) (generator coil_generator)"))
        self.assertIn('(paper "User" 200 200)', text)
        self.assertIn('(title_block (title "t") (comment 1 "c1") (comment 2 "c2"))', text)
        self.assertIn('(net 0 "")\n  (net 1 "TX")\n  (net 2 "1")', text)
        self.assertIn('(segment (start 0 0) (end 1 1) (width 0.2) (layer "F.Cu") (net 1))', text)
        self.assertIn('(via (at 1 1) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net 2))', text)
        self.assertIn('(gr_circle (center 0 0) (end 0 5) (layer "Edge.Cuts") (width 0.05) (fill none))', text)
        self.assertIn('(gr_poly (pts (xy 0 0) (xy 1 0) (xy 1 1)) (layer "F.Cu") (width 0) (fill solid))', text)
        self.assertIn('(0 "F.Cu" signal)\n    (31 "B.Cu" signal)', text)
        self.assertNotIn("In1.Cu", text)
        self.assertTrue(text.endswith(")\n"))
        four = KiCadBoard(copper_layers=4).text()
        self.assertIn('(1 "In1.Cu" signal)\n    (2 "In2.Cu" signal)', four)

    def test_blind_vias(self):
        b = KiCadBoard(copper_layers=4)
        b.via((1, 1), 0.4, 0.15, "TX")                                          # through: F.Cu B.Cu, no token
        b.via((2, 2), 0.4, 0.15, "TX", layers=("In1.Cu", "F.Cu"))               # layers given but not blind: the same
        b.via((3, 3), 0.4, 0.15, "TX", layers=("F.Cu", "In1.Cu"), blind=True)
        b.via((4, 4), 0.4, 0.15, "TX", layers=("B.Cu", "F.Cu"), blind=True)    # Top + Bottom: a through via after all
        b.via((5, 5), 0.4, 0.15, "TX", layers=None, blind=True)                 # no pair known: through
        b.via((6, 6), 0.4, 0.15, "TX", layers=("In1.Cu", "In2.Cu"), blind=True)  # buried: the same token
        vias = [l for l in b.text().splitlines() if "(via" in l]
        self.assertEqual(vias, [
            '  (via (at 1 1) (size 0.4) (drill 0.15) (layers "F.Cu" "B.Cu") (net 1))',
            '  (via (at 2 2) (size 0.4) (drill 0.15) (layers "F.Cu" "B.Cu") (net 1))',
            '  (via blind (at 3 3) (size 0.4) (drill 0.15) (layers "F.Cu" "In1.Cu") (net 1))',
            '  (via (at 4 4) (size 0.4) (drill 0.15) (layers "F.Cu" "B.Cu") (net 1))',
            '  (via (at 5 5) (size 0.4) (drill 0.15) (layers "F.Cu" "B.Cu") (net 1))',
            '  (via blind (at 6 6) (size 0.4) (drill 0.15) (layers "In1.Cu" "In2.Cu") (net 1))'])
        board = RT.Board(b.text())                                              # the regression parser reads both forms
        self.assertEqual(board.via_blind.tolist(), [False, False, True, False, False, True])
        self.assertEqual(board.via_layers[2], ("F.Cu", "In1.Cu"))
        self.assertEqual(board.unknown, [])

    def test_save_uses_lf(self):
        b = KiCadBoard()
        p = os.path.join(tempfile.mkdtemp(dir=H.temp_root()), "x.kicad_pcb")
        b.save(p)
        with open(p, "rb") as fh:
            raw = fh.read()
        self.assertNotIn(b"\r", raw)
        self.assertEqual(raw.decode(), b.text())

    def test_page_grows_for_large_boards(self):
        H.restore()
        self.assertEqual(page_size(H.P, 100, 100, 27), (200, 200), "the example board fits the smallest page")
        w, h = page_size(H.P, 100, 100, 85)
        self.assertGreater(w, 200)
        self.assertGreater(h, 200)
        w2, h2 = page_size(H.P, 100, 100, 86)
        self.assertGreaterEqual(w2 * h2, w * h, "a bigger board never gets a smaller page")


class Reports(unittest.TestCase):
    def test_titles(self):
        self.assertEqual(conflict_title(["A"]), "A")
        self.assertEqual(conflict_title(["A", "B"]), "A conflicts with B")
        self.assertEqual(conflict_title(["A", "B", "C"]), "A conflicts with B and C")
        self.assertEqual(conflict_title(["A", "B", "C", "D"]), "A conflicts with B, C and D")

    def test_report_levels_and_text(self):
        rep = Report()
        rep.error("e1")
        rep.warn("w1")
        rep.info("i1")
        rep.conflict(("A", "B"), "why")
        rep.conflict(("A", "B"), "soft", level="warning")
        self.assertEqual(rep.errors, ["e1", "A conflicts with B: why"])
        self.assertEqual(rep.warnings, ["w1", "A conflicts with B: soft"])
        other = Report()
        other.error("e2")
        rep.extend(other)
        self.assertEqual(len(rep.items), 6)
        Colour.setup(False)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rep.print()
        out = buf.getvalue()
        self.assertIn("  ERROR   e1\n", out)
        self.assertIn("  WARNING w1\n", out)
        self.assertIn("  info    i1\n", out)
        self.assertIn("  ERROR   A conflicts with B\n          why\n", out)
        self.assertNotIn("\x1b[", out)

    def test_exceptions_become_items(self):
        rep = Report()
        rep.add_exception(ParameterConflict(("X", "Y"), "no"))
        rep.add_exception(ValueError("plain"))
        self.assertEqual(rep.errors, ["X conflicts with Y: no", "plain"])
        e = ParameterConflict(("X", "Y"), "no")
        self.assertEqual(str(e), "X conflicts with Y: no")

    def test_classify_generator_output(self):
        rep = DesignChecks.classify_generator_output(
            "WARNING: a via sits only 0.150 mm from other copper\nWARNING: copper is only -0.1 mm from copper\nnote\n\n")
        self.assertEqual(len(rep.warnings), 1)
        self.assertEqual(len(rep.errors), 1)
        self.assertIn("would short", rep.errors[0])
        self.assertEqual([i for i in rep.items if i[0] == "info"], [("info", "note", ())])


class ParameterHelpers(unittest.TestCase):
    def setUp(self):
        H.restore()

    def tearDown(self):
        H.restore()

    def test_tx_wiring_and_shape(self):
        self.assertEqual(Layers.tx_wiring(H.P), "single")
        self.assertEqual(BoardLayout.tx_shape(H.P), "diagonal")
        H.apply({"TX_WIRING": " Series ", "TX_SHAPE": "STEPPED_ARC"})
        self.assertEqual(Layers.tx_wiring(H.P), "series")
        self.assertEqual(BoardLayout.tx_shape(H.P), "arc")
        H.apply({"TX_WIRING": "twisted"})
        with self.assertRaises(ValueError):
            Layers.tx_wiring(H.P)
        H.apply({"TX_SHAPE": "square"})
        with self.assertRaises(ValueError):
            BoardLayout.tx_shape(H.P)

    def test_rx_band_from_radii_and_from_centre(self):
        band = BoardLayout.rx_band(H.P)
        self.assertEqual((band["ri"], band["ro"]), (16.2, 21.4))
        H.apply({"INSIDE_RADIUS_MM": None, "OUTSIDE_RADIUS_MM": None, "RX_R_BASE_MM": 18.8, "RX_A_MM": 2.6})
        band = BoardLayout.rx_band(H.P)
        self.assertAlmostEqual(band["ri"], 16.2)
        self.assertAlmostEqual(band["ro"], 21.4)
        self.assertEqual(band["mode"], "centre")

    def test_layer_names(self):
        self.assertEqual(Layers.LAYER_NAMES, {1: "F.Cu", 2: "In1.Cu", 3: "In2.Cu", 4: "B.Cu"})
        self.assertEqual(Layers.rx_layer_names(H.P), ("F.Cu", "B.Cu"))
        H.apply({"PCB_LAYERS": 4, "RX_LAYER_A": 2, "RX_LAYER_B": 3})
        self.assertEqual(Layers.rx_layer_names(H.P), ("In1.Cu", "In2.Cu"))

    def test_via_type_pair_and_kind(self):
        self.assertEqual(Layers.via_type(types.SimpleNamespace()), "through", "a missing line means through")
        self.assertEqual(Layers.via_type(types.SimpleNamespace(VIA_TYPE=" Blind ")), "blind")
        with self.assertRaises(ValueError):
            Layers.via_type(types.SimpleNamespace(VIA_TYPE="buried"))
        self.assertEqual(Layers.via_pair("B.Cu", "F.Cu"), ("F.Cu", "B.Cu"))
        self.assertEqual(Layers.via_pair("In2.Cu", "In1.Cu"), ("In1.Cu", "In2.Cu"))
        self.assertEqual([Layers.via_kind(p) for p in (("F.Cu", "B.Cu"), ("F.Cu", "In1.Cu"), ("In2.Cu", "B.Cu"),
                                                        ("In1.Cu", "In2.Cu"), ("F.Cu", "In2.Cu"), ("In1.Cu", "B.Cu"))],
                         ["through", "blind", "blind", "buried", "skip", "skip"])

    def test_chord_tolerance(self):
        self.assertEqual(Geometry.chord_tolerance(H.P, "RX"), 0.001)
        H.apply({"RX_CHORD_TOLERANCE_MM": 0.01})
        self.assertEqual(Geometry.chord_tolerance(H.P, "RX"), 0.01)


class GeometryHelpers(unittest.TestCase):
    def test_point_segment_distance(self):
        d = Geometry.point_segments_distance(np.array([0.0, 1.0]), np.array([[-1.0, 0.0]]), np.array([[1.0, 0.0]]))
        self.assertAlmostEqual(float(np.min(d)), 1.0)
        d = Geometry.point_segments_distance(np.array([3.0, 0.0]), np.array([[-1.0, 0.0]]), np.array([[1.0, 0.0]]))
        self.assertAlmostEqual(float(np.min(d)), 2.0)

    def test_segment_distance(self):
        self.assertAlmostEqual(Geometry.segment_distance((0, 0), (1, 0), (0, 1), (1, 1)), 1.0)
        self.assertAlmostEqual(Geometry.segment_distance((0, 0), (1, 1), (0, 1), (1, 0)), 0.0, msg="crossing segments touch")
        self.assertAlmostEqual(Geometry.segment_distance((0, 0), (1, 0), (2, 0), (3, 0)), 1.0)

    def test_regression_tools_agree_with_the_generator(self):
        """The suite's own distance code (RegressionTools) agrees with the generator's Geometry on random pairs."""
        import RegressionTools as RT
        rng = np.random.default_rng(1)
        A = rng.uniform(-5, 5, (200, 2))
        B = rng.uniform(-5, 5, (200, 2))
        C = rng.uniform(-5, 5, (200, 2))
        D = rng.uniform(-5, 5, (200, 2))
        ours = RT.segment_segment_distance(A, B, C, D)
        theirs = np.array([Geometry.segment_distance(a, b, c, d) for a, b, c, d in zip(A, B, C, D)])
        self.assertTrue(np.allclose(ours, theirs, atol=1e-9), f"max difference {np.abs(ours - theirs).max()}")
        P = rng.uniform(-5, 5, (200, 2))
        ours = RT.point_segment_distance(P, A, B)
        theirs = np.array([float(np.min(Geometry.point_segments_distance(p, a[None, :], b[None, :]))) for p, a, b in zip(P, A, B)])
        self.assertTrue(np.allclose(ours, theirs, atol=1e-9))

    def test_elliptic_integrals(self):
        K, E = Geometry.ellipk_ellipe(0.0)
        self.assertAlmostEqual(float(K), np.pi / 2, 6)
        self.assertAlmostEqual(float(E), np.pi / 2, 6)
        K, E = Geometry.ellipk_ellipe(0.5)
        self.assertAlmostEqual(float(K), 1.8540746773, 5)
        self.assertAlmostEqual(float(E), 1.3506438810, 5)


class Harness(unittest.TestCase):
    def test_delete_and_restore(self):
        H.apply({"LOOPS": 5, "NEW_NAME": 1, "TX_TURNS": H.DELETE})
        self.assertEqual(H.P.LOOPS, 5)
        self.assertTrue(hasattr(H.P, "NEW_NAME"))
        self.assertFalse(hasattr(H.P, "TX_TURNS"))
        H.restore()
        self.assertEqual(H.P.LOOPS, 1)
        self.assertFalse(hasattr(H.P, "NEW_NAME"))
        self.assertEqual(H.P.TX_TURNS, 3)

    def test_no_pycache_is_written(self):
        """The suite and the generator leave no __pycache__ folders that are not already part of the repository."""
        import subprocess
        try:
            out = subprocess.run(["git", "status", "--porcelain", "--", H.PROJECT, H.RESOURCES], capture_output=True,
                                 text=True, cwd=H.REPO, timeout=30).stdout
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git is not available")
        strays = [l for l in out.splitlines() if "__pycache__" in l or l.endswith(".pyc")]
        self.assertEqual(strays, [])


if __name__ == "__main__":
    unittest.main()
