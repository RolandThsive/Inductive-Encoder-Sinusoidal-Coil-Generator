"""
RunCoilGenerator.py  -  checks the parameters, then writes the stator and the rotor.
This is the only program that writes boards (StatorGenerator.py / RotorGenerator.py no longer do).

    python RunCoilGenerator.py              check, then write Stator + Rotor
    python RunCoilGenerator.py --check      check only, write nothing
    python RunCoilGenerator.py --strict     treat warnings as errors (nothing is written if any)
    python RunCoilGenerator.py --stator     only the stator
    python RunCoilGenerator.py --rotor      only the rotor (needs the stator geometry, but does not write it)
    python RunCoilGenerator.py --no-color   plain text

Colours: red = error (nothing is written), yellow = warning, green = success.

Steps
  1. ParameterChecker.check_parameters   rules on the parameter values
  2. build the stator                    (the generator's own clearance warnings are shown here),
     ParameterChecker.check_design       rules on the finished geometry
  3. build the rotor, check again
  4. CoilElectrics.estimate              TX inductance, tank capacitors, oscillator frequency and
                                         receiver voltage, checked against RECEIVER_IC (an estimate:
                                         it never changes the boards, its warnings count like the others)
  5. decide (--strict, --check)
  6. write the files - only if no step reported an error.  OutputDirectoryManager.py makes a new
     folder for every run inside OUTPUT_DIR (the Output folder of the project),
         Coil_<board inside radius>_<board outside radius>_<RX loops>_<RX sub-coils>_<TX turns>_<TX wiring>_<TX shape>
     e.g. Coil_36.8_56.6_8_1_3_Single_Stepped (TX wiring: Single, Series or Parallel; TX shape: Stepped or
     Spiral), with __1, __2, ... added when that name exists already, and writes Stator.kicad_pcb,
     Rotor.kicad_pcb and Parameters.txt (every value used, the summaries, the electrical estimate
     and copies of the parameter files) into it.  Nothing is ever overwritten.

All settings are in Board_Parameters.py, RX_Parameters.py, TX_Parameters.py and
Rotor_Parameters.py (the Parameters folder).  Run it from any folder, e.g. from the project folder:
    python Generator/RunCoilGenerator.py
(project layout: README.txt in the project folder).
"""

import argparse
import contextlib
import io
import os
import sys

# The project folders sit next to each other: Parameters, Generator, Analyser_And_Optimizer (and Output).
# Put all three on the import path, so every program runs from any folder.  (All files in one folder works too.)
_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ("Analyser_And_Optimizer", "Generator", "Parameters"):
    _p = os.path.join(_PROJECT, _sub)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ParameterChecker as PC                      # noqa: E402
import OutputDirectoryManager as ODM                # noqa: E402
from ParameterChecker import Colour                 # noqa: E402


def step(n, total, text):
    print(Colour.bold(f"[{n}/{total}] {text}"))


def stop(rep_count, why):
    print()
    print(Colour.red(f"FAILED: {why}. Nothing was written."))
    return 1


def captured_warnings(text):
    """The generator's own 'WARNING: ...' lines (stderr) as report items (rules live in ParameterChecker)."""
    return PC.classify_generator_output(text)


def electrical(P, stator, rotor, RG, n, total):
    """Step n: print the electrical estimate (CoilElectrics.py).  Returns (warning texts, one-line summary or
    None, report lines for Parameters.txt).  It never stops a generation: if it cannot be made, a note says why
    and the boards are written."""
    if rotor is None:                                  # --stator: the rotor is built only for the estimate
        try:
            rotor = RG.RotorDesign(P, stator=stator)
        except Exception:
            rotor = None
    try:
        import CoilElectrics as CE
        el = CE.estimate(stator, rotor, P)
    except Exception as e:
        step(n, total, "Electrical estimate")
        why = f"the electrical estimate could not be made ({type(e).__name__}: {e}); the boards are not affected"
        print("  " + Colour.yellow(why))
        return [], None, ["ELECTRICAL ESTIMATE", "  " + why]
    step(n, total, f"Electrical estimate  ({el.heading()})")
    for line in el.lines(title=False):
        print(line)
    rep = PC.Report()
    rep.items = [(level, msg) for level, _code, msg in el.findings]
    rep.print()
    record = el.lines(title=True) + [f"  {level.upper():8s}{msg}" for level, _code, msg in el.findings]
    return rep.warnings, el.summary(), record


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check the parameters, then generate the stator and rotor.")
    ap.add_argument("--check", action="store_true", help="check the parameters and the geometry, write nothing")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--stator", action="store_true", help="write only the stator")
    ap.add_argument("--rotor", action="store_true", help="write only the rotor")
    ap.add_argument("--no-color", action="store_true", help="no colours")
    args = ap.parse_args(argv)
    Colour.setup(False if args.no_color else None)
    want_stator = args.stator or not args.rotor
    want_rotor = args.rotor or not args.stator
    total = 6

    # ---------------------------------------------------------------- 1. parameters
    step(1, total, "Checking the parameters")
    try:
        import Parameters as P
    except Exception as e:                                             # syntax error, missing file ...
        print("  " + Colour.red(f"ERROR   the parameter files cannot be loaded: {type(e).__name__}: {e}"))
        return stop(1, "parameter files cannot be loaded")
    rep = PC.check_parameters(P)
    rep.print()
    warn_texts = list(rep.warnings)                                    # for the record in the output folder
    if rep.errors:
        return stop(len(rep.errors), f"{len(rep.errors)} parameter error(s)")
    print("  " + Colour.green("parameters OK"))

    # ---------------------------------------------------------------- 2. stator
    import StatorGenerator as SG
    import RotorGenerator as RG
    step(2, total, "Building the stator")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            stator = SG.StatorDesign(P)
    except (ValueError, RuntimeError) as e:
        print("  " + Colour.red(f"ERROR   the stator cannot be built: {e}"))
        return stop(1, "stator cannot be built")
    gen_rep = captured_warnings(buf.getvalue())
    design_rep = PC.check_design(P, stator)
    gen_rep.extend(design_rep)
    gen_rep.print()
    all_warn = len(rep.warnings) + len(gen_rep.warnings)
    warn_texts += gen_rep.warnings
    if gen_rep.errors:
        return stop(len(gen_rep.errors), f"{len(gen_rep.errors)} geometry error(s)")
    print("  " + Colour.green("stator built"))

    # ---------------------------------------------------------------- 3. rotor
    step(3, total, "Building the rotor")
    try:
        rotor = RG.RotorDesign(P, stator=stator) if want_rotor or args.check else None
    except (ValueError, RuntimeError) as e:
        print("  " + Colour.red(f"ERROR   the rotor cannot be built: {e}"))
        return stop(1, "rotor cannot be built")
    if rotor is not None:
        rot_rep = PC.check_design(P, stator, rotor)
        # only the rotor's own notes are new here (the stator findings were shown above)
        rot_rep.items = [(l, m) for l, m in rot_rep.items if (l, m) not in gen_rep.items]
        rot_rep.print()
        all_warn += len(rot_rep.warnings)
        warn_texts += rot_rep.warnings
        if rot_rep.errors:
            return stop(len(rot_rep.errors), f"{len(rot_rep.errors)} rotor error(s)")
        print("  " + Colour.green("rotor built"))
    else:
        print("  " + Colour.dim("--stator: the rotor is not written"))

    # ---------------------------------------------------------------- 4. electrical estimate
    el_warn, el_summary, el_record = electrical(P, stator, rotor, RG, 4, total)
    all_warn += len(el_warn)

    # ---------------------------------------------------------------- 5. strict / check-only
    step(5, total, "Deciding")
    if args.strict and all_warn:
        print("  " + Colour.red(f"--strict: {all_warn} warning(s) count as errors"))
        return stop(all_warn, f"{all_warn} warning(s) in strict mode")
    if all_warn:
        print("  " + Colour.yellow(f"{all_warn} warning(s) - the files can still be written; read them first"))
    else:
        print("  " + Colour.green("no warnings"))
    if args.check:
        print()
        print(Colour.green("CHECK PASSED") + " (--check: no files written)")
        return 0

    # ---------------------------------------------------------------- 6. write
    step(6, total, "Writing the files")
    written, folder = [], None
    try:
        folder = ODM.create_output_folder(stator, P)
        print(f"  folder  {folder}")
        if want_stator:
            path = stator.write(os.path.join(folder, P.STATOR_FILE))
            written.append(path)
            print("  " + Colour.green(f"stator  -> {path}"))
        if want_rotor:
            path = rotor.write(os.path.join(folder, P.ROTOR_FILE))
            written.append(path)
            print("  " + Colour.green(f"rotor   -> {path}"))
        path = ODM.write_record(folder, P, written, stator=stator, rotor=rotor if want_rotor else None,
                                electrical_lines=el_record, warnings=warn_texts + list(el_warn),
                                command="python RunCoilGenerator.py " + " ".join(sys.argv[1:] if argv is None else argv))
        print("  " + Colour.green(f"record  -> {path}"))
    except OSError as e:
        print("  " + Colour.red(f"ERROR   cannot write: {e}"))
        if not written:
            ODM.remove_if_empty(folder)
            return stop(1, "cannot write the files")
        print()
        print(Colour.red(f"FAILED: only {', '.join(os.path.basename(p) for p in written)} was written to {folder}."))
        return 1

    print()
    if want_stator:
        print(stator.summary())
    if want_rotor:
        print(rotor.summary())
    if el_summary:
        print(f"Electrical (estimate, step 4): {el_summary}")
    print()
    print(Colour.green(f"SUCCESS: {len(written)} board file(s) + {ODM.RECORD_FILE} written to {folder}")
          + (Colour.yellow(f"  ({all_warn} warning(s) above)") if all_warn else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
