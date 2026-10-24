"""
run_regression.py  -  runs the regression tests of the Dual Generator (from any folder):

    python "Dual Generator/Regression Testing/run_regression.py"                 all tests
    python "Dual Generator/Regression Testing/run_regression.py" -v              one line per test
    python "Dual Generator/Regression Testing/run_regression.py" -k silkscreen   only tests whose name contains it
    python "Dual Generator/Regression Testing/run_regression.py" --update-references
                                                                                   write References/ anew from the
                                                                                   generator as it is now (do this
                                                                                   only after reading the differences
                                                                                   the failing tests printed)
    python "Dual Generator/Regression Testing/run_regression.py" --keep          keep the temporary output folder
                                                                                   (its path is printed)

Exit code 0 when every test passed, 1 otherwise.  Needs Python 3.9 or newer and numpy (see requirements.txt), like the generator.
It writes nothing into the repository except, with --update-references, the References folder.
"""

import argparse
import os
import platform
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the Dual Generator's regression tests.")
    ap.add_argument("-v", "--verbose", action="store_true", help="one line per test")
    ap.add_argument("-k", dest="pattern", default=None, help="run only the tests whose id contains this text")
    ap.add_argument("--update-references", action="store_true", help="rewrite the reference files from this run")
    ap.add_argument("--keep", action="store_true", help="keep the temporary output folder")
    args = ap.parse_args(argv)
    if args.update_references:
        os.environ["REGRESSION_UPDATE_REFERENCES"] = "1"
    if args.keep:
        os.environ["REGRESSION_KEEP_OUTPUT"] = "1"
    sys.dont_write_bytecode = True
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import harness
    import numpy
    print(f"Dual Generator regression tests  -  Python {platform.python_version()} ({platform.system()}), "
          f"numpy {numpy.__version__}")
    print(f"  generator   {harness.PROJECT}")
    print(f"  output      {harness.temp_root()}" + ("  (kept)" if args.keep else "  (removed at the end)"))
    if args.update_references:
        print("  REFERENCES ARE BEING REWRITTEN from this run")
    print()

    loader = unittest.TestLoader()
    suite = loader.discover(HERE, pattern="test_*.py", top_level_dir=HERE)
    if args.pattern:
        suite = _filter(suite, args.pattern)
    t0 = time.time()
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1, stream=sys.stdout).run(suite)
    print(f"\n{result.testsRun} tests in {time.time() - t0:.1f} s: "
          f"{len(result.failures)} failed, {len(result.errors)} errors, {len(result.skipped)} skipped")
    return 0 if result.wasSuccessful() else 1


def _filter(suite, pattern):
    out = unittest.TestSuite()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            out.addTest(_filter(item, pattern))
        elif pattern.lower() in item.id().lower():
            out.addTest(item)
    return out


if __name__ == "__main__":
    sys.exit(main())
