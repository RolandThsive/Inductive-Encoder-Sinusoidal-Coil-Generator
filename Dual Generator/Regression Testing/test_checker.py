"""
test_checker.py  -  the dual parameter checks (the four modes, the fixed file, the dual rules, the Single
Generator's checks on each set) and the decision of Dual_RunCoilGenerator.py, run with --check (nothing is
written).  Every case sets a few values in memory and says what the generator must print and return.

A case is (name, overrides, return code, must-match patterns, must-not-match patterns).  Most cases start from
harness.MODE1_BASE (DUAL_MODE 1, edges 8.5 / 29.5, gap 0.5, three TX turns), the layout they were written against;
the cases named default_... use the repository's files as they are (the R_145 board, DUAL_MODE 2).
"""

import unittest

import harness as H
from harness import BAND1, BAND2_CENTRE, NO_EDGES, DELETE, mode1

B1_CENTRE_TOO = {"RX1.RX_R_BASE_MM": 12.875, "RX1.RX_A_MM": 3.175}
CASES = [
    # ------------------------------------------------------------------ the repository's own files
    ("default_passes", {}, 0, [r"layout: DUAL_MODE = 2", r"bore r = 7\.25 mm", r"outline r = 26\.875 mm",
                               r"gap 3\.725 mm", r"5\.80 mm bare", r"no warnings", r"CHECK PASSED"], [r"WARNING", r"ERROR"]),
    ("default_stator_only", {}, 0, [r"rotor built", r"CHECK PASSED"], [r"--stator: the rotor is not written"], ["--stator"]),
    ("default_parallel_wiring_does_not_fit", {"TX2.TX_WIRING": "parallel"}, 1,
     [r"ERROR   TX_PITCH_MM conflicts with VIA_DIAMETER_MM and TX_WIRING", r"set 2: a pitch of 0\.35 mm is too small"], []),
    ("default_rotor_only", {}, 0, [r"rotor built", r"CHECK PASSED"], [], ["--rotor"]),
    ("default_strict_passes", {"BOARD.GENERATOR_MODE": "strict"}, 0, [r"CHECK PASSED"], [r"ERROR"]),
    # ------------------------------------------------------------------ the four modes
    ("mode1", mode1(), 0, [r"DUAL_MODE = 1", r"CHECK PASSED", r"0\.500 mm free"], [r"ERROR"]),
    ("mode2_both_bands_no_gap_no_edges", mode1(**BAND1, **BAND2_CENTRE, **NO_EDGES, **{"BOARD.DUAL_MODE": 2, "BOARD.TRACK_GAP_MM": None}),
     0, [r"DUAL_MODE = 2", r"bore r = 8\.5", r"outline r = 29\.5", r"CHECK PASSED", r"0\.500 mm free"], [r"ERROR"]),
    ("mode3_rx1_band_and_gap", mode1(**BAND1, **NO_EDGES, **{"BOARD.DUAL_MODE": 3}), 0,
     [r"DUAL_MODE = 3", r"RX2 band r = 19\.55 \.\.\. 25\.9", r"CHECK PASSED"], [r"ERROR"]),
    ("mode3_rx2_band_and_gap", mode1(**BAND2_CENTRE, **NO_EDGES, **{"BOARD.DUAL_MODE": 3}), 0,
     [r"DUAL_MODE = 3", r"RX1 band r = 9\.7 \.\.\. 16\.05", r"bore r = 8\.5", r"CHECK PASSED"], [r"ERROR"]),
    ("mode4_everything_given", mode1(**BAND1, **BAND2_CENTRE, **{"BOARD.DUAL_MODE": 4, "BOARD.TRACK_GAP_MM": None}), 0,
     [r"DUAL_MODE = 4", r"CHECK PASSED"], [r"ERROR"]),
    # ------------------------------------------------------------------ what is set does not match the mode
    ("err_mode1_but_a_band_given", mode1(**BAND1), 1,
     [r"ERROR", r"DUAL_MODE = 1 \(the bands fitted between the edges\) does not match",
      r"the RX1 band is given \(Dual_RX1_Parameters.py: INSIDE_RADIUS_MM = 9.7, OUTSIDE_RADIUS_MM = 16.05\) but the mode places both bands: set its four values to None",
      r"Change the values, or choose another DUAL_MODE"], []),
    ("err_mode1_but_gap_none", mode1(**{"BOARD.TRACK_GAP_MM": None}), 1,
     [r"ERROR", r"TRACK_GAP_MM is None \(Dual_Board_Parameters.py\) but the mode needs it"], []),
    ("err_mode1_with_the_values_of_mode2", mode1(**BAND1, **BAND2_CENTRE, **NO_EDGES, **{"BOARD.TRACK_GAP_MM": None}), 1,
     [r"ERROR", r"does not match what is set", r"What is set matches DUAL_MODE = 2 \(the edges from the bands\); choose that mode"], []),
    ("err_mode2_but_gap_set", mode1(**BAND1, **BAND2_CENTRE, **NO_EDGES, **{"BOARD.DUAL_MODE": 2}), 1,
     [r"ERROR", r"TRACK_GAP_MM = 0.5 \(Dual_Board_Parameters.py\) but the mode measures the gap: set it to None"], []),
    ("err_mode2_but_edges_set", mode1(**BAND1, **BAND2_CENTRE, **{"BOARD.DUAL_MODE": 2, "BOARD.TRACK_GAP_MM": None}), 1,
     [r"ERROR", r"INNER_EDGE_RADIUS_MM = 8.5 \(Dual_Board_Parameters.py\) but the mode takes the edges from the bands: set it to None",
      r"OUTER_EDGE_RADIUS_MM = 29.5", r"matches DUAL_MODE = 4"], []),
    ("err_mode3_with_no_band", mode1(**NO_EDGES, **{"BOARD.DUAL_MODE": 3}), 1,
     [r"ERROR", r"no RX band is given .* but the mode needs one band"], []),
    ("err_mode3_with_both_bands", mode1(**BAND1, **BAND2_CENTRE, **NO_EDGES, **{"BOARD.DUAL_MODE": 3}), 1,
     [r"ERROR", r"both RX bands are given .* but the mode places the other band: set one band's four values to None"], []),
    ("err_mode4_with_one_band_none", mode1(**BAND1, **{"BOARD.DUAL_MODE": 4, "BOARD.TRACK_GAP_MM": None}), 1,
     [r"ERROR", r"the RX2 band is None \(Dual_RX2_Parameters.py: INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM or RX_R_BASE_MM / RX_A_MM\) but the mode needs both bands"], []),
    ("err_one_edge_none_in_mode1", mode1(**{"BOARD.OUTER_EDGE_RADIUS_MM": None}), 1,
     [r"ERROR", r"OUTER_EDGE_RADIUS_MM is None \(Dual_Board_Parameters.py\) but the mode needs both edges"], []),
    ("err_dual_mode_5", mode1(**{"BOARD.DUAL_MODE": 5}), 1, [r"ERROR", r"DUAL_MODE = 5: must be between 1 and 4"], []),
    ("err_dual_mode_text", mode1(**{"BOARD.DUAL_MODE": "auto"}), 1, [r"ERROR", r"DUAL_MODE = 'auto': must be a whole number between 1 and 4"], []),
    ("err_dual_mode_missing", mode1(**{"BOARD.DUAL_MODE": DELETE}), 1, [r"ERROR", r"DUAL_MODE is missing - add it to Dual_Board_Parameters.py"], []),
    ("err_half_a_band_pair", mode1(**{"RX1.INSIDE_RADIUS_MM": 9.7}), 1, [r"ERROR"], []),
    ("err_both_pairs_in_rx1", mode1(**BAND1, **B1_CENTRE_TOO), 1, [r"ERROR"], []),
    ("err_mode2_bands_too_close", mode1(**BAND1, **NO_EDGES, **{"RX2.RX_R_BASE_MM": 21.0, "RX2.RX_A_MM": 3.0, "BOARD.DUAL_MODE": 2, "BOARD.TRACK_GAP_MM": None}), 1,
     [r"ERROR", r"run into each other"], []),
    ("err_mode4_edges_too_tight", mode1(**BAND1, **BAND2_CENTRE, **{"BOARD.DUAL_MODE": 4, "BOARD.TRACK_GAP_MM": None, "BOARD.OUTER_EDGE_RADIUS_MM": 28.0}), 1, [r"ERROR"], []),
    ("err_board_too_small_narrow_bands", mode1(**{"BOARD.OUTER_EDGE_RADIUS_MM": 20.0}), 1, [r"ERROR", r"hint    DUAL_MODE 1 fitted"], []),
    ("err_board_far_too_small", mode1(**{"BOARD.OUTER_EDGE_RADIUS_MM": 16.0}), 1, [r"ERROR", r"too small for two RX bands"], []),
    # ------------------------------------------------------------------ the fixed file
    ("err_fixed_pcb_layers_changed", mode1(**{"FIXED.PCB_LAYERS": 2}), 1, [r"ERROR", r"is FIXED at 4"], []),
    ("err_fixed_name_missing", mode1(**{"FIXED.RX_TABS": DELETE}), 1, [r"ERROR", r"RX_TABS is missing"], []),
    ("err_fixed_tx_shape_changed", mode1(**{"FIXED.TX_SHAPE": "spiral"}), 1, [r"ERROR", r"is FIXED at 'stepped_diagonal'"], []),
    ("warn_cover_tx_in_the_fixed_file", mode1(**{"FIXED.ROTOR_AUTO_COVER_TX": False}), 0,
     [r"WARNING", r"ROTOR_AUTO_COVER_TX in Dual_Fixed_Parameters.py is ignored: it belongs in Dual_Rotor1_Parameters.py / Dual_Rotor2_Parameters.py"], [r"ERROR"]),
    ("warn_tx_shape_in_a_tx_file", mode1(**{"TX2.TX_SHAPE": "spiral"}), 0, [r"WARNING", r"TX_SHAPE in Dual_TX2_Parameters.py is ignored"], [r"ERROR"]),
    ("warn_fixed_name_in_board_file", mode1(**{"BOARD.PCB_LAYERS": 2}), 0, [r"WARNING", r"PCB_LAYERS"], [r"ERROR"]),
    ("warn_ic_name_in_board_file", mode1(**{"BOARD.IC_MIN_RP_OHM": 100}), 0,
     [r"WARNING", r"IC_MIN_RP_OHM in Dual_Board_Parameters.py is ignored: it belongs in Dual_IC1_Parameters.py / Dual_IC2_Parameters.py", r"CHECK PASSED"], [r"ERROR"]),
    ("warn_unknown_name_in_rx1", mode1(**{"RX1.FOO_BAR": 1}), 0, [r"WARNING", r"FOO_BAR"], [r"ERROR"]),
    ("warn_receiver_ic_retired", mode1(**{"TX1.RECEIVER_IC": "IPS2550"}), 0,
     [r"WARNING", r"RECEIVER_IC in Dual_TX1_Parameters.py is no longer used", r"Dual_IC1_Parameters.py", r"CHECK PASSED"], [r"ERROR"]),
    # ------------------------------------------------------------------ the rotor rings
    ("warn_then_err_ring1_covers_tx1", mode1(**{"ROTOR1.ROTOR_AUTO_COVER_TX": True}), 1,
     [r"WARNING", r"ROTOR_AUTO_COVER_TX = True in Dual_Rotor1_Parameters.py", r"ROTOR_1_TO_RX2_MM", r"ERROR", r"rotor rings are too close"], []),
    ("ring1_covers_tx1_ring2_moved_out", mode1(**{"ROTOR1.ROTOR_AUTO_COVER_TX": True, "BOARD.TRACK_GAP_MM": 3.5, "BOARD.OUTER_EDGE_RADIUS_MM": 31.0}), 0,
     [r"WARNING", r"ROTOR_AUTO_COVER_TX = True", r"CHECK PASSED"], [r"ERROR"]),
    ("err_ring1_cover_with_bad_overhang", mode1(**{"ROTOR1.ROTOR_AUTO_COVER_TX": True, "ROTOR1.ROTOR_AUTO_TX_OVERHANG_MM": -1}), 1,
     [r"ERROR", r"ROTOR_AUTO_TX_OVERHANG_MM"], []),
    ("warn_ring1_too_close_to_rx2", mode1(**{"ROTOR1.ROTOR_AUTO_EXTENSION_OUTER_MM": 1.0}), 0, [r"WARNING", r"ROTOR_1_TO_RX2_MM"], [r"ERROR"]),
    ("err_ring2_too_close_to_ring1", mode1(**{"ROTOR2.ROTOR_AUTO_EXTENSION_INNER_MM": 2.0}), 1, [r"ERROR", r"rotor rings are too close"], []),
    ("rotor_zero_from_the_board", mode1(**{"BOARD.ROTOR_START_ANGLE_ZERO": "Board"}), 0, [r"CHECK PASSED"], [r"ERROR"]),
    ("err_rotor_zero_bad", mode1(**{"BOARD.ROTOR_START_ANGLE_ZERO": "shaft"}), 1,
     [r"ERROR", r"ROTOR_START_ANGLE_ZERO = 'shaft': must be one of 'rx_zero', 'board'"], []),
    ("err_rotor_zero_missing", mode1(**{"BOARD.ROTOR_START_ANGLE_ZERO": DELETE}), 1, [r"ERROR", r"ROTOR_START_ANGLE_ZERO is missing"], []),
    ("custom_rotor_mode", mode1(**{"BOARD.ROTOR_MODE": "custom"}), 0, [r"CHECK PASSED"], [r"ERROR"]),
    # ------------------------------------------------------------------ the dual rules
    ("err_single_wiring", mode1(**{"TX1.TX_WIRING": "single"}), 1, [r"ERROR", r"a single-layer TX has no place"], []),
    ("parallel_wiring_set_1", mode1(**{"TX1.TX_WIRING": "parallel"}), 0, [r"CHECK PASSED", r"0\.500 mm free"], [r"ERROR"]),
    ("parallel_wiring_both_sets", mode1(**{"TX1.TX_WIRING": "parallel", "TX2.TX_WIRING": "parallel"}), 0, [r"CHECK PASSED"], [r"ERROR"]),
    ("err_duplicate_net", mode1(**{"RX2.RX_NET_PHASE_0_2": "SIN_1"}), 1, [r"ERROR", r"used twice"], []),
    ("warn_set2_on_all_four_layers", mode1(**{"TX2.TX_LAYER_A": 3, "TX2.TX_LAYER_B": 4}), 0, [r"WARNING", r"all four layers"], [r"ERROR"]),
    ("warn_frequencies_10_percent_apart", mode1(**{"TX2.EXCITATION_FREQ_HZ": 3.3e6}), 0, [r"WARNING", r"differ by 10\.0 %"], [r"ERROR"]),
    ("warn_frequencies_3_to_2", mode1(**{"TX2.EXCITATION_FREQ_HZ": 4.5e6}), 0,
     [r"WARNING", r"ratio 3:2", r"TX_FREQ_RATIO_TOLERANCE = 2 %", r"TX_FREQ_RATIO_MAX_ORDER = 4"], [r"ERROR"]),
    ("ratio_warning_off_with_order_1", mode1(**{"TX2.EXCITATION_FREQ_HZ": 4.5e6, "BOARD.TX_FREQ_RATIO_MAX_ORDER": 1}), 0,
     [r"no warnings", r"CHECK PASSED"], [r"WARNING"]),
    ("warn_5_to_4_found_with_order_5", mode1(**{"TX2.EXCITATION_FREQ_HZ": 3.75e6, "BOARD.TX_FREQ_RATIO_MAX_ORDER": 5}), 0, [r"WARNING", r"ratio 5:4"], [r"ERROR"]),
    ("5_to_4_not_found_with_order_4", mode1(**{"TX2.EXCITATION_FREQ_HZ": 3.75e6}), 0, [r"no warnings", r"CHECK PASSED"], [r"WARNING"]),
    ("warn_within_8_percent_tolerance", mode1(**{"BOARD.TX_FREQ_RATIO_TOLERANCE": 0.08}), 0,
     [r"WARNING", r"ratio 3:2", r"TX_FREQ_RATIO_TOLERANCE = 8 %"], [r"ERROR"]),
    ("err_ratio_order_0", mode1(**{"BOARD.TX_FREQ_RATIO_MAX_ORDER": 0}), 1, [r"ERROR", r"TX_FREQ_RATIO_MAX_ORDER"], []),
    ("err_ratio_tolerance_1", mode1(**{"BOARD.TX_FREQ_RATIO_TOLERANCE": 1.0}), 1, [r"ERROR", r"TX_FREQ_RATIO_TOLERANCE"], []),
    ("err_layout_tolerance_negative", mode1(**{"BOARD.LAYOUT_TOLERANCE_MM": -0.1}), 1, [r"ERROR", r"LAYOUT_TOLERANCE_MM"], []),
    ("layout_tolerance_0_passes", mode1(**{"BOARD.LAYOUT_TOLERANCE_MM": 0}), 0, [r"CHECK PASSED"], [r"ERROR"]),
    ("err_missing_tx_turns", mode1(**{"TX1.TX_TURNS": DELETE}), 1, [r"ERROR", r"TX_TURNS"], []),
    ("err_band_split_1", mode1(**{"BOARD.BAND_SPLIT": 1.0}), 1, [r"ERROR", r"BAND_SPLIT"], []),
    ("err_gap_negative", mode1(**{"BOARD.TRACK_GAP_MM": -1}), 1, [r"ERROR", r"TRACK_GAP_MM"], []),
    ("strict_mode_with_a_board_warning", mode1(**{"BOARD.GENERATOR_MODE": "strict", "ROTOR1.ROTOR_AUTO_EXTENSION_OUTER_MM": 1.0}), 1,
     [r"WARNING", r'GENERATOR_MODE = "strict"', r"board warning\(s\) in strict mode"], []),
    # ------------------------------------------------------------------ the ICs and the estimate
    ("err_ic2_oscillator_range_empty", mode1(**{"IC2.IC_OSC_MIN_MHZ": 6.0, "IC2.IC_OSC_MAX_MHZ": 5.0}), 1,
     [r"ERROR", r"IC_OSC_MIN_MHZ conflicts with IC_OSC_MAX_MHZ", r"set 2: the IC.s oscillator range 6 ... 5 MHz is empty"], []),
    ("different_ics_per_set", mode1(**{"IC1.IC_NAME": "IPS2200", "IC1.IC_OSC_MIN_MHZ": 1.7, "IC1.IC_OSC_MAX_MHZ": 5.8, "IC1.IC_MIN_RP_OHM": 100,
                                       "IC2.IC_NAME": None, "IC2.IC_OSC_MIN_MHZ": None, "IC2.IC_OSC_MAX_MHZ": None, "IC2.IC_MIN_RP_OHM": None}), 0,
     [r"receiver IC IPS2200", r"no IC limits set", r"CHECK PASSED"], [r"ERROR"]),
    ("e24_caps_one_cap_across_the_coil", mode1(**{"BOARD.TANK_CAP_SERIES": "e24", "IC1.IC_SPLIT_TANK_CAPS": False}), 0,
     [r"\(E24\)", r"across the coil \(or", r"CHECK PASSED"], [r"ERROR"]),
    ("err_tank_cap_series_e48", mode1(**{"BOARD.TANK_CAP_SERIES": "e48"}), 1, [r"ERROR", r"TANK_CAP_SERIES"], []),
    ("info_ic_name_missing_in_ic1", mode1(**{"IC1.IC_NAME": DELETE}), 0, [r"IC_NAME is not in Dual_IC1_Parameters.py", r"CHECK PASSED"], [r"ERROR"]),
    # ------------------------------------------------------------------ the Single Generator's checks on each set
    ("err_set2_loops_17", mode1(**{"RX2.LOOPS": 17}), 1, [r"ERROR.*set 2: LOOPS", r"Dual_RX2_Parameters\.py"], []),
    ("err_set1_tx_pitch_text", mode1(**{"TX1.TX_PITCH_MM": "0.6"}), 1, [r"ERROR.*set 1: TX_PITCH_MM", r"Dual_TX1_Parameters\.py"], []),
    ("err_set1_rx_layers_equal", mode1(**{"RX1.RX_LAYER_A": 2, "RX1.RX_LAYER_B": 2}), 1, [r"ERROR   RX_LAYER_A conflicts with RX_LAYER_B\n\s+set 1: the two RX layers must be different"], []),
    ("err_set2_drill_too_big", mode1(**{"BOARD.VIA_DRILL_MM": 0.8}), 1, [r"ERROR   VIA_DRILL_MM conflicts with VIA_DIAMETER_MM\n\s+set 1: the drill",
                                                                        r"ERROR   VIA_DRILL_MM conflicts with VIA_DIAMETER_MM\n\s+set 2: the drill"], []),
    ("set2_duty_low_warns", mode1(**{"ROTOR2.ROTOR_AUTO_DUTY": 0.2}), 0, [r"WARNING.*set 2: rotor metal fraction 0\.2", r"CHECK PASSED"], [r"ERROR"]),
    # ------------------------------------------------------------------ VIA_TYPE (shared by both sets)
    ("via_type_blind_default_layers", mode1(**{"BOARD.VIA_TYPE": "blind", "BOARD.VIA_DIAMETER_MM": 0.4, "BOARD.VIA_DRILL_MM": 0.15}), 0,
     [r"info    VIA_TYPE conflicts with RX_LAYER_A and RX_LAYER_B\n\s+set 1: the RX tip vias are blind vias between Top and Inner-1",
      r"info    VIA_TYPE conflicts with RX_LAYER_A and RX_LAYER_B\n\s+set 2: the RX tip vias are blind vias between Top and Inner-1",
      r"WARNING VIA_TYPE conflicts with TX_LAYER_A and TX_LAYER_B\n\s+set 1: the TX vias join Top and Inner-2, skipping the layer between",
      r"WARNING VIA_TYPE conflicts with TX_LAYER_A and TX_LAYER_B\n\s+set 2: the TX vias join Top and Inner-2, skipping the layer between",
      r"CHECK PASSED"], [r"ERROR", r"VIA_TYPE conflicts with VIA_DRILL_MM"]),
    ("via_type_blind_large_drill_warns", mode1(**{"BOARD.VIA_TYPE": "blind"}), 0,
     [r"WARNING VIA_TYPE conflicts with VIA_DRILL_MM\n\s+set 1: blind vias are laser-drilled, at most about 0\.15 mm wide at "
      r"common fabs; VIA_DRILL_MM = 0\.3 is a mechanical drill", r"CHECK PASSED"], [r"ERROR"]),
    ("via_type_bad_value", mode1(**{"BOARD.VIA_TYPE": "micro"}), 1,
     [r"ERROR   set 1: VIA_TYPE = 'micro': must be one of 'through', 'blind'   \(Dual_Board_Parameters\.py\)", r"FAILED: 2 parameter error"], []),
    ("via_type_missing_uses_through", mode1(**{"BOARD.VIA_TYPE": DELETE}), 0,
     [r"VIA_TYPE is not in Dual_Board_Parameters\.py: using the default 'through'", r"CHECK PASSED"], [r"ERROR", r"blind vias"]),
    ("via_type_in_a_set_file_is_ignored", mode1(**{"RX1.VIA_TYPE": "blind"}), 0,
     [r"WARNING VIA_TYPE in Dual_RX1_Parameters\.py is ignored: it belongs in Dual_Board_Parameters\.py", r"CHECK PASSED"],
     [r"ERROR", r"blind vias between"]),
]


class CheckerCases(unittest.TestCase):
    pass


def _make(name, overrides, rc, must, must_not, extra_args):
    def test(self):
        res = H.check(overrides, extra_args)
        tail = "\n".join(res.lines[-25:])
        self.assertEqual(res.rc, rc, f"return code {res.rc}, expected {rc}:\n{tail}")
        for pat in must:
            self.assertTrue(res.has(pat), f"the output does not match {pat!r}:\n{tail}")
        for pat in must_not:
            self.assertFalse(res.has(pat), f"the output matches {pat!r} but must not:\n{tail}")
        self.assertEqual(res.err, "", f"the run wrote to stderr:\n{res.err}")
        if rc == 1:
            self.assertTrue(res.has(r"FAILED: .*Nothing was written"), f"a failed run must say so:\n{tail}")
        else:
            self.assertTrue(res.has(r"CHECK PASSED"), f"a passed check must say so:\n{tail}")
    test.__name__ = "test_" + name
    test.__doc__ = f"{name} -> rc {rc}"
    return test


for _case in CASES:
    _name, _ov, _rc, _must, _not = _case[:5]
    _args = _case[5] if len(_case) > 5 else ()
    setattr(CheckerCases, "test_" + _name, _make(_name, _ov, _rc, _must, _not, _args))


class CheckerBehaviour(unittest.TestCase):
    def test_overrides_do_not_leak_between_runs(self):
        H.check(mode1(**{"RX2.LOOPS": 0}))
        self.assertEqual(H.P.RX2.LOOPS, 16)
        self.assertEqual(H.P.BOARD.DUAL_MODE, 2)
        res = H.check()
        self.assertEqual(res.rc, 0)
        self.assertFalse(res.has("WARNING"))

    def test_single_generator_is_left_as_it_was(self):
        """A dual run turns each set to its own terminal angle; the Single Generator's own setting is back at
        0 deg afterwards, and its parameter module still holds the Single Generator's values."""
        from Generator.Stator import StatorAssembly
        import Parameters as SingleP
        H.check()
        self.assertEqual(StatorAssembly.TERMINAL_DEG, 0.0)
        self.assertEqual((SingleP.LOOPS, SingleP.PCB_LAYERS, SingleP.OUTER_EDGE_RADIUS_MM), (1, 2, 27.0))

    def test_no_color_output_is_plain(self):
        self.assertNotIn("\x1b[", H.check().out)

    def test_every_error_names_its_dual_file(self):
        res = H.check(mode1(**{"RX1.LOOPS": 0, "TX2.TX_TURNS": 0, "ROTOR1.ROTOR_AUTO_DUTY": 2, "IC2.IC_MIN_RP_OHM": -1}))
        self.assertEqual(res.rc, 1)
        for f in ("Dual_RX1_Parameters.py", "Dual_TX2_Parameters.py", "Dual_Rotor1_Parameters.py", "Dual_IC2_Parameters.py"):
            self.assertIn(f, res.out)
        self.assertNotIn("RX_Parameters.py", res.out.replace("Dual_RX1_Parameters.py", "").replace("Dual_RX2_Parameters.py", ""),
                         "the Single Generator's file names are translated into the dual ones")


if __name__ == "__main__":
    unittest.main()
