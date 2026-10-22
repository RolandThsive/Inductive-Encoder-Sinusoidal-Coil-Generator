"""
test_boards.py  -  every board case of harness.BOARD_CASES written and compared with its reference in References/:
Stator.kicad_pcb, Rotor.kicad_pcb and Parameters.txt (without the lines that change with every run).  Numbers
must agree within 1e-5, everything else must be identical.

When a difference is intended (the generator was changed on purpose), read the printed differences, then run
    python run_regression.py --update-references
and commit the new References/ together with the change that caused it.
"""

import os
import unittest

import harness as H
import RegressionTools as RT

FILES = ("Stator.kicad_pcb", "Rotor.kicad_pcb", "Parameters.txt")


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
        "default": "DualCoil_7.25_26.875_1x16_4x4",
        "mode1_fitted_bands": "DualCoil_8.5_29.5_1x16_3x3",
        "mode3_rx1_band_gap": "DualCoil_8.5_29.5_1x16_3x3",
        "mode4_all_given": "DualCoil_8.5_29.5_1x16_3x3",
        "parallel_both_sets": "DualCoil_8.5_29.5_1x16_3x3",
        "loops_2x8_rotor_from_board": "DualCoil_7.25_26.875_2x8_4x4",
    }

    def test_folder_names(self):
        for case, name in self.EXPECTED_NAMES.items():
            with self.subTest(case=case):
                self.assertEqual(os.path.basename(H.board(case).folder), name)

    def test_every_case_writes_three_files(self):
        for case in H.BOARD_CASES:
            with self.subTest(case=case):
                res = H.board(case)
                self.assertEqual(sorted(os.listdir(res.folder)), sorted(FILES))
                self.assertTrue(res.has(r"SUCCESS: 2 board file\(s\) \+ Parameters\.txt written"), res.out[-400:])
                self.assertEqual(res.made, [os.path.basename(res.folder)], "exactly one folder per run")

    def test_reference_folder_has_no_strays(self):
        if not os.path.isdir(H.REFERENCES):
            self.skipTest("no References folder yet")
        self.assertEqual(sorted(d for d in os.listdir(H.REFERENCES) if not d.startswith(".")), sorted(H.BOARD_CASES))


if __name__ == "__main__":
    unittest.main()
