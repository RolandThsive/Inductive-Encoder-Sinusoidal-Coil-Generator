"""
Dual_OutputFolders.py  -  where Dual_RunCoilGenerator.py puts every generation, and the record it leaves there.

Every generation gets its own folder inside OUTPUT_DIR (Dual_Board_Parameters.py; "Output" = the Output folder in
"Dual Generator", next to Parameters and Dual_Generator):

    DualCoil_<bore radius>_<outline radius>_<set 1 loops>x<set 2 loops>_<set 1 TX turns>x<set 2 TX turns>

for example  DualCoil_8.5_29.5_1x16_2x3.  If that folder already exists, the next free one of
DualCoil_..._2x3__1, __2, ... is used, so nothing is ever overwritten.

A relative OUTPUT_DIR is taken from the "Dual Generator" folder, not from the folder the program is run from.

Inside the folder:
    Stator.kicad_pcb, Rotor.kicad_pcb   (STATOR_FILE / ROTOR_FILE)
    Parameters.txt                      what was generated, with which values: the mode and every value the
                                        generator computed (bands, edges, gap, zeros), the summaries and the
                                        electrical estimate of each set, the value of every parameter by dual
                                        file, what the dual board fixes, and a verbatim copy of the seven files
"""

import datetime
import os

from Generator.Checks import ParameterRules as SingleRules

from Dual_Generator import DUAL_GENERATOR
from Dual_Generator.Core import Dual_SetParameters as SP

RECORD_FILE = "Parameters.txt"
FOLDER_PREFIX = "DualCoil"
INCREMENT_SEPARATOR = "__"
FOLDER_PATTERN = "DualCoil_<bore radius>_<outline radius>_<set 1 loops>x<set 2 loops>_<set 1 TX turns>x<set 2 TX turns>"


def _num(x):
    """Number for a folder name: no needless decimals (36.8, 56.6, 8), at most 3 decimals."""
    x = round(float(x), 3)
    return str(int(x)) if x == int(x) else f"{x:g}"


def folder_name(dual, P):
    s1, s2 = dual.sets
    return "_".join((FOLDER_PREFIX, _num(dual.bore), _num(dual.outline), f"{int(s1.N)}x{int(s2.N)}",
                     f"{int(s1.P.TX_TURNS)}x{int(s2.P.TX_TURNS)}"))


def project_folder():
    """The "Dual Generator" folder (it holds Parameters, Dual_Generator and Output)."""
    return DUAL_GENERATOR


def output_dir(B):
    """OUTPUT_DIR as a usable path: an absolute one as it is, a relative one from "Dual Generator"."""
    d = os.path.expanduser(str(B.OUTPUT_DIR))
    return d if os.path.isabs(d) else os.path.normpath(os.path.join(project_folder(), d))


def create_output_folder(dual, P):
    """Create the folder for this generation inside OUTPUT_DIR and return its path.  An existing folder of
    the same name is never reused: the name gets __1, __2, ... (the first one that is free)."""
    parent = output_dir(P.BOARD)
    os.makedirs(parent, exist_ok=True)
    base = folder_name(dual, P)
    n = 0
    while True:
        name = base if n == 0 else f"{base}{INCREMENT_SEPARATOR}{n}"
        path = os.path.join(parent, name)
        try:
            os.mkdir(path)
            return path
        except FileExistsError:
            n += 1


def remove_if_empty(folder):
    try:
        if folder and os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)
    except OSError:
        pass


def _parameter_dir():
    return os.path.join(project_folder(), "Parameters")


def _values_by_file(P):
    """[(file, [(name, value text), ...]), ...]: every parameter of every dual file, in the order of
    Dual_SetParameters.NAMES_BY_FILE, with the value in the file (or 'not set')."""
    attrs = {"Dual_Board_Parameters.py": P.BOARD, "Dual_RX1_Parameters.py": P.RX1, "Dual_RX2_Parameters.py": P.RX2,
             "Dual_TX1_Parameters.py": P.TX1, "Dual_TX2_Parameters.py": P.TX2,
             "Dual_Rotor1_Parameters.py": P.ROTOR1, "Dual_Rotor2_Parameters.py": P.ROTOR2,
             SP.FIXED_FILE: getattr(P, "FIXED", None)}
    out = []
    for file, names in SP.NAMES_BY_FILE.items():
        mod = attrs[file]
        if mod is None:
            out.append((file, [("(file not loaded)", "")]))
            continue
        items = [(n, repr(getattr(mod, n)) if hasattr(mod, n) else "(not set: the default is used)") for n in names]
        extra = [(n, repr(getattr(mod, n)) + "   (not a parameter of this file: ignored)")
                 for n in sorted(dir(mod)) if n.isupper() and not n.startswith("_") and n not in names]
        out.append((file, items + extra))
    return out


def write_record(folder, P, written, dual=None, disc=None, layout=None, sets=None, electrical_lines=None,
                 warnings=None, command=None):
    """Write Parameters.txt into the generation folder: what was made and every value it was made with.
    sets: the two set namespaces (Dual_SetParameters.build) as used; electrical_lines: {1: [...], 2: [...]}."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = ["DUAL COIL GENERATION RECORD", "=" * 27, "",
             f"generated   {now}",
             f"folder      {os.path.abspath(folder)}",
             f"files       {', '.join(os.path.basename(p) for p in written) or '-'}"]
    if command:
        lines.append(f"command     {command}")
    if dual is not None:
        lines.append(f"name        {folder_name(dual, P)}  = {FOLDER_PATTERN}")
        for k, st in ((1, dual.sets[0]), (2, dual.sets[1])):
            lines.append(f"set {k}       turned by {st.rotation_deg:.2f} deg so that its TX ends sit at {st.terminal_deg:g} deg; "
                         f"its RX pattern's zero is at {st.rotation_deg:.2f} deg")
    lines.append("")
    if layout is not None:
        lines += ["LAYOUT (what the generator computed)", "-" * 36] + layout.lines() + [""]
    if warnings:
        lines += ["WARNINGS OF THIS RUN", "-" * 20] + [f"  {w}" for w in warnings] + [""]
    if dual is not None:
        lines += ["STATOR", "-" * 6, dual.summary(), ""]
    if disc is not None:
        lines += ["ROTOR", "-" * 5, disc.summary(), ""]
    if electrical_lines:
        for k in (1, 2):
            if electrical_lines.get(k):
                lines += [f"SET {k}: " + electrical_lines[k][0]] + list(electrical_lines[k][1:]) + [""]
    lines += ["PARAMETER VALUES USED", "-" * 21]
    for file, items in _values_by_file(P):
        lines.append(f"[{file}]")
        width = max(len(n) for n, _ in items)
        lines += [f"  {n:<{width}s} = {v}" for n, v in items]
        lines.append("")
    if sets:
        lines += ["THE TWO SETS AS HANDED TO THE SINGLE GENERATOR (its names)", "-" * 58]
        order = [name for _f, name, _k, _o, _a in SingleRules.SPEC]
        for k, Pk in sorted(sets.items()):
            lines.append(f"[set {k}]")
            width = max(len(n) for n in order)
            lines += [f"  {n:<{width}s} = {getattr(Pk, n)!r}" for n in order if hasattr(Pk, n)]
            lines.append("")
    pdir = _parameter_dir()
    lines += ["PARAMETER FILES (verbatim copies)", "-" * 33]
    for fname in SP.PARAMETER_FILES:
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
