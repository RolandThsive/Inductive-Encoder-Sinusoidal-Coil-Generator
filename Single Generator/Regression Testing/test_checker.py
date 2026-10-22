"""
test_checker.py  -  the parameter checks and the decision of RunCoilGenerator.py, run with --check (nothing is
written): every case sets a few values in memory and says what the generator must print and return.

A case is (name, overrides, return code, must-match patterns, must-not-match patterns).  The patterns are regular
expressions searched in everything the run printed.  A return code of 1 means "FAILED ... Nothing was written".
"""

import re
import unittest

import harness as H

D = H.DELETE
# a 4-layer board whose via pairs are Top + Inner-1 (TX) and Inner-2 + Bottom (RX): one-step blind vias
FOUR = {"PCB_LAYERS": 4, "TX_WIRING": "series", "TX_LAYER_A": 1, "TX_LAYER_B": 2, "RX_LAYER_A": 3, "RX_LAYER_B": 4,
        "RX_TABS": "none"}
FOUR_BLIND = dict(FOUR, VIA_TYPE="blind", VIA_DIAMETER_MM=0.4, VIA_DRILL_MM=0.15)
CASES = [
    # ------------------------------------------------------------------ the defaults
    ("default_passes", {}, 0, [r"parameters OK", r"stator built", r"rotor built", r"no warnings", r"CHECK PASSED"],
     [r"WARNING", r"ERROR"]),
    ("default_stator_only", {}, 0, [r"--stator: the rotor is not written", r"CHECK PASSED"], [r"rotor built"],
     ["--stator"]),
    ("default_rotor_only", {}, 0, [r"rotor built", r"CHECK PASSED"], [], ["--rotor"]),
    ("strict_mode_case_insensitive_no_warnings", {"GENERATOR_MODE": "Strict"}, 0, [r"CHECK PASSED"], [r"ERROR"]),
    # ------------------------------------------------------------------ one value of every kind, wrong
    ("num_negative", {"VIA_DRILL_MM": -0.1}, 1, [r"ERROR.*VIA_DRILL_MM", r"Board_Parameters\.py", r"FAILED: 1 parameter error"], []),
    ("num_as_text", {"TX_PITCH_MM": "0.6"}, 1, [r"ERROR.*TX_PITCH_MM", r"TX_Parameters\.py"], []),
    ("num_bool_is_not_a_number", {"AIR_GAP_MM": True}, 1, [r"ERROR.*AIR_GAP_MM"], []),
    ("num_above_limit", {"EDGE_LINE_WIDTH_MM": 2.0}, 1, [r"ERROR.*EDGE_LINE_WIDTH_MM"], []),
    ("int_as_float", {"LOOPS": 2.5}, 1, [r"ERROR.*LOOPS"], []),
    ("int_zero", {"LOOPS": 0}, 1, [r"ERROR.*LOOPS"], []),
    ("int_above_limit", {"LOOPS": 17}, 1, [r"ERROR.*LOOPS"], []),
    ("choice_bad_number", {"PCB_LAYERS": 3}, 1, [r"ERROR.*PCB_LAYERS"], []),
    ("choice_case_sensitive", {"RX_PROFILE": "Equal_Area"}, 1, [r"ERROR.*RX_PROFILE"], []),
    ("choice_bad_text", {"TX_WIRING": "double"}, 1, [r"ERROR.*TX_WIRING"], []),
    ("pair_too_short", {"PAGE_SIZE_MM": (200,)}, 1, [r"ERROR.*PAGE_SIZE_MM"], []),
    ("bool_as_text", {"ROTOR_AUTO_COVER_TX": "yes"}, 1, [r"ERROR.*ROTOR_AUTO_COVER_TX"], []),
    ("net_empty", {"TX_NET": ""}, 1, [r"ERROR.*TX_NET"], []),
    ("file_empty", {"STATOR_FILE": ""}, 1, [r"ERROR.*STATOR_FILE", r"must be a file name"], []),
    ("file_with_folder", {"STATOR_FILE": "a/b.kicad_pcb"}, 1, [r"ERROR.*STATOR_FILE", r"give only a file name"], []),
    ("file_odd_extension_warns", {"STATOR_FILE": "Stator.txt"}, 0, [r"WARNING.*STATOR_FILE.*does not end in \.kicad_pcb", r"CHECK PASSED"], [r"ERROR"]),
    ("steps_bad_text", {"STEPS_PER_LOOP": "many"}, 1, [r"ERROR.*STEPS_PER_LOOP"], []),
    ("auto_or_int_below_limit", {"TX_STEPS": 5}, 1, [r"ERROR.*TX_STEPS"], []),
    ("auto_or_num_bad", {"TX_SHAPE": "stepped_arc", "TX_STEPPED_ARC_RADIUS_MM": "big"}, 1,
     [r"ERROR.*TX_STEPPED_ARC_RADIUS_MM"], []),
    ("rotor_layers_bad", {"ROTOR_AUTO_COPPER_LAYERS": ["X.Cu"]}, 1, [r"ERROR.*ROTOR_AUTO_COPPER_LAYERS"], []),
    ("mask_expansion_bad", {"ROTOR_SOLDER_MASK_EXPANSION_MM": -0.5}, 1, [r"ERROR.*ROTOR_SOLDER_MASK_EXPANSION_MM"], []),
    ("str_or_none_bad", {"IC_NAME": 42}, 1, [r"ERROR.*IC_NAME"], []),
    ("num_or_none_bad", {"INNER_EDGE_RADIUS_MM": "none"}, 1, [r"ERROR.*INNER_EDGE_RADIUS_MM"], []),
    # ------------------------------------------------------------------ missing, unknown, inactive
    ("required_missing", {"TX_TURNS": D}, 1, [r"ERROR.*TX_TURNS", r"missing"], []),
    ("optional_missing_uses_default", {"COPPER_THICKNESS_UM": D, "TANK_CAP_SERIES": D, "IC_NAME": D}, 0,
     [r"CHECK PASSED"], [r"ERROR"]),
    ("unknown_name_warns", {"FOO_BAR_MM": 1.0}, 0, [r"WARNING.*FOO_BAR_MM", r"CHECK PASSED"], [r"ERROR"]),
    ("inactive_value_not_checked", {"TX_SHAPE": "stepped_arc", "TX_STEPPED_ANGLE_DEG": 1000}, 0, [r"CHECK PASSED"],
     [r"ERROR.*TX_STEPPED_ANGLE_DEG"]),
    ("active_value_checked", {"TX_STEPPED_ANGLE_DEG": 1000}, 1, [r"ERROR.*TX_STEPPED_ANGLE_DEG"], []),
    ("rx_layers_ignored_on_two_layer_board", {"RX_LAYER_A": 9, "RX_LAYER_B": 9}, 0, [r"CHECK PASSED"],
     [r"ERROR.*RX_LAYER"]),
    ("tab_values_ignored_without_tabs", {"RX_TABS": "none", "RX_TAB_WIDTH_MM": -1}, 0, [r"CHECK PASSED"],
     [r"ERROR.*RX_TAB_WIDTH_MM"]),
    # ------------------------------------------------------------------ conflicts between values
    ("drill_not_smaller_than_via", {"VIA_DRILL_MM": 0.8}, 1, [r"ERROR.*VIA_DRILL_MM.*VIA_DIAMETER_MM", r"drill"], []),
    ("rx_layers_equal", {"PCB_LAYERS": 4, "RX_LAYER_A": 2, "RX_LAYER_B": 2}, 1, [r"ERROR.*RX_LAYER_A.*RX_LAYER_B"], []),
    ("net_names_equal", {"RX_NET_PHASE_0_2": "TX"}, 1, [r"ERROR", r"net names must all be different"], []),
    ("outer_edge_too_small", {"OUTER_EDGE_RADIUS_MM": 22.0}, 1, [r"ERROR.*OUTER_EDGE_RADIUS_MM", r"too small"], []),
    ("same_file_names", {"ROTOR_FILE": "Stator.kicad_pcb"}, 1, [r"ERROR.*STATOR_FILE.*ROTOR_FILE"], []),
    ("tx_pitch_too_small", {"TX_PITCH_MM": 0.25}, 1, [r"ERROR", r"TX_PITCH_MM"], []),
    ("band_half_given", {"INSIDE_RADIUS_MM": None}, 1, [r"ERROR"], []),
    ("band_given_twice", {"RX_R_BASE_MM": 18.8, "RX_A_MM": 2.6}, 1, [r"ERROR"], []),
    ("band_from_board_edges", {"INSIDE_RADIUS_MM": None, "OUTSIDE_RADIUS_MM": None}, 0,
     [r"info.*INNER_EDGE_RADIUS_MM = 15 sets the centre hole", r"CHECK PASSED"], [r"ERROR"]),
    ("rx_via_angle_below_limit", {"RX_VIA_ELECTRICAL_DEG": 40.0}, 1, [r"ERROR.*RX_VIA_ELECTRICAL_DEG"], []),
    ("rotor_custom_sectors_mismatch_warns", {"ROTOR_MODE": "custom", "ROTOR_CUSTOM_SECTORS": 3}, 0,
     [r"WARNING.*ROTOR_CUSTOM_SECTORS.*LOOPS", r"one sector per loop", r"CHECK PASSED"], [r"ERROR"]),
    ("rotor_custom_radii_swapped", {"ROTOR_MODE": "custom", "ROTOR_CUSTOM_INNER_RADIUS_MM": 24.3,
                                    "ROTOR_CUSTOM_OUTER_RADIUS_MM": 15.53}, 1,
     [r"ERROR.*ROTOR_CUSTOM_INNER_RADIUS_MM.*ROTOR_CUSTOM_OUTER_RADIUS_MM"], []),
    ("rotor_custom_passes", {"ROTOR_MODE": "custom"}, 0, [r"CHECK PASSED"], [r"ERROR"]),
    ("rotor_duty_at_limit", {"ROTOR_AUTO_DUTY": 1.0}, 1, [r"ERROR.*ROTOR_AUTO_DUTY"], []),
    ("rotor_duty_low_warns", {"ROTOR_AUTO_DUTY": 0.2}, 0, [r"WARNING.*rotor metal fraction 0\.2", r"CHECK PASSED"], [r"ERROR"]),
    ("ic_range_empty", {"IC_OSC_MIN_MHZ": 6.0, "IC_OSC_MAX_MHZ": 5.0}, 1, [r"ERROR.*IC_OSC_MIN_MHZ.*IC_OSC_MAX_MHZ"], []),
    ("ic_limits_off", {"IC_OSC_MIN_MHZ": None, "IC_OSC_MAX_MHZ": None, "IC_MIN_RP_OHM": None}, 0,
     [r"CHECK PASSED"], [r"ERROR", r"range 2 \.\.\. 5\.6"]),
    ("tank_series_bad", {"TANK_CAP_SERIES": "e48"}, 1, [r"ERROR.*TANK_CAP_SERIES"], []),
    ("frequency_below_ic_range_warns", {"EXCITATION_FREQ_HZ": 1.0e6}, 0, [r"WARNING", r"CHECK PASSED"], [r"ERROR"]),
    ("tab_legs_too_close", {"RX_TAB_WIDTH_MM": 0.3}, 1, [r"ERROR.*RX_TAB_WIDTH_MM"], []),
    ("series_tx_without_fingers", {"TX_WIRING": "series", "RX_TABS": "none"}, 0,
     [r"series TX on two layers: 3 turns on B\.Cu \+ 3 turns on F\.Cu", r"CHECK PASSED"], [r"ERROR"]),
    ("series_tx_fingers_too_short", {"TX_WIRING": "series"}, 1,
     [r"ERROR.*RX_TAB_LENGTH_MM.*RX_TAB_LAYER.*TX_TURNS", r"goes around the fingers"], []),
    ("four_layers_default_layers", {"PCB_LAYERS": 4}, 0, [r"CHECK PASSED"], [r"ERROR"]),
    # ------------------------------------------------------------------ the geometry stops the run
    ("subcoils_do_not_fit", {"LOOPS": 8, "RX_SUBCOILS": 2, "RX_TABS": "none"}, 1,
     [r"WARNING.*RX_SUBCOILS", r"ERROR.*LOOPS.*RX_SUBCOILS", r"junction vias", r"FAILED: the stator cannot be built"], []),
    ("fingers_hit_the_tx", {"TX_SHAPE": "spiral", "TX_TURNS": 5, "OUTER_EDGE_RADIUS_MM": None}, 1,
     [r"ERROR.*RX_TAB_LENGTH_MM.*TX_OFFSET_MM"], []),
    ("board_too_small_for_bands", {"OUTER_EDGE_RADIUS_MM": 18.0, "INSIDE_RADIUS_MM": None, "OUTSIDE_RADIUS_MM": None}, 1,
     [r"ERROR"], []),
    # ------------------------------------------------------------------ strict mode
    ("strict_turns_board_warning_into_error", {"GENERATOR_MODE": "strict", "LOOPS": 4, "RX_SUBCOILS": 2, "RX_TABS": "none"}, 1,
     [r"WARNING.*via sits only", r'GENERATOR_MODE = "strict": 1 warning\(s\) about the boards count as errors',
      r"FAILED: 1 board warning\(s\) in strict mode"], []),
    ("normal_mode_keeps_board_warning", {"LOOPS": 4, "RX_SUBCOILS": 2, "RX_TABS": "none"}, 0,
     [r"WARNING.*via sits only", r"1 warning\(s\) - the files can still be written", r"CHECK PASSED"], [r"ERROR"]),
    ("strict_ignores_parameter_warnings", {"GENERATOR_MODE": "strict", "FOO_BAR_MM": 1.0}, 0,
     [r"WARNING.*FOO_BAR_MM", r"CHECK PASSED"], [r"ERROR"]),
    ("strict_ignores_electrical_warnings", {"GENERATOR_MODE": "strict", "EXCITATION_FREQ_HZ": 1.0e6}, 0,
     [r"WARNING", r"CHECK PASSED"], [r"ERROR"]),
]


CASES += [
    # ------------------------------------------------------------------ VIA_TYPE (blind vias, 4 layers only)
    ("via_type_missing_uses_through", {"VIA_TYPE": D}, 0,
     [r"info\s+VIA_TYPE is not in Board_Parameters\.py: using the default 'through'", r"CHECK PASSED"], [r"ERROR", r"WARNING"]),
    ("via_type_bad_value", {"VIA_TYPE": "buried"}, 1,
     [r"ERROR   VIA_TYPE = 'buried': must be one of 'through', 'blind'", r"Board_Parameters\.py"], []),
    ("via_type_blind_on_two_layers", {"VIA_TYPE": "blind"}, 1,
     [r'ERROR   VIA_TYPE conflicts with PCB_LAYERS\n\s+VIA_TYPE = "blind" needs inner layers to stop at; a 2-layer board '
      r'has only through vias - set PCB_LAYERS = 4, or VIA_TYPE = "through"', r"FAILED: 1 parameter error"], []),
    ("via_type_blind_pairs_reported", dict(FOUR_BLIND, VIA_TYPE="Blind"), 0,
     [r"info    VIA_TYPE conflicts with RX_LAYER_A and RX_LAYER_B\n\s+the RX tip vias are blind vias between Inner-2 and Bottom",
      r"info    VIA_TYPE conflicts with TX_LAYER_A and TX_LAYER_B\n\s+the TX vias are blind vias between Top and Inner-1",
      r"CHECK PASSED"], [r"ERROR", r"VIA_TYPE conflicts with VIA_DRILL_MM", r"changes nothing"]),
    ("via_type_blind_large_drill_warns", dict(FOUR, VIA_TYPE="blind"), 0,
     [r"WARNING VIA_TYPE conflicts with VIA_DRILL_MM\n\s+blind vias are laser-drilled, at most about 0\.15 mm wide at common "
      r"fabs; VIA_DRILL_MM = 0\.4 is a mechanical drill - set VIA_DRILL_MM and VIA_DIAMETER_MM to blind via sizes, or use "
      r"through vias", r"CHECK PASSED"], [r"ERROR"]),
    ("via_type_blind_skipped_layer_warns", dict(FOUR_BLIND, RX_LAYER_A=1, RX_LAYER_B=3, TX_LAYER_A=2, TX_LAYER_B=4), 0,
     [r"WARNING VIA_TYPE conflicts with RX_LAYER_A and RX_LAYER_B\n\s+the RX tip vias join Top and Inner-2, skipping the "
      r"layer between: not a one-step blind via",
      r"WARNING VIA_TYPE conflicts with TX_LAYER_A and TX_LAYER_B\n\s+the TX vias join Inner-1 and Bottom, skipping"],
     [r"ERROR"]),
    ("via_type_blind_buried_and_through_pairs", dict(FOUR_BLIND, RX_LAYER_A=2, RX_LAYER_B=3, TX_LAYER_A=1, TX_LAYER_B=4), 0,
     [r"info    VIA_TYPE conflicts with RX_LAYER_A and RX_LAYER_B\n\s+the RX tip vias join Inner-1 and Inner-2: that is a "
      r"buried via \(mechanically drilled inside the board\), written with KiCad's blind via token",
      r"info    VIA_TYPE conflicts with TX_LAYER_A and TX_LAYER_B\n\s+the TX vias join Top and Bottom: they stay through vias"],
     [r"ERROR", r"changes nothing"]),
    ("via_type_blind_changes_nothing_warns", {"PCB_LAYERS": 4, "VIA_TYPE": "blind", "VIA_DIAMETER_MM": 0.4, "VIA_DRILL_MM": 0.15,
                                              "RX_LAYER_A": 1, "RX_LAYER_B": 4, "TX_WIRING": "single", "TX_LAYER_A": 1,
                                              "TX_SERIES_UNDERPASS_LAYER": 4, "RX_TABS": "none"}, 0,
     [r'WARNING VIA_TYPE conflicts with PCB_LAYERS\n\s+VIA_TYPE = "blind" changes nothing: every via joins Top and Bottom',
      r"the TX vias join Top and Bottom: they stay through vias"], [r"ERROR"]),
    ("via_type_blind_single_wiring_tail_pair", {"PCB_LAYERS": 4, "VIA_TYPE": "blind", "VIA_DIAMETER_MM": 0.4,
                                                "VIA_DRILL_MM": 0.15, "RX_LAYER_A": 2, "RX_LAYER_B": 3, "TX_WIRING": "single",
                                                "TX_LAYER_A": 1, "RX_TABS": "none"}, 0,
     [r"the TX vias are blind vias between Top and Inner-1", r"the RX tip vias join Inner-1 and Inner-2: that is a buried via"],
     [r"ERROR"]),
    ("via_type_through_on_four_layers_says_nothing", dict(FOUR, VIA_TYPE="through"), 0, [r"CHECK PASSED"],
     [r"ERROR", r"VIA_TYPE"]),
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
    test.__doc__ = f"{name}: {overrides!r} -> rc {rc}"
    return test


for _case in CASES:
    _name, _ov, _rc, _must, _not = _case[:5]
    _args = _case[5] if len(_case) > 5 else ()
    setattr(CheckerCases, "test_" + _name, _make(_name, _ov, _rc, _must, _not, _args))


class CheckerBehaviour(unittest.TestCase):
    def test_every_error_names_its_file(self):
        """A parameter error says which file the value is in."""
        res = H.check({"LOOPS": 0, "TX_TURNS": 0, "ROTOR_AUTO_DUTY": 2, "IC_MIN_RP_OHM": -1, "VIA_DRILL_MM": 0})
        self.assertEqual(res.rc, 1)
        for file in ("RX_Parameters.py", "TX_Parameters.py", "Rotor_Parameters.py", "IC_Parameters.py", "Board_Parameters.py"):
            self.assertIn(file, res.out)
        self.assertTrue(res.has(r"FAILED: 5 parameter error"), res.out[-600:])

    def test_overrides_do_not_leak_between_runs(self):
        """The harness restores every value: a run after a broken one is the default again."""
        H.check({"LOOPS": 0})
        self.assertEqual(H.P.LOOPS, 1)
        res = H.check()
        self.assertEqual(res.rc, 0)
        self.assertFalse(res.has("WARNING"))

    def test_no_color_output_is_plain(self):
        res = H.check()
        self.assertNotIn("\x1b[", res.out)

    def test_summary_lines_in_check_output(self):
        res = H.check()
        self.assertTrue(res.has(r"\[1/6\] Checking the parameters"))
        self.assertTrue(res.has(r"\[5/6\] Deciding"))
        self.assertFalse(res.has(r"\[6/6\]"), "--check must not reach the writing step")
        self.assertTrue(re.search(r"L = [\d.]+ uH with the rotor away", res.out))


if __name__ == "__main__":
    unittest.main()
