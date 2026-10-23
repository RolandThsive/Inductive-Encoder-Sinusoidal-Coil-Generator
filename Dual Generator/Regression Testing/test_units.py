"""
test_units.py  -  the dual generator's own building blocks on their own: the set parameters handed to the Single
Generator, the layout modes, the output folder names, the design checks between the sets, and the guard that the
dual files supply every name the Single Generator's rule table knows.  Fast, no board written.
"""

import os
import re
import tempfile
import types
import unittest

import harness as H
from Generator.Core.Conflict import ParameterConflict
from Generator.Stator import StatorAssembly
from Dual_Generator.Checks import Dual_DesignChecks as DDC
from Dual_Generator.Core import Dual_SetParameters as SP
from Dual_Generator.Core import Dual_TrackLayout as TL
from Dual_Generator.Run import Dual_OutputFolders as OF
from Dual_Generator.Stator import Dual_StatorAssembler as DSA


class SetParameters(unittest.TestCase):
    def setUp(self):
        H.restore()

    def tearDown(self):
        H.restore()

    def test_every_single_name_is_supplied(self):
        """When the Single Generator gains a parameter, the dual files must supply it too: this list is empty."""
        self.assertEqual(SP.names_the_single_wants_but_the_dual_lacks(), [])

    def test_build_takes_each_sets_own_values(self):
        s1, s2 = SP.build(H.P, 1), SP.build(H.P, 2)
        self.assertEqual((s1.LOOPS, s2.LOOPS), (H.P.RX1.LOOPS, H.P.RX2.LOOPS))
        self.assertEqual((s1.TX_NET, s2.TX_NET), ("TX_1", "TX_2"))
        self.assertEqual((s1.RX_NET_PHASE_0_2, s2.RX_NET_PHASE_1_3), ("SIN_1", "COS_2"))
        self.assertEqual(s1.ROTOR_AUTO_COVER_TX, H.P.ROTOR1.ROTOR_AUTO_COVER_TX)
        self.assertEqual(s2.ROTOR_AUTO_COVER_TX, H.P.ROTOR2.ROTOR_AUTO_COVER_TX)
        self.assertEqual(s1.IC_NAME, H.P.IC1.IC_NAME)
        for name, (value, _why) in SP.FIXED_REQUIRED.items():
            self.assertEqual(getattr(s1, name), value, name)
            self.assertEqual(getattr(s2, name), value, name)
        self.assertEqual(s1.VIA_DIAMETER_MM, H.P.BOARD.VIA_DIAMETER_MM, "board names are shared")
        self.assertEqual((s1.VIA_TYPE, s2.VIA_TYPE), (H.P.BOARD.VIA_TYPE, H.P.BOARD.VIA_TYPE), "VIA_TYPE is shared")
        self.assertFalse(hasattr(s1, "DUAL_MODE"), "dual-only names are not handed to the Single Generator")
        self.assertFalse(hasattr(s1, "TRACK_GAP_MM"))

    def test_build_with_band_and_edges(self):
        s = SP.build(H.P, 1, band={"RX_R_BASE_MM": 10.0, "RX_A_MM": 1.5}, edges=(7.0, 30.0))
        self.assertEqual((s.RX_R_BASE_MM, s.RX_A_MM), (10.0, 1.5))
        self.assertIsNone(s.INSIDE_RADIUS_MM)
        self.assertIsNone(s.OUTSIDE_RADIUS_MM)
        self.assertEqual((s.INNER_EDGE_RADIUS_MM, s.OUTER_EDGE_RADIUS_MM), (7.0, 30.0))

    def test_missing_name_is_left_out(self):
        H.apply({"TX2.TX_TURNS": H.DELETE})
        s = SP.build(H.P, 2)
        self.assertFalse(hasattr(s, "TX_TURNS"), "the Single Generator's checker reports it")
        self.assertTrue(hasattr(SP.build(H.P, 1), "TX_TURNS"))

    def test_fixed_values_fill_a_missing_name(self):
        H.apply({"FIXED.RX_TABS": H.DELETE, "FIXED.PCB_LAYERS": 2})
        v = SP.fixed_values(H.P)
        self.assertEqual(v["RX_TABS"], "none")
        self.assertEqual(v["PCB_LAYERS"], 2, "a changed value is handed on; the checker refuses it")

    def test_modules_and_ic_module(self):
        self.assertEqual(SP.modules(H.P, 1), (H.P.RX1, H.P.TX1, H.P.ROTOR1))
        self.assertEqual(SP.modules(H.P, 2), (H.P.RX2, H.P.TX2, H.P.ROTOR2))
        self.assertIs(SP.ic_module(H.P, 2), H.P.IC2)
        with self.assertRaises(ValueError):
            SP.modules(H.P, 3)
        with self.assertRaises(ValueError):
            SP.ic_module(H.P, 0)

    def test_rename_single_files(self):
        text = "LOOPS (RX_Parameters.py) and TX_TURNS (TX_Parameters.py), Board_Parameters.py, IC_Parameters.py"
        self.assertEqual(SP.rename_single_files(text, 2),
                         "LOOPS (Dual_RX2_Parameters.py) and TX_TURNS (Dual_TX2_Parameters.py), Dual_Board_Parameters.py, Dual_IC2_Parameters.py")
        self.assertIn("Dual_Rotor1_Parameters.py", SP.rename_single_files("Rotor_Parameters.py", 1))
        # the file at the end follows the name the message starts with
        self.assertEqual(SP.rename_single_files("EXCITATION_FREQ_HZ = 'x': must be a number   (Board_Parameters.py)", 2),
                         "EXCITATION_FREQ_HZ = 'x': must be a number   (Dual_TX2_Parameters.py)")
        self.assertEqual(SP.rename_single_files("ROTOR_MODE = 3: must be one of ...   (Rotor_Parameters.py)", 1),
                         "ROTOR_MODE = 3: must be one of ...   (Dual_Board_Parameters.py)")
        self.assertEqual(SP.dual_file_of("LOOPS", 2), "Dual_RX2_Parameters.py")
        self.assertEqual(SP.dual_file_of("ROTOR_AUTO_DUTY", 1), "Dual_Rotor1_Parameters.py")
        self.assertEqual(SP.dual_file_of("TX_SHAPE", 1), SP.FIXED_FILE)
        self.assertIsNone(SP.dual_file_of("NOT_A_NAME", 1))


class TrackLayout(unittest.TestCase):
    def setUp(self):
        H.restore()

    def tearDown(self):
        H.restore()

    def test_default_layout(self):
        lay = TL.resolve(H.P)
        self.assertEqual(lay.mode, 2)
        self.assertAlmostEqual(lay.bore, 7.25)
        self.assertAlmostEqual(lay.outline, 26.875)
        self.assertEqual((lay.band1["ri"], lay.band1["ro"]), (8.45, 11.7))
        self.assertEqual((lay.band2["ri"], lay.band2["ro"]), (18.0, 23.9))
        self.assertAlmostEqual(lay.gap_expected, 3.725, 3)
        self.assertIsNone(lay.gap_setting)
        self.assertEqual(lay.set_band(1), lay.band1["names"])
        self.assertEqual(lay.edges(), (lay.bore, lay.outline))
        self.assertTrue(lay.lines()[0].startswith("layout: DUAL_MODE = 2"))

    def test_mode1_layout_fits_the_bands(self):
        H.apply(H.MODE1_BASE)
        lay = TL.resolve(H.P)
        self.assertEqual(lay.mode, 1)
        self.assertEqual((lay.bore, lay.outline), (8.5, 29.5))
        self.assertEqual(lay.gap_setting, 0.5)
        self.assertEqual((lay.band1["how"], lay.band2["how"]), ("placed", "placed"))
        self.assertLess(lay.band1["ro"], lay.band2["ri"])

    def test_mode_table(self):
        self.assertEqual(TL.MODE_NEEDS, {1: (True, True, 0), 2: (False, False, 2), 3: (True, False, 1), 4: (False, True, 2)})
        for m, needs in TL.MODE_NEEDS.items():
            self.assertEqual(TL.mode_matching(*needs), m)
        self.assertIsNone(TL.mode_matching(True, True, 2))

    def test_mode_of_errors(self):
        for bad in (0, 5, 2.5, "2", True, None):
            H.apply({"BOARD.DUAL_MODE": bad})
            with self.assertRaises(ParameterConflict, msg=repr(bad)):
                TL.mode_of(H.P)
        H.apply({"BOARD.DUAL_MODE": 3})
        self.assertEqual(TL.mode_of(H.P), 3)

    def test_band_of(self):
        self.assertIsNone(TL.band_of(types.SimpleNamespace(RX_TRACE_WIDTH_MM=0.2), 1))
        b = TL.band_of(types.SimpleNamespace(INSIDE_RADIUS_MM=9.7, OUTSIDE_RADIUS_MM=16.05), 1)
        self.assertEqual((b["ri"], b["ro"], b["how"]), (9.7, 16.05, "radii"))
        b = TL.band_of(types.SimpleNamespace(RX_R_BASE_MM=10.0, RX_A_MM=2.0), 2)
        self.assertEqual((b["ri"], b["ro"], b["how"]), (8.0, 12.0, "centre"))
        with self.assertRaises(ParameterConflict):
            TL.band_of(types.SimpleNamespace(INSIDE_RADIUS_MM=9.7), 1)
        with self.assertRaises(ParameterConflict):
            TL.band_of(types.SimpleNamespace(INSIDE_RADIUS_MM=9.7, OUTSIDE_RADIUS_MM=16.05, RX_R_BASE_MM=10.0, RX_A_MM=2.0), 1)
        with self.assertRaises(ParameterConflict):
            TL.band_of(types.SimpleNamespace(INSIDE_RADIUS_MM=16.05, OUTSIDE_RADIUS_MM=9.7), 1)

    def test_check_mode_names_the_hint(self):
        with self.assertRaises(ParameterConflict) as cm:
            TL.check_mode(H.P, 1, None, None, None, {"names": {"INSIDE_RADIUS_MM": 1, "OUTSIDE_RADIUS_MM": 2}},
                          {"names": {"RX_R_BASE_MM": 3, "RX_A_MM": 4}})
        self.assertIn("matches DUAL_MODE = 2", str(cm.exception))
        self.assertIn("DUAL_MODE", cm.exception.names)
        self.assertIsNone(TL.check_mode(H.P, 2, None, None, None, {"names": {}}, {"names": {}}))
        self.assertIsNone(TL.mode_matching(True, None, 0), "one edge alone matches no mode")

    def test_outer_room_as_rotor_builder_limits_ring_2(self):
        """With ring 2 over the TX2 turns the outline keeps: the overhang, ROTOR_AUTO_EDGE_CLEARANCE_MM, half the
        edge line, the polygon vertices and LAYOUT_TOLERANCE_MM; the rotor settings default as in the Single."""
        H.restore()
        B, TX2, RX2, RO2 = H.P.BOARD, H.P.TX2, H.P.RX2, H.P.ROTOR2
        ring = TL.BoardLayout.tx_ring(TL._tx_namespace(TX2, B), 0.0)
        edge = ring["outer_copper_edge"] + RO2.ROTOR_AUTO_TX_OVERHANG_MM + B.ROTOR_AUTO_EDGE_CLEARANCE_MM
        fine = B.EDGE_LINE_WIDTH_MM / 2.0 + B.ROTOR_CHORD_TOLERANCE_MM
        self.assertLess(fine, B.LAYOUT_TOLERANCE_MM, "the repository's slack covers the edge line and the vertices")
        want = edge + B.LAYOUT_TOLERANCE_MM
        self.assertAlmostEqual(TL.outer_room(TX2, B, RO2, RX2), want, 9)
        no_slack = types.SimpleNamespace(**dict({n: getattr(B, n) for n in dir(B) if n.isupper()}, LAYOUT_TOLERANCE_MM=0.0))
        self.assertAlmostEqual(TL.outer_room(TX2, no_slack, RO2, RX2), edge + fine, 9, "no slack: what the ring needs")
        wide_line = types.SimpleNamespace(**dict({n: getattr(B, n) for n in dir(B) if n.isupper()}, EDGE_LINE_WIDTH_MM=0.3))
        self.assertAlmostEqual(TL.outer_room(TX2, wide_line, RO2, RX2), edge + 0.15 + B.ROTOR_CHORD_TOLERANCE_MM, 9)
        no_rotor = types.SimpleNamespace(ROTOR_AUTO_COVER_TX=None, ROTOR_AUTO_TX_OVERHANG_MM=None)
        self.assertAlmostEqual(TL.outer_room(TX2, B, no_rotor, RX2), want, 9, "None: the Single Generator's defaults")
        self.assertAlmostEqual(TL.outer_room(TX2, B, types.SimpleNamespace(), RX2), want, 9, "missing: the same")
        self.assertEqual(TL.ring_vertex_sag(B, RO2, RX2, 20.0), B.ROTOR_CHORD_TOLERANCE_MM, "auto steps")
        steps = types.SimpleNamespace(ROTOR_ARC_STEPS_PER_SECTOR=8, ROTOR_CHORD_TOLERANCE_MM=0.001)
        sag = TL.ring_vertex_sag(steps, types.SimpleNamespace(ROTOR_AUTO_DUTY=0.5), types.SimpleNamespace(LOOPS=16), 20.0)
        self.assertAlmostEqual(sag, 20.0 * (1.0 / __import__("math").cos(0.5 * 2 * 3.141592653589793 / 16 / 8 / 2) - 1.0), 12)
        self.assertLess(TL.outer_room(TX2, B, types.SimpleNamespace(ROTOR_AUTO_COVER_TX=False), RX2), want,
                        "no overhang room when ring 2 stays inside the TX ring")


class Assembler(unittest.TestCase):
    def test_terminal_at_restores(self):
        self.assertEqual(StatorAssembly.TERMINAL_DEG, 0.0)
        with DSA.terminal_at(180.0):
            self.assertEqual(StatorAssembly.TERMINAL_DEG, 180.0)
        self.assertEqual(StatorAssembly.TERMINAL_DEG, 0.0)
        try:
            with DSA.terminal_at(90.0):
                raise RuntimeError("inside")
        except RuntimeError:
            pass
        self.assertEqual(StatorAssembly.TERMINAL_DEG, 0.0, "restored after an exception too")

    def test_folder_names(self):
        self.assertEqual(OF._num(26.875), "26.875")
        self.assertEqual(OF._num(8.5), "8.5")
        self.assertEqual(OF._num(29.0), "29")
        dual = types.SimpleNamespace(bore=7.25, outline=26.875,
                                     sets=(types.SimpleNamespace(N=1, P=types.SimpleNamespace(TX_TURNS=4)),
                                           types.SimpleNamespace(N=16, P=types.SimpleNamespace(TX_TURNS=4))))
        self.assertEqual(OF.folder_name(dual, H.P), "DualCoil_7.25_26.875_1x16_4x4")
        self.assertEqual(OF.project_folder(), H.PROJECT)
        H.restore()
        self.assertEqual(OF.output_dir(H.P.BOARD), os.path.join(H.PROJECT, "Output"))
        d = tempfile.mkdtemp(dir=H.temp_root())
        H.apply({"BOARD.OUTPUT_DIR": d})
        try:
            a = OF.create_output_folder(dual, H.P)
            b = OF.create_output_folder(dual, H.P)
            self.assertEqual(os.path.basename(b), "DualCoil_7.25_26.875_1x16_4x4__1")
            OF.remove_if_empty(a)
            self.assertFalse(os.path.isdir(a))
        finally:
            H.restore()

    def test_title_block_names_the_tx_layers_of_both_wirings(self):
        for case, word in (("default", "Series"), ("parallel_both_sets", "Parallel")):
            text = H.board(case).text("Stator.kicad_pcb")
            comments = re.findall(r'\(comment \d "(Set \d:[^"]*)"\)', text)
            self.assertEqual(len(comments), 2, case)
            for c in comments:
                self.assertIn(word, c)
                self.assertNotIn("None", c, "the TX layers are named for parallel wiring too")
                self.assertRegex(c, r"Turns: \d+ [\w-]+ \d+ [\w-]+, Ends at")

    def test_record_keeps_the_sets_values_as_given(self):
        """build_ring turns a copy of the set namespace: the record's set sections show the start angles as in
        the files, not shifted by the set's RX pattern zero."""
        rec = H.board("default").record
        angles = re.findall(r"START_ANGLE_DEG\s+= (\S+)", rec)
        self.assertGreaterEqual(len(angles), 4)
        self.assertEqual(set(angles), {"0.0"}, angles)

    def test_copper_extent_of_a_built_set(self):
        H.restore()
        lay = TL.resolve(H.P)
        s1 = DSA.build_set(SP.build(H.P, 1, lay.set_band(1), lay.edges()), 180.0)
        lo, hi = DDC.copper_extent(s1)
        self.assertAlmostEqual(hi, lay.reach1, 3, "the TX1 ring reaches where the layout said")
        self.assertGreater(lo, lay.bore)
        rlo, rhi = DDC.rx_extent(s1)
        self.assertLessEqual(rhi, hi)
        margin = max(H.P.RX1.RX_TRACE_WIDTH_MM, H.P.BOARD.VIA_DIAMETER_MM) / 2.0      # the inner tip vias sit on the band start
        self.assertAlmostEqual(rlo, lay.band1["ri"] - margin, 2)
        self.assertEqual(s1.terminal_deg, 180.0)
        self.assertEqual(StatorAssembly.TERMINAL_DEG, 0.0)


if __name__ == "__main__":
    unittest.main()
