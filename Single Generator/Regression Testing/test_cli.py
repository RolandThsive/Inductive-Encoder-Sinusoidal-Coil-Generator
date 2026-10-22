"""
test_cli.py  -  the generator started the way a user starts it: as a script in a fresh Python process, from the
"Single Generator" folder and from elsewhere, with --check, --help and a bad option.  The in-process tests cannot
see the script's own import-path setup; these do.
"""

import os
import subprocess
import sys
import unittest

import harness as H

SCRIPT = os.path.join(H.PROJECT, "Generator", "Run", "RunCoilGenerator.py")


def run(args, cwd):
    return subprocess.run([sys.executable, "-B", SCRIPT] + args, cwd=cwd, capture_output=True, text=True, timeout=600)


class CommandLine(unittest.TestCase):
    def test_check_from_the_project_folder(self):
        p = run(["--check", "--no-color"], H.PROJECT)
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])
        self.assertIn("CHECK PASSED (--check: no files written)", p.stdout)
        self.assertEqual(p.stderr, "")

    def test_check_from_another_folder(self):
        p = run(["--check", "--no-color"], H.temp_root())
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])
        self.assertIn("CHECK PASSED", p.stdout)

    def test_help_and_bad_option(self):
        p = run(["--help"], H.PROJECT)
        self.assertEqual(p.returncode, 0)
        for opt in ("--check", "--stator", "--rotor", "--no-color"):
            self.assertIn(opt, p.stdout)
        p = run(["--bogus"], H.PROJECT)
        self.assertEqual(p.returncode, 2)
        self.assertIn("unrecognized arguments", p.stderr)

    def test_colour_off_by_pipe(self):
        """Without --no-color the output to a pipe carries no colour codes either."""
        p = run(["--check"], H.PROJECT)
        self.assertEqual(p.returncode, 0)
        self.assertNotIn("\x1b[", p.stdout)

    def test_python_version_is_supported(self):
        self.assertGreaterEqual(sys.version_info[:2], (3, 8))


if __name__ == "__main__":
    unittest.main()
