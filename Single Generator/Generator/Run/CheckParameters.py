"""
CheckParameters.py  -  checks the parameter files without generating anything:

    python Generator/Run/CheckParameters.py        (from the "Single Generator" folder)

Two kinds of rules, in this order: ParameterRules.py (every parameter on its own: present, the right kind of value,
in range) and ConflictRules.py (settings that cannot hold together).  RunCoilGenerator.py runs the same
check_parameters before it builds anything; the checks on the finished boards are in DesignChecks.py.

Findings have three levels:
  ERROR    the board would be wrong or impossible - nothing is written
  WARNING  the board can be made, but something is likely to be a problem
  INFO     plain facts worth knowing (printed without colour)
Thresholds named "typical" are general PCB-fab rules of thumb, not the limits of any particular manufacturer.
"""

import os
import sys

if __package__ in (None, ""):                      # started as a script: make the Generator package importable
    _SINGLE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _SINGLE not in sys.path:
        sys.path.insert(0, _SINGLE)

from Generator.Checks import ConflictRules, ParameterRules                # noqa: E402
from Generator.Core.Conflict import Colour, Report                       # noqa: E402


def check_parameters(P):
    """Every rule on the parameter values.  Returns a Report; the values themselves are never changed."""
    rep = Report()
    v = ParameterRules.load_values(P, rep)
    ParameterRules.single_value_warnings(v, rep)
    ConflictRules.check(P, v, rep)
    return rep


def main():
    Colour.setup()
    import Parameters as P
    r = check_parameters(P)
    r.print()
    if r.errors:
        print(Colour.red(f"{len(r.errors)} error(s) - fix the parameters before generating"))
        return 1
    print(Colour.green("Parameters OK") + (Colour.yellow(f" ({len(r.warnings)} warning(s))") if r.warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
