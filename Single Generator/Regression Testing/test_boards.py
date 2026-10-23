"""
test_boards.py  -  every board case of harness.BOARD_CASES written and compared with its reference in References/:
Stator.kicad_pcb, Rotor.kicad_pcb and Parameters.txt (without the lines that change with every run).  Numbers
must agree within 1e-5 (the files carry 6 decimals; a different machine may round the last one differently),
everything else must be identical.

When a difference is intended (the generator was changed on purpose), read the printed differences, then run
    python run_regression.py --update-references
and commit the new References/ together with the change that caused it.
"""

import os
import unittest

import harness as H
import RegressionTools as RT

FILES = ("Stator.kicad_pcb", "Rotor.kicad_pcb", "Parameters.txt")
PICTURES = ("_Representative.svg", "_Actual.svg")   # resources/RepresentativeSVGMaker.py, ActualSVGMaker.py


class BoardReferences(unittest.TestCase):
    pass


def _compare(self, case, file):
    res = H.board(case)
    actual = res.text(file)
    if file == "Parameters.txt":
        actual = res.normalised_record
    path = H.reference_path(case, file)
    if H.UPDATE_REFERENCES:
        RT.write_reference(path, actual, compress=file != "Parameters.txt")
        return
    expected = RT.read_reference(path)
    self.assertIsNotNone(expected, f"no reference {path}(.gz): run with --update-references to create it")
    diff = RT.compare_text(expected, actual)
    self.assertFalse(diff, f"{case}/{file} differs from its reference ({len(diff)} shown):\n  " + "\n  ".join(diff))


def _make(case, file):
    def test(self):
        _compare(self, case, file)
    test.__doc__ = f"{case}: {file} equals References/{case}/{file}"
    return test


for _case in H.BOARD_CASES:
    for _file in FILES:
        setattr(BoardReferences, f"test_{_case}__{_file.split('.')[0]}", _make(_case, _file))


class BoardFolders(unittest.TestCase):
    EXPECTED_NAMES = {
        "default": "Coil_15_27_1_1_3_Single_SteppedDiagonal",
        "loops_4_subcoils_2": "Coil_15_27_4_2_3_Single_SteppedDiagonal",
        "loops_16_tabs_single": "Coil_15_27_16_1_3_Single_SteppedDiagonal",
        "four_layer_series": "Coil_15_27_1_1_3_Series_SteppedDiagonal",
        "four_layer_parallel_staggered": "Coil_15_27_1_1_3_Parallel_SteppedDiagonal",
        "spiral_tx": "Coil_15_28.2_1_1_5_Single_Spiral",
        "stepped_arc_tx": "Coil_15_27_1_1_2_Single_SteppedArc",
        "band_from_centre": "Coil_15_27_1_1_3_Single_SteppedDiagonal",
    }

    def test_folder_names(self):
        for case, name in self.EXPECTED_NAMES.items():
            with self.subTest(case=case):
                self.assertEqual(os.path.basename(H.board(case).folder), name)

    def test_every_case_writes_its_files(self):
        for case in H.BOARD_CASES:
            with self.subTest(case=case):
                res = H.board(case)
                name = os.path.basename(res.folder)
                self.assertEqual(sorted(os.listdir(res.folder)), sorted(FILES + tuple(name + s for s in PICTURES)))
                self.assertTrue(res.has(r"SUCCESS: 2 board file\(s\) \+ Parameters\.txt written"), res.out[-400:])
                self.assertEqual(res.made, [os.path.basename(res.folder)], "exactly one folder per run")

    def test_reference_folder_has_no_strays(self):
        """References/ holds one folder per board case and nothing else (a case renamed leaves no orphan)."""
        if not os.path.isdir(H.REFERENCES):
            self.skipTest("no References folder yet")
        self.assertEqual(sorted(d for d in os.listdir(H.REFERENCES) if not d.startswith(".")), sorted(H.BOARD_CASES))


if __name__ == "__main__":
    unittest.main()
