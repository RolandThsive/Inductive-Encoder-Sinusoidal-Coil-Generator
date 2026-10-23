"""
Dual_CheckParameters.py  -  checks the dual parameter files without generating anything:

    python Dual_Generator/Checks/Dual_CheckParameters.py        (from the "Dual Generator" folder)

In this order:
  1. Dual_ParameterRules.check_files       every name in its file, nothing missing, nothing that does not belong
     Dual_ParameterRules.check_fixed       Dual_Fixed_Parameters.py holds exactly the fixed values
  2. Dual_ParameterRules.check_dual_values the dual-only values (gaps, split, angles)
  3. Dual_ParameterRules.dual_rules        the rules between the two sets
  4. Dual_TrackLayout.resolve             the mode, the two bands, the bore, the outline, the gap
  5. the Single Generator's own check_parameters on each set, in the Single Generator's names (every rule about a
     set on its own: present, in range, settings that cannot hold together), its findings prefixed "set 1:" /
     "set 2:" with the dual file names

Dual_RunCoilGenerator.py runs the same check_parameters before it builds anything; the checks on the finished
boards are in Dual_DesignChecks.py (and the Single Generator's DesignChecks.py for each set).

Findings have three levels: ERROR (nothing is written), WARNING (the board can be made, read it), INFO.
"""

import os
import sys

sys.dont_write_bytecode = True                      # no __pycache__ anywhere, in the Single Generator least of all

if __package__ in (None, ""):                      # started as a script: make the Dual_Generator package importable
    _DUAL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _DUAL not in sys.path:
        sys.path.insert(0, _DUAL)

import Dual_Generator  # noqa: E402,F401   (puts the Parameters folder and the Single Generator on the path)
from Generator.Core.Conflict import Colour, ParameterConflict, Report              # noqa: E402
from Generator.Run.CheckParameters import check_parameters as single_check         # noqa: E402

from Dual_Generator.Checks import Dual_ParameterRules as DR                        # noqa: E402
from Dual_Generator.Core import Dual_SetParameters as SP                           # noqa: E402
from Dual_Generator.Core import Dual_TrackLayout as TL                             # noqa: E402


def check_parameters(P):
    """Every rule on the dual parameter values.  Returns (Report, Layout or None when the layout could not be
    worked out); the values themselves are never changed."""
    rep = Report()
    DR.check_files(P, rep)
    DR.check_fixed(P, rep)
    v = DR.check_dual_values(P, rep)
    lacking = SP.names_the_single_wants_but_the_dual_lacks()
    if lacking:
        rep.error("the Single Generator has parameters that the dual generator does not supply: "
                  + ", ".join(lacking) + " (the Single Generator gained them; add them to Dual_SetParameters.py)")
    DR.dual_rules(P, v, rep)
    if rep.errors:
        return rep, None
    try:
        layout = TL.resolve(P)
    except ParameterConflict as e:
        rep.add_exception(e)
        return rep, None
    except (TypeError, ValueError, AttributeError) as e:
        # a value the layout reads is not a number (None, a string): the Single Generator's per-set checks name
        # it, on each set's own file values (the band and edge names are the layout's business, not reported here)
        skip = set(SP.BAND_NAMES + SP.EDGE_NAMES)
        named = False
        for k in (1, 2):
            for level, msg, names in single_check(SP.build(P, k)).items:
                if level == "error" and not (set(names) & skip) and not msg.startswith(tuple(skip)):
                    rep.add(level, f"set {k}: " + SP.rename_single_files(msg, k), names)
                    named = True
        if not named:
            rep.error(f"the layout of the two sets cannot be worked out (a setting is not a number: {e})")
        return rep, None
    for line in layout.lines():
        rep.info(line)
    for k in (1, 2):
        Pk = SP.build(P, k, layout.set_band(k), layout.edges())
        r = single_check(Pk)
        for level, msg, names in r.items:
            if "OUTPUT_DIR" in msg:                  # the dual checks its own output folder (dual_rules)
                continue
            rep.add(level, f"set {k}: " + SP.rename_single_files(msg, k), names)
    return rep, layout


def main():
    Colour.setup()
    import Dual_Parameters as P
    r, _layout = check_parameters(P)
    r.print()
    if r.errors:
        print(Colour.red(f"{len(r.errors)} error(s) - fix the parameters before generating"))
        return 1
    print(Colour.green("Parameters OK") + (Colour.yellow(f" ({len(r.warnings)} warning(s))") if r.warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
