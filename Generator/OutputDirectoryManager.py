#!/usr/bin/env python3
"""
OutputDirectoryManager.py  -  where RunCoilGenerator.py puts every generation, and the record it leaves there.

Every generation gets its own folder inside OUTPUT_DIR (Board_Parameters.py; "Output" = the Output folder of
the project, next to Parameters, Generator and Analyser_And_Optimizer):

    Coil_<board inside radius>_<board outside radius>_<RX loops>_<RX sub-coils>_<TX turns>_<TX wiring>_<TX shape>

    board inside radius   radius of the centre hole of the stator board (mm)
    board outside radius  radius of the outer edge of the stator board (mm)
    RX loops              LOOPS
    RX sub-coils          RX_SUBCOILS
    TX turns              TX_TURNS (turns per TX layer)
    TX wiring             Single   (TX_LAYERS = 1: one layer)
                          Series   (TX_LAYERS = 2, TX_SERIES = True: two layers in series)
                          Parallel (TX_LAYERS = 2, TX_SERIES = False: two layers in parallel)
    TX shape              Stepped or Spiral (TX_TURN_SHAPE)

for example  Coil_36.8_56.6_8_1_3_Single_Stepped.  If that folder already exists, the next free one of
Coil_..._Stepped__1, Coil_..._Stepped__2, ... is used, so nothing is ever overwritten.

A relative OUTPUT_DIR is taken from the project folder (the one that holds Parameters, Generator, ...), not
from the folder you run the program in, so the boards always land in the same place.  (With every file in one
folder, as in earlier versions, it is taken from the folder you run the program in, as before.)

Inside the folder:
    Stator.kicad_pcb, Rotor.kicad_pcb   (STATOR_FILE / ROTOR_FILE)
    Parameters.txt                      what was generated, with which values: the value of every
                                        parameter, the summaries and the electrical estimate of
                                        this run, and a verbatim copy of the four parameter files

Only RunCoilGenerator.py writes boards; StatorGenerator.py and RotorGenerator.py no longer write
files when they are run on their own.
"""

import datetime
import os

PARAMETER_FILES = ("Board_Parameters.py", "RX_Parameters.py", "TX_Parameters.py", "Rotor_Parameters.py")
RECORD_FILE = "Parameters.txt"
FOLDER_PREFIX = "Coil"
INCREMENT_SEPARATOR = "__"


def _num(x):
    """Number for a folder name: no needless decimals (36.8, 56.6, 8), at most 3 decimals."""
    x = round(float(x), 3)
    return str(int(x)) if x == int(x) else f"{x:g}"


TX_WIRING_WORDS = {"single": "Single", "series2": "Series", "parallel": "Parallel"}
FOLDER_PATTERN = ("Coil_<board inside radius>_<board outside radius>_<RX loops>_<RX sub-coils>_<TX turns>_"
                  "<TX wiring>_<TX shape>")


def tx_words(stator, P):
    """('Single' | 'Series' | 'Parallel', 'Stepped' | 'Spiral') of this TX."""
    mode = getattr(stator, "tx_mode", None)
    if mode is None:                                   # (no stator: from the parameters)
        mode = "single" if int(getattr(P, "TX_LAYERS", 1)) == 1 else (
            "series2" if getattr(P, "TX_SERIES", True) is True else "parallel")
    wiring = TX_WIRING_WORDS.get(mode, str(mode).title())
    shape = "Spiral" if str(getattr(P, "TX_TURN_SHAPE", "stepped")).lower() == "spiral" else "Stepped"
    return wiring, shape


def folder_name(stator, P):
    """Coil_<board inside radius>_<board outside radius>_<RX loops>_<RX sub-coils>_<TX turns>_<TX wiring>_<TX shape>."""
    parts = (FOLDER_PREFIX, _num(stator.inner_edge_radius), _num(stator.outer_edge_radius),
             str(int(P.LOOPS)), str(int(P.RX_SUBCOILS)), str(int(P.TX_TURNS))) + tx_words(stator, P)
    return "_".join(parts)


def project_folder():
    """The project folder (it holds Parameters, Generator, Analyser_And_Optimizer and Output), or None when every
    file sits in one folder (earlier versions)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return root if os.path.isdir(os.path.join(root, "Parameters")) and os.path.isdir(os.path.join(root, "Generator")) \
        else None


def output_dir(P):
    """OUTPUT_DIR as a usable path: an absolute one as it is, a relative one from the project folder (from the
    current folder when every file sits in one folder)."""
    d = os.path.expanduser(str(P.OUTPUT_DIR))
    if os.path.isabs(d):
        return d
    root = project_folder()
    return os.path.normpath(os.path.join(root, d)) if root else d


def create_output_folder(stator, P):
    """Create the folder for this generation inside OUTPUT_DIR and return its path.  An existing folder of
    the same name is never reused: the name gets __1, __2, ... (the first one that is free)."""
    parent = output_dir(P)
    os.makedirs(parent, exist_ok=True)
    base = folder_name(stator, P)
    n = 0
    while True:
        name = base if n == 0 else f"{base}{INCREMENT_SEPARATOR}{n}"
        path = os.path.join(parent, name)
        try:
            os.mkdir(path)                       # fails if it exists: two runs at once cannot share a folder
            return path
        except FileExistsError:
            n += 1


def remove_if_empty(folder):
    """Clean up after a failed write (only an empty folder is removed)."""
    try:
        if folder and os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)
    except OSError:
        pass


def _parameter_dir(P):
    """Folder of the parameter files (next to Parameters.py)."""
    f = getattr(P, "__file__", None)
    return os.path.dirname(os.path.abspath(f)) if f else os.getcwd()


def _values_by_file(P, stator=None):
    """[(file, [(name, value text), ...]), ...]: every parameter the program knows, in the order of the
    checker's table, with the value that was used ('not set' when an optional line is missing).  A radius that
    the board edge overrides (INNER_EDGE_RADIUS_MM / OUTER_EDGE_RADIUS_MM) is marked 'not used'."""
    try:
        import ParameterChecker as PC
        spec = [(file, name) for file, name, _kind, _opt, _active in PC.SPEC]
    except Exception:                                   # without the checker: whatever the module holds
        spec = [("Parameters", n) for n in sorted(dir(P)) if n.isupper() and not n.startswith("_")]
    out, known = {}, set()
    for file, name in spec:
        known.add(name)
        val = repr(getattr(P, name)) if hasattr(P, name) else "(not set: the default is used)"
        if stator is not None and name == "INSIDE_RADIUS_MM" and getattr(P, "INNER_EDGE_RADIUS_MM", None) is not None:
            val += f"   (not used: INNER_EDGE_RADIUS_MM sets it, the RX band starts at r = {stator.ri:g})"
        if stator is not None and name == "OUTSIDE_RADIUS_MM" and getattr(P, "OUTER_EDGE_RADIUS_MM", None) is not None:
            val += f"   (not used: OUTER_EDGE_RADIUS_MM sets it, the RX band ends at r = {stator.ro:g})"
        out.setdefault(file, []).append((name, val))
    extra = [(n, repr(getattr(P, n))) for n in sorted(dir(P)) if n.isupper() and not n.startswith("_")
             and n not in known]
    if extra:
        out["not used by the program"] = extra
    return list(out.items())


def write_record(folder, P, written, stator=None, rotor=None, electrical_lines=None, warnings=None, command=None):
    """Write Parameters.txt into the generation folder: what was made and every value it was made with."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = ["COIL GENERATION RECORD", "=" * 22, "",
             f"generated   {now}",
             f"folder      {os.path.abspath(folder)}",
             f"files       {', '.join(os.path.basename(p) for p in written) or '-'}"]
    if command:
        lines.append(f"command     {command}")
    if stator is not None:
        lines.append(f"name        {folder_name(stator, P)}  = {FOLDER_PATTERN}")
    lines.append("")
    if warnings:
        lines += ["WARNINGS OF THIS RUN", "-" * 20] + [f"  {w}" for w in warnings] + [""]
    if stator is not None:
        lines += ["STATOR", "-" * 6, stator.summary(), ""]
    if rotor is not None:
        lines += ["ROTOR", "-" * 5, rotor.summary(), ""]
    if electrical_lines:
        lines += list(electrical_lines) + [""]
    lines += ["PARAMETER VALUES USED", "-" * 21]
    for file, items in _values_by_file(P, stator):
        lines.append(f"[{file}]")
        width = max(len(n) for n, _ in items)
        lines += [f"  {n:<{width}s} = {v}" for n, v in items]
        lines.append("")
    pdir = _parameter_dir(P)
    lines += ["PARAMETER FILES (verbatim copies)", "-" * 33]
    for fname in PARAMETER_FILES:
        path = os.path.join(pdir, fname)
        lines.append(f"########## {fname} " + "#" * max(0, 60 - len(fname)))
        try:
            with open(path, encoding="utf-8") as fh:
                lines.append(fh.read().rstrip("\n"))
        except OSError as e:
            lines.append(f"(could not be read: {e})")
        lines.append("")
    path = os.path.join(folder, RECORD_FILE)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path
