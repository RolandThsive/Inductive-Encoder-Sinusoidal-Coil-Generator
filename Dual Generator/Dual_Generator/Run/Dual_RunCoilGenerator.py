"""
Dual_RunCoilGenerator.py  -  checks the dual parameters, then writes the dual stator and the rotor disc.
This is the only program of the dual generator that writes boards.

    python Dual_RunCoilGenerator.py              check, then write Stator + Rotor
    python Dual_RunCoilGenerator.py --check      check only, write nothing
    python Dual_RunCoilGenerator.py --stator     only the stator
    python Dual_RunCoilGenerator.py --rotor      only the rotor (needs the stator geometry, but does not write it)
    python Dual_RunCoilGenerator.py --no-color   plain text

Colours: red = error (nothing is written), yellow = warning, green = success.

Steps (the same six as the Single Generator's RunCoilGenerator.py, each done twice where there are two sets)
  1. Dual_CheckParameters.check_parameters   the dual rules, the mode (Dual_TrackLayout), then the Single
                                             Generator's own parameter checks on each set
  2. the Single Generator's chain for each set (RX -> TX -> assemble -> clearances, DesignChecks), set 1 turned
     so that its TX ends sit at TERMINAL_1_DEG and set 2 at TERMINAL_2_DEG; then Dual_StatorAssembler puts the
     two sets on one board and Dual_DesignChecks measures the gap between them on the built copper
  3. the Single Generator's rotor for each set (its ring), then Dual_RotorBuilder puts the two rings on one disc
     and Dual_DesignChecks measures the gap between the rings
  4. TX_Electrics.estimate for each set (each set with its own TX, rotor ring and IC; the other set is not in
     the estimate)
  5. decide (GENERATOR_MODE, --check)
  6. write the files - only if no step reported an error.  Dual_OutputFolders.py makes a new folder for every
     run inside OUTPUT_DIR and writes Stator.kicad_pcb, Rotor.kicad_pcb and Parameters.txt into it.
     Last, Dual_LeadCutting_SilkscreenSuggestion.py draws the lead-cutting suggestion (where to break each RX
     coil, where the TX ends get their vias) on the silkscreen of the written stator file and adds it to the record.
     When both boards were written, resources/RepresentativeSVGMaker.py and resources/ActualSVGMaker.py draw them
     as <folder name>_Representative.svg and <folder name>_Actual.svg in the same folder; a missing file or a failed
     picture is only a warning.

All settings are in the Dual_..._Parameters.py files (the Parameters folder; Dual_Parameters.py lists them).  Run
it from any folder, e.g.
from the "Dual Generator" folder:
    python Dual_Generator/Run/Dual_RunCoilGenerator.py
The Single Generator's code does every piece of geometry; nothing in it is changed.
"""

import argparse
import contextlib
import io
import os
import sys

sys.dont_write_bytecode = True                      # no __pycache__ anywhere, in the Single Generator least of all

if __package__ in (None, ""):                      # started as a script: make the Dual_Generator package importable
    _DUAL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _DUAL not in sys.path:
        sys.path.insert(0, _DUAL)

import Dual_Generator  # noqa: E402,F401   (puts the Parameters folder and the Single Generator on the path)
from Generator.Checks import DesignChecks                                           # noqa: E402
from Generator.Core.Conflict import Colour, Report                                  # noqa: E402

from Dual_Generator.Checks import Dual_DesignChecks as DDC                          # noqa: E402
from Dual_Generator.Checks.Dual_CheckParameters import check_parameters             # noqa: E402
from Dual_Generator.Core import Dual_SetParameters as SP                            # noqa: E402
from Dual_Generator.Run import Dual_OutputFolders as OF                             # noqa: E402


RESOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                         "resources")
SVG_MAKERS = ("RepresentativeSVGMaker.py", "ActualSVGMaker.py")       # each has make_svg(folder)


def draw_pictures(folder):
    """The SVG pictures of the written board (resources/RepresentativeSVGMaker.py and ActualSVGMaker.py).  Extras: when
    a file is missing or anything goes wrong, a yellow warning is printed and the run goes on.  Returns the number of
    warnings printed."""
    import importlib.util
    warned = 0
    for name in SVG_MAKERS:
        try:
            path = os.path.join(RESOURCES, name)
            if not os.path.isfile(path):
                raise FileNotFoundError(f"{name} not found in resources")
            spec = importlib.util.spec_from_file_location(os.path.splitext(name)[0], path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            print("  " + Colour.green(f"picture -> {mod.make_svg(folder)}"))
        except Exception as e:
            print("  " + Colour.yellow(f"WARNING picture not made by {name}: {e}; the boards are not affected"))
            warned += 1
    return warned


SET_WORD = {1: "set 1 (inner)", 2: "set 2 (outer)"}


def step(n, total, text):
    print(Colour.bold(f"[{n}/{total}] {text}"))


def stop(why):
    print()
    print(Colour.red(f"FAILED: {why}. Nothing was written."))
    return 1


def narrow_band_hint(layout):
    """DUAL_MODE 1 fits the bands into whatever is left between the edges; when a set cannot be built, the usual
    reason is that the leftover was too little for its vias."""
    if layout.mode != 1:
        return
    w1 = layout.band1["ro"] - layout.band1["ri"]
    w2 = layout.band2["ro"] - layout.band2["ri"]
    print("  " + Colour.yellow(f"hint    DUAL_MODE 1 fitted the RX bands into the room between the board edges: RX1 came out "
                               f"{w1:.2f} mm wide, RX2 {w2:.2f} mm. If the errors above are vias touching copper, the "
                               f"bands are too narrow: raise OUTER_EDGE_RADIUS_MM, lower INNER_EDGE_RADIUS_MM, or move "
                               f"BAND_SPLIT towards the set that failed"))


def prefixed(rep, k):
    """The report's items with 'set k: ' in front and the dual file names."""
    out = Report()
    out.items = [(level, f"set {k}: " + SP.rename_single_files(msg, k), names) for level, msg, names in rep.items]
    return out


def electrical(Pk, k, stator, rotor, RB):
    """The electrical estimate of one set (TX_Electrics.py).  Returns (warning texts, summary or None, record lines).
    It never stops a generation."""
    if rotor is None:
        try:
            rotor = RB.RotorDesign(Pk, stator=stator)
        except Exception:
            rotor = None
    try:
        from Generator.Stator.TX import TX_Electrics as TXE
        el = TXE.estimate(stator, rotor, Pk)
    except Exception as e:
        why = f"the electrical estimate of {SET_WORD[k]} could not be made ({type(e).__name__}: {e}); the boards are not affected"
        print("  " + Colour.yellow(why))
        return [], None, ["ELECTRICAL ESTIMATE", "  " + why]
    print("  " + Colour.bold(f"{SET_WORD[k]}: {el.heading()}"))
    for line in el.lines(title=False):
        print("  " + line)
    rep = Report()
    rep.items = [(level, f"set {k}: {msg}", ()) for level, _code, msg in el.findings]
    rep.print()
    record = el.lines(title=True) + [f"  {level.upper():8s}{msg}" for level, _code, msg in el.findings]
    record.append("  (each set is estimated on its own: the other set's TX ring and rotor ring are not in the estimate)")
    return rep.warnings, el.summary(), record


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check the dual parameters, then generate the dual stator and the rotor disc.")
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
        import Dual_Parameters as P
    except Exception as e:
        print("  " + Colour.red(f"ERROR   the parameter files cannot be loaded: {type(e).__name__}: {e}"))
        return stop("parameter files cannot be loaded")
    rep, layout = check_parameters(P)
    rep.print()
    warn_texts = list(rep.warnings)
    if rep.errors or layout is None:
        return stop(f"{len(rep.errors)} parameter error(s)")
    print("  " + Colour.green("parameters OK"))
    strict = str(getattr(P.BOARD, "GENERATOR_MODE", "normal")).strip().lower() == "strict"
    sets = {k: SP.build(P, k, layout.set_band(k), layout.edges()) for k in (1, 2)}
    terminal = {1: float(P.BOARD.TERMINAL_1_DEG), 2: float(P.BOARD.TERMINAL_2_DEG)}

    # ---------------------------------------------------------------- 2. stator
    from Generator.Rotor import RotorBuilder as RB
    from Dual_Generator.Stator import Dual_StatorAssembler as DSA
    from Dual_Generator.Stator import Dual_LeadCutting_SilkscreenSuggestion as LCS
    from Dual_Generator.Rotor import Dual_RotorBuilder as DRB
    step(2, total, "Building the stator: the two sets, each by the Single Generator, then the board")
    stators, gen_rep = {}, Report()
    for k in (1, 2):
        buf = io.StringIO()
        try:
            with contextlib.redirect_stderr(buf):
                stators[k] = DSA.build_set(sets[k], terminal[k])
        except (ValueError, RuntimeError) as e:
            failed = Report()
            failed.add_exception(e)
            prefixed(failed, k).print()
            narrow_band_hint(layout)
            return stop(f"{SET_WORD[k]} cannot be built")
        r = DesignChecks.classify_generator_output(buf.getvalue())
        r.extend(DesignChecks.check_design(sets[k], stators[k]))
        gen_rep.extend(prefixed(r, k))
    dual = DSA.assemble(P, layout, stators[1], stators[2])
    sets_rep, _gap = DDC.check_sets(P, layout, stators[1], stators[2])
    gen_rep.extend(sets_rep)
    gen_rep.print()
    all_warn = len(rep.warnings) + len(gen_rep.warnings)
    board_warn = len(gen_rep.warnings)
    warn_texts += gen_rep.warnings
    if gen_rep.errors:
        narrow_band_hint(layout)
        return stop(f"{len(gen_rep.errors)} geometry error(s)")
    print("  " + Colour.green("stator built"))

    # ---------------------------------------------------------------- 3. rotor
    step(3, total, "Building the rotor: the two rings, each by the Single Generator, then the disc")
    rings, disc = {}, None
    if want_rotor or args.check:
        rot_rep = Report()
        for k in (1, 2):
            try:
                rings[k] = DRB.build_ring(sets[k], stators[k], getattr(P.BOARD, "ROTOR_START_ANGLE_ZERO", "rx_zero"))
            except (ValueError, RuntimeError) as e:
                failed = Report()
                failed.add_exception(e)
                prefixed(failed, k).print()
                return stop(f"ring {k} of the rotor cannot be built")
            r = DesignChecks.check_design(sets[k], stators[k], rings[k])
            r = prefixed(r, k)
            r.items = [it for it in r.items if it not in gen_rep.items]      # only the rotor's own notes are new
            rot_rep.extend(r)
        disc = DRB.assemble(P, dual, rings[1], rings[2])
        rot_rep.extend(DDC.check_rings(P, layout, rings[1], rings[2], stators[1], stators[2]))
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
    step(4, total, "Electrical estimate, each set on its own")
    el_record, el_summary, el_warn = {}, {}, []
    for k in (1, 2):
        w, s, lines = electrical(sets[k], k, stators[k], rings.get(k), RB)
        el_warn += w
        el_summary[k] = s
        el_record[k] = lines
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
    written, folder, silk = [], None, None
    try:
        folder = OF.create_output_folder(dual, P)
        print(f"  folder  {folder}")
        if want_stator:
            path = dual.write(os.path.join(folder, P.BOARD.STATOR_FILE))
            written.append(path)
            print("  " + Colour.green(f"stator  -> {path}"))
            silk = LCS.add_to_file(path, P)              # the lead-cutting silkscreen suggestion, drawn into the file
        if want_rotor:
            path = disc.write(os.path.join(folder, P.BOARD.ROTOR_FILE))
            written.append(path)
            print("  " + Colour.green(f"rotor   -> {path}"))
        path = OF.write_record(folder, P, written, dual=dual, disc=disc if want_rotor else None, layout=layout,
                               sets=sets, electrical_lines=el_record, warnings=warn_texts + list(el_warn),
                               command="python Dual_RunCoilGenerator.py " + " ".join(sys.argv[1:] if argv is None else argv))
        if silk is not None:
            LCS.append_record(path, silk)
        print("  " + Colour.green(f"record  -> {path}"))
        if want_stator and want_rotor:
            all_warn += draw_pictures(folder)
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
        print(dual.summary())
    if want_rotor:
        print(disc.summary())
    for k in (1, 2):
        if el_summary.get(k):
            print(f"Electrical of {SET_WORD[k]} (estimate, step 4): {el_summary[k]}")
    print()
    print(Colour.green(f"SUCCESS: {len(written)} board file(s) + {OF.RECORD_FILE} written to {folder}")
          + (Colour.yellow(f"  ({all_warn} warning(s) above)") if all_warn else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
