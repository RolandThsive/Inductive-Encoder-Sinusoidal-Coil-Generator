"""
RunCoilGenerator.py  -  checks the parameters, then writes the stator and the rotor.
This is the only program that writes boards.

    python Generator/Run/RunCoilGenerator.py              check, then write Stator + Rotor
    python Generator/Run/RunCoilGenerator.py --check      check only, write nothing (with --stator: as the
                                                          --stator run, the rotor is not checked)
    python Generator/Run/RunCoilGenerator.py --stator     only the stator
    python Generator/Run/RunCoilGenerator.py --rotor      only the rotor (needs the stator geometry, but does not
                                                          write it)
    python Generator/Run/RunCoilGenerator.py --no-color   plain text
(from the "Single Generator" folder)

Colours: red = error (nothing is written), yellow = warning, green = success.

Steps (the chain: every step reads only what the steps before it made)
  1. CheckParameters.check_parameters    rules on the parameter values (ParameterRules.py, ConflictRules.py)
  2. RX_Builder.build_rx                 the RX coils and their fingers (from the parameters alone)
     TX_Builder.build_tx                 the TX coil, its terminal where it keeps the largest gap from the RX
     StatorAssembly.assemble             the board, turned so that the TX terminal sits at 0 deg (the right)
     DesignChecks                        the clearances of the finished copper, the outline, the page
  3. build the rotor, check again
  4. TX_Electrics.estimate              TX inductance, tank capacitors and oscillator frequency,
                                         checked against IC_Parameters.py (an estimate: it never changes
                                         the boards, its warnings count like the others)
  5. decide (GENERATOR_MODE, --check): in "strict" mode every warning about the finished boards (steps 2
     and 3) counts as an error and nothing is written
  6. write the files - only if no step reported an error.  OutputFolders.py makes a new
     folder for every run inside OUTPUT_DIR (the Output folder in "Single Generator"),
         Coil_<board inside radius>_<board outside radius>_<RX loops>_<RX sub-coils>_<TX turns>_<TX wiring>_<TX shape>
     e.g. Coil_15_27_1_1_3_Single_SteppedDiagonal (TX wiring: Single, Series or Parallel; TX shape:
     SteppedDiagonal, SteppedArc or Spiral), with __1, __2, ... added when that name exists already, and writes Stator.kicad_pcb,
     Rotor.kicad_pcb and Parameters.txt (every value used, the summaries, the electrical estimate
     and copies of the parameter files) into it.  Nothing is ever overwritten.

All settings are in Board_Parameters.py, RX_Parameters.py, TX_Parameters.py, Rotor_Parameters.py and
IC_Parameters.py (the Parameters folder).  Run it from any folder, e.g. from the "Single Generator" folder:
    python Generator/Run/RunCoilGenerator.py
(project layout: wiki page "Project Output Organization", docs/wiki/Project-Output-Organization.md;
overview in README.md in the top folder).
"""

import argparse
import contextlib
import io
import os
import sys

if __package__ in (None, ""):                      # started as a script: make the Generator package importable
    _SINGLE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _SINGLE not in sys.path:
        sys.path.insert(0, _SINGLE)

from Generator.Checks import DesignChecks                               # noqa: E402
from Generator.Core.Conflict import Colour, Report                      # noqa: E402
from Generator.Run import OutputFolders as OF                           # noqa: E402
from Generator.Run.CheckParameters import check_parameters              # noqa: E402


def step(n, total, text):
    print(Colour.bold(f"[{n}/{total}] {text}"))


def stop(why):
    print()
    print(Colour.red(f"FAILED: {why}. Nothing was written."))
    return 1


def captured_warnings(text):
    """The generator's own 'WARNING: ...' lines (stderr) as report items (DesignChecks.classify_generator_output)."""
    return DesignChecks.classify_generator_output(text)


def electrical(P, stator, rotor, RB, n, total):
    """Step n: print the electrical estimate (TX_Electrics.py).  Returns (warning texts, one-line summary or
    None, report lines for Parameters.txt).  It never stops a generation: if it cannot be made, a note says why
    and the boards are written."""
    if rotor is None:                                  # --stator: the rotor is built only for the estimate
        try:
            rotor = RB.RotorDesign(P, stator=stator)
        except Exception:
            rotor = None
    try:
        from Generator.Stator.TX import TX_Electrics as TXE
        el = TXE.estimate(stator, rotor, P)
    except Exception as e:
        step(n, total, "Electrical estimate")
        why = f"the electrical estimate could not be made ({type(e).__name__}: {e}); the boards are not affected"
        print("  " + Colour.yellow(why))
        return [], None, ["ELECTRICAL ESTIMATE", "  " + why]
    step(n, total, f"Electrical estimate  ({el.heading()})")
    for line in el.lines(title=False):
        print(line)
    rep = Report()
    rep.items = [(level, msg, ()) for level, _code, msg in el.findings]
    rep.print()
    record = el.lines(title=True) + [f"  {level.upper():8s}{msg}" for level, _code, msg in el.findings]
    return rep.warnings, el.summary(), record


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check the parameters, then generate the stator and rotor.")
    ap.add_argument("--check", action="store_true", help="check the parameters and the geometry, write nothing")
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
        return stop("parameter files cannot be loaded")
    rep = check_parameters(P)
    rep.print()
    warn_texts = list(rep.warnings)                                    # for the record in the output folder
    if rep.errors:
        return stop(f"{len(rep.errors)} parameter error(s)")
    print("  " + Colour.green("parameters OK"))
    strict = str(getattr(P, "GENERATOR_MODE", "normal")).strip().lower() == "strict"

    # ---------------------------------------------------------------- 2. stator
    from Generator.Stator import StatorAssembly
    from Generator.Stator.RX import RX_Builder
    from Generator.Stator.TX import TX_Builder
    from Generator.Rotor import RotorBuilder as RB
    step(2, total, "Building the stator")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            # THE CHAIN.  THE RX READS ONLY THE PARAMETERS; THE TX READS THE RX (ITS FINGERS AND ITS COPPER, TO FIND
            # THE PLACE FOR ITS TERMINAL); THE ASSEMBLY TURNS THE BOARD SO THAT THE TERMINAL SITS AT 0 DEG (THE RIGHT);
            # THE CHECKS MEASURE THE RESULT.  NOTHING GOES BACKWARDS AND NOTHING IS ESTIMATED.
            rx = RX_Builder.build_rx(P)
            tx = TX_Builder.build_tx(rx)
            DesignChecks.check_tx_terminal(tx)
            stator = StatorAssembly.assemble(P, rx, tx)
            DesignChecks.check_stator_clearances(stator)
    except (ValueError, RuntimeError) as e:
        failed = Report()
        failed.add_exception(e)
        failed.print()
        return stop("the stator cannot be built")
    gen_rep = captured_warnings(buf.getvalue())
    design_rep = DesignChecks.check_design(P, stator)
    gen_rep.extend(design_rep)
    gen_rep.print()
    all_warn = len(rep.warnings) + len(gen_rep.warnings)
    board_warn = len(gen_rep.warnings)                                  # warnings about the finished boards
    warn_texts += gen_rep.warnings
    if gen_rep.errors:
        return stop(f"{len(gen_rep.errors)} geometry error(s)")
    print("  " + Colour.green("stator built"))

    # ---------------------------------------------------------------- 3. rotor
    step(3, total, "Building the rotor")
    try:
        # (--stator --check follows the --stator run: the rotor is not built or checked; the estimate in step 4
        # still builds one for itself)
        rotor = RB.RotorDesign(P, stator=stator) if want_rotor else None
    except (ValueError, RuntimeError) as e:
        failed = Report()
        failed.add_exception(e)
        failed.print()
        return stop("the rotor cannot be built")
    if rotor is not None:
        rot_rep = DesignChecks.check_design(P, stator, rotor)
        # only the rotor's own notes are new here (the stator findings were shown above)
        rot_rep.items = [it for it in rot_rep.items if it not in gen_rep.items]
        rot_rep.print()
        all_warn += len(rot_rep.warnings)
        board_warn += len(rot_rep.warnings)
        warn_texts += rot_rep.warnings
        if rot_rep.errors:
            return stop(f"{len(rot_rep.errors)} rotor error(s)")
        print("  " + Colour.green("rotor built"))
    else:
        print("  " + Colour.dim("--stator: the rotor is not written"))

    # ---------------------------------------------------------------- 4. electrical estimate
    el_warn, el_summary, el_record = electrical(P, stator, rotor, RB, 4, total)
    all_warn += len(el_warn)

    # ---------------------------------------------------------------- 5. strict / check-only
    step(5, total, "Deciding")
    if strict and board_warn:
        print("  " + Colour.red(f'GENERATOR_MODE = "strict": {board_warn} warning(s) about the boards count as errors'))
        return stop(f"{board_warn} board warning(s) in strict mode")
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
        folder = OF.create_output_folder(stator, P)
        print(f"  folder  {folder}")
        if want_stator:
            path = stator.write(os.path.join(folder, P.STATOR_FILE))
            written.append(path)
            print("  " + Colour.green(f"stator  -> {path}"))
        if want_rotor:
            path = rotor.write(os.path.join(folder, P.ROTOR_FILE))
            written.append(path)
            print("  " + Colour.green(f"rotor   -> {path}"))
        path = OF.write_record(folder, P, written, stator=stator, rotor=rotor if want_rotor else None,
                                electrical_lines=el_record, warnings=warn_texts + list(el_warn),
                                command="python Generator/Run/RunCoilGenerator.py "
                                        + " ".join(sys.argv[1:] if argv is None else argv))
        print("  " + Colour.green(f"record  -> {path}"))
    except OSError as e:
        print("  " + Colour.red(f"ERROR   cannot write: {e}"))
        if not written:
            OF.remove_if_empty(folder)
            return stop("cannot write the files")
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
    print(Colour.green(f"SUCCESS: {len(written)} board file(s) + {OF.RECORD_FILE} written to {folder}")
          + (Colour.yellow(f"  ({all_warn} warning(s) above)") if all_warn else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
