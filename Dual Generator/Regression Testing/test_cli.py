"""
test_cli.py  -  the dual generator started the way a user starts it: as a script in a fresh Python process, from
the "Dual Generator" folder and from elsewhere, with --check, --help and a bad option; the checker on its own
(Dual_CheckParameters.py); and the promise that a dual run leaves no __pycache__ in the Single Generator.
"""

import os
import subprocess
import sys
import unittest

import harness as H

SCRIPT = os.path.join(H.PROJECT, "Dual_Generator", "Run", "Dual_RunCoilGenerator.py")
CHECKER = os.path.join(H.PROJECT, "Dual_Generator", "Checks", "Dual_CheckParameters.py")


def run(script, args, cwd):
    return subprocess.run([sys.executable, script] + args, cwd=cwd, capture_output=True, text=True, timeout=900)


class CommandLine(unittest.TestCase):
    def test_check_from_the_project_folder(self):
        p = run(SCRIPT, ["--check", "--no-color"], H.PROJECT)
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])
        self.assertIn("CHECK PASSED (--check: no files written)", p.stdout)
        self.assertIn("layout: DUAL_MODE = 2", p.stdout)
        self.assertEqual(p.stderr, "")

    def test_check_from_another_folder(self):
        p = run(SCRIPT, ["--check", "--no-color"], H.temp_root())
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])
        self.assertIn("CHECK PASSED", p.stdout)

    def test_help_and_bad_option(self):
        p = run(SCRIPT, ["--help"], H.PROJECT)
        self.assertEqual(p.returncode, 0)
        for opt in ("--check", "--stator", "--rotor", "--no-color"):
            self.assertIn(opt, p.stdout)
        p = run(SCRIPT, ["--bogus"], H.PROJECT)
        self.assertEqual(p.returncode, 2)
        self.assertIn("unrecognized arguments", p.stderr)

    def test_checker_script_on_its_own(self):
        p = run(CHECKER, [], H.PROJECT)
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])

    def test_no_pycache_left_anywhere(self):
        """The dual scripts set sys.dont_write_bytecode: a run leaves no new __pycache__ in the Single Generator,
        the dual generator or the test folders."""
        try:
            before = subprocess.run(["git", "status", "--porcelain", "--", H.REPO], capture_output=True, text=True,
                                    cwd=H.REPO, timeout=30)
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git is not available")
        if before.returncode != 0:
            self.skipTest("not a git checkout")
        run(SCRIPT, ["--check", "--no-color"], H.PROJECT)
        after = subprocess.run(["git", "status", "--porcelain", "--", H.REPO], capture_output=True, text=True, cwd=H.REPO).stdout
        strays = [l for l in after.splitlines() if "__pycache__" in l or l.endswith(".pyc")]
        self.assertEqual(strays, [])


if __name__ == "__main__":
    unittest.main()
