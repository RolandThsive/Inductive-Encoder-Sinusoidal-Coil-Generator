"""
WebGenerator.py  -  the web GUI's entry point into the generator (runs inside the browser with Pyodide).

It does what RunCoilGenerator.py does, without touching the generator itself:
  1. the visitor's values are written into copies of the parameter files (only the changed lines
     change, so Parameters.txt keeps its verbatim copies),
  2. the chain of RunCoilGenerator.py: CheckParameters.check_parameters, RX_Builder.build_rx, TX_Builder.build_tx,
     StatorAssembly.assemble + DesignChecks, RotorBuilder.RotorDesign + DesignChecks,
  3. the files are written with OutputFolders into Output/Coil_..., and zipped.

The electrical estimate (TX_Electrics.py) is not made in the web GUI; Parameters.txt says so.  Nothing here is
needed to run the generator on a desktop.

Every function returns JSON text, so the JavaScript side never sees Python objects.

Folder layout in the browser's in-memory file system (ROOT):
    ROOT/Generator/...                the generator package ("Single Generator/Generator" in the repository)
    ROOT/WebGUI/WebGenerator.py       this file
    ROOT/Parameters_Default/*.py      the parameter files as published (never changed)
    ROOT/Parameters/*.py              the same files with the visitor's values (rewritten on every run)
    ROOT/Output/Coil_.../             the run's folder (emptied before every run)
    ROOT/out.zip                      the run's zip (generate)
    ROOT/parameters.zip               the Export zip (export_zip)
"""

import ast
import contextlib
import io
import json
import os
import re
import shutil
import sys
import types
import zipfile

ROOT = "/coilgen"
PARAMETER_FILES = ("Board_Parameters.py", "RX_Parameters.py", "TX_Parameters.py", "Rotor_Parameters.py",
                   "IC_Parameters.py")
PARAMETER_MODULES = ("Parameters",) + tuple(f[:-3] for f in PARAMETER_FILES)

# Not shown in the web GUI: settings that only feed the electrical estimate (they never change a board).  Their
# files stay in the zip and in Export with the published values.
HIDDEN = {"RECEIVER_IC", "COPPER_THICKNESS_UM", "COPPER_CONDUCTIVITY_S_M", "TX_AC_RESISTANCE_FACTOR",
          "STACKUP_PREPREG_MM", "TANK_CAP_SERIES",
          "IC_NAME", "IC_OSC_MIN_MHZ", "IC_OSC_MAX_MHZ", "IC_MIN_RP_OHM", "IC_SPLIT_TANK_CAPS"}


def _no_removed_features(text):
    """The web page has no electrical estimate, so the help texts and notes that point to it (they come from the
    generator's own files, which stay unchanged) lose those sentences."""
    t = re.sub(r"\s*The electrical estimate sizes the\s+tank capacitors for it; the rotor summary", " The rotor summary", text)
    t = re.sub(r"\s*\(see the electrical estimate\)", "", t)
    return re.sub(r"[ \t]{2,}", " ", t)


def _web_text(text):
    return _no_removed_features(text)


# Starting values that differ from the parameter files in the web version only (none now: the files themselves
# carry the web's defaults, e.g. RX nets "SIN_Signal" / "COS_Signal").  WebGUI.js has a matching empty hook,
# START_DESIGN, which also feeds the Reset button and the changed-dot logic.
WEB_DEFAULTS = {}
# Shown, but not editable: they only name files and place the board on the KiCad page.
READ_ONLY = {"OUTPUT_DIR", "STATOR_FILE", "ROTOR_FILE", "CENTER_X_MM", "CENTER_Y_MM", "PAGE_SIZE_MM"}


def _paths():
    # The parameter files can be rewritten less than a second apart with the same size (LOOPS = 1 -> 4), so a
    # cached .pyc keyed on time and size could look valid and the old values would be used.  Never cache them.
    sys.dont_write_bytecode = True
    shutil.rmtree(os.path.join(ROOT, "Parameters", "__pycache__"), ignore_errors=True)
    # the generator is the package ROOT/Generator; importing it puts ROOT/Parameters on the path too
    for p in (os.path.join(ROOT, "Parameters"), ROOT):
        if p not in sys.path:
            sys.path.insert(0, p)


def _forget_modules():
    """Drop the generator's modules so the next import reads the newly written parameter files."""
    import importlib
    importlib.invalidate_caches()
    shutil.rmtree(os.path.join(ROOT, "Parameters", "__pycache__"), ignore_errors=True)
    for name in list(sys.modules):
        if name == "Generator" or name.startswith("Generator.") or name in PARAMETER_MODULES:
            sys.modules.pop(name, None)


def _jsonable(x):
    if isinstance(x, (tuple, list)):
        return [_jsonable(i) for i in x]
    if isinstance(x, float) and x != x:
        return None
    return x


# =============================================================================
# parameter files
# =============================================================================
def _assignments(source):
    """{NAME: (line, col, end_line, end_col) of the value expression} of every top-level NAME = value."""
    out = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = node.value
            # these are UTF-8 byte offsets; the parameter files are ASCII, so they equal str indices
            out[node.targets[0].id] = (v.lineno, v.col_offset, v.end_lineno, v.end_col_offset)
    return out


# help for the few parameters the parameter files leave without a comment
FALLBACK_HELP = {
    "RX_TRACE_WIDTH_MM": "Width of the RX coil traces, in mm.",
    "TX_NET": "KiCad net name of the TX coil (its pads and traces carry this net).",
    "ROTOR_CUSTOM_SECTORS": "Custom rotor (ROTOR_MODE = \"custom\"): number of metal sectors around the rotor.",
    "ROTOR_CUSTOM_DUTY": "Custom rotor (ROTOR_MODE = \"custom\"): metal fraction of each sector period (0.5 = half metal).",
    "ROTOR_CUSTOM_START_ANGLE_DEG": "Custom rotor (ROTOR_MODE = \"custom\"): mechanical angle where the first sector starts, in degrees.",
    "ROTOR_CUSTOM_INNER_RADIUS_MM": "Custom rotor (ROTOR_MODE = \"custom\"): inner radius of the metal sectors, in mm.",
    "ROTOR_CUSTOM_OUTER_RADIUS_MM": "Custom rotor (ROTOR_MODE = \"custom\"): outer radius of the metal sectors, in mm.",
    "ROTOR_CUSTOM_COPPER_LAYERS": "Custom rotor (ROTOR_MODE = \"custom\"): layer(s) carrying the metal sectors; mount the copper side towards the stator.",
}


def _help_texts(source):
    """{NAME: help text}: the comment block right above the assignment, its trailing comment and the
    comment-only lines that continue it below (the parameter files are written that way)."""
    lines = source.split("\n")
    out, prev_end = {}, {}
    spots = _assignments(source)
    for name, (ln, _col, end_ln, end_col) in sorted(spots.items(), key=lambda kv: kv[1]):
        i = ln - 1                                        # 0-based line of the assignment
        above = []
        j = i - 1
        while j >= 0 and lines[j].lstrip().startswith("#") and not set(lines[j].strip()) <= set("#= -") \
                and not lines[j].strip().startswith("# ----"):            # a section heading ends the block
            above.insert(0, lines[j].strip().lstrip("#").rstrip())
            j -= 1
        trailing = []
        first = lines[end_ln - 1]
        if "#" in first[end_col:]:
            trailing.append(first[first.index("#", end_col) + 1:].strip())
            k = end_ln
            col = first.index("#", end_col)
            # a continuation comment may start up to 2 columns left of the trailing '#'
            while k < len(lines) and lines[k].strip().startswith("#") and len(lines[k]) - len(lines[k].lstrip()) >= col - 2:
                trailing.append(lines[k].strip().lstrip("#").strip())
                k += 1
        text = "\n".join(t[1:] if t.startswith(" ") else t for t in above)
        if trailing:
            text = (text + "\n" if text else "") + " ".join(trailing)
        text = text.strip()
        # a parameter written right under another one, with no comment of its own, shares that one's text
        # (TX_WIRING / TX_LAYER_A / TX_LAYER_B)
        if not text and prev_end.get("line") == i - 1 and prev_end.get("name"):
            text = out[prev_end["name"]]
        # "... or set a fixed radius here" finishes the sentence of the parameter above ("... - this ...")
        if text.startswith("...") and prev_end.get("name") and out[prev_end["name"]].endswith("..."):
            text = out[prev_end["name"]] + " " + text[3:].lstrip()
        out[name] = text
        prev_end = {"line": end_ln - 1, "name": name}
    return out


def _groups(source):
    """{NAME: heading}: the section heading of the parameter file each parameter sits under
    ("# ===" + "# TITLE", or a "# ---- title ----" sub-heading)."""
    lines = source.split("\n")
    spots = _assignments(source)
    by_line = {ln: name for name, (ln, _c, _e, _ec) in spots.items()}
    out, title, sub = {}, "", ""
    for i, line in enumerate(lines):
        s = line.strip()
        if re.fullmatch(r"#\s*=+", s) and i + 1 < len(lines):
            t = lines[i + 1].strip()
            m = re.fullmatch(r"#\s+([A-Z][A-Z0-9 /,()+'_-]*[A-Z0-9)])\s*(\(.*\))?", t)
            if m:
                title, sub = m.group(1).strip().title(), ""
        m = re.fullmatch(r"#\s*-{2,}\s*(.+?)\s*-{2,}", s)
        if m:
            sub = m.group(1).strip()
            sub = sub[:1].upper() + sub[1:]
        if i + 1 in by_line:
            out[by_line[i + 1]] = sub or title or "General"
    return out


def _py_literal(value, kind):
    # (no editable parameter is a pair today: PAGE_SIZE_MM is read-only; kept in case it becomes editable)
    if kind == "pair" and isinstance(value, list):
        value = tuple(value)
    if isinstance(value, float) and value.is_integer() and kind == "int":
        value = int(value)
    return repr(value)


def _write_parameter_files(values):
    """Write ROOT/Parameters/*.py: the published files with the visitor's values put in.  Only the value
    expressions of changed parameters are replaced; comments and layout stay as they are."""
    from Generator.Checks import ParameterRules as PR
    kinds = {name: kind for _f, name, kind, _o, _a in PR.SPEC}
    os.makedirs(os.path.join(ROOT, "Parameters"), exist_ok=True)
    changed = []
    for fname in PARAMETER_FILES:
        with open(os.path.join(ROOT, "Parameters_Default", fname), encoding="utf-8") as fh:
            src = fh.read()
        spots = _assignments(src)
        lines = src.split("\n")
        # replace from the bottom up, so earlier positions stay valid
        for name, (ln, col, end_ln, end_col) in sorted(spots.items(), key=lambda kv: kv[1], reverse=True):
            if name not in values or name in READ_ONLY or name in HIDDEN:
                continue
            new = _py_literal(values[name], kinds.get(name))
            old_expr = (lines[ln - 1][col:end_col] if ln == end_ln else
                        "\n".join([lines[ln - 1][col:]] + lines[ln:end_ln - 1] + [lines[end_ln - 1][:end_col]]))
            try:
                same = ast.literal_eval(old_expr) == ast.literal_eval(new)
            except Exception:
                same = old_expr == new
            if same:
                continue
            head, tail = lines[ln - 1][:col], lines[end_ln - 1][end_col:]
            pad = " " * max(0, len(old_expr) - len(new)) if ln == end_ln and "#" in tail else ""
            lines[ln - 1:end_ln] = [head + new + pad + tail]
            changed.append(name)
        with open(os.path.join(ROOT, "Parameters", fname), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines))
    return changed


def _restore_default_files():
    os.makedirs(os.path.join(ROOT, "Parameters"), exist_ok=True)
    for fname in PARAMETER_FILES + ("Parameters.py",):
        shutil.copyfile(os.path.join(ROOT, "Parameters_Default", fname), os.path.join(ROOT, "Parameters", fname))


# =============================================================================
# what the page asks for
# =============================================================================
def describe():
    """Every parameter the GUI may show: file, name, kind, options, default value, help text, flags."""
    _paths()
    _restore_default_files()
    _forget_modules()
    import Parameters as P
    from Generator.Checks import ParameterRules as PR
    helps, groups = {}, {}
    for fname in PARAMETER_FILES:
        with open(os.path.join(ROOT, "Parameters_Default", fname), encoding="utf-8") as fh:
            src = fh.read()
        helps.update(_help_texts(src))
        groups.update(_groups(src))
    out = []
    for file, name, kind, o, active in PR.SPEC:
        if name in HIDDEN:
            continue
        opts = {k: _jsonable(v) for k, v in o.items() if k in ("lo", "hi", "lo_ex", "hi_ex", "values", "ci",
                                                                  "optional", "default")}
        default = getattr(P, name, o.get("default"))
        default = WEB_DEFAULTS.get(name, default)
        help_text = _web_text(helps.get(name) or FALLBACK_HELP.get(name, ""))
        out.append({"file": file,
                    "name": name,
                    "kind": kind,
                    "options": opts,
                    "default": _jsonable(default),
                    "help": help_text,
                    "group": groups.get(name, "General"),
                    "readOnly": name in READ_ONLY})
    shown = {p["file"] for p in out}
    return json.dumps({"parameters": out, "files": [f for f in PARAMETER_FILES if f in shown]})


def inactive(values_json):
    """Names of the parameters the generator ignores with these values (greyed out in the GUI)."""
    _paths()
    from Generator.Checks import ParameterRules as PR
    values = json.loads(values_json)
    ns = types.SimpleNamespace(**{k: (tuple(v) if isinstance(v, list) and k == "PAGE_SIZE_MM" else v)
                                  for k, v in values.items()})
    out = []
    for _file, name, _kind, _o, active in PR.SPEC:
        if active is None or name in HIDDEN:
            continue
        try:
            if not active(ns):
                out.append(name)
        except Exception:
            pass
    return json.dumps(out)


def generate(values_json):
    """Run the generator with the visitor's values.  Returns the findings and, when nothing failed, the files."""
    _paths()
    values = json.loads(values_json)
    items = []
    result = {"ok": False, "items": items, "name": None, "files": {}, "summaries": {}}

    def take(stage, rep):
        from Generator.Core.Conflict import conflict_title
        for level, msg, names in rep.items:
            items.append({"stage": stage, "level": level, "msg": _web_text(msg), "names": list(names),
                          # a conflict between parameters: "NAME_A conflicts with NAME_B", the explanation below it
                          "title": conflict_title(names) if len(names) >= 2 else None})

    def fail(why):
        result["failed"] = why
        return json.dumps(result)

    # 0. the parameter files
    _restore_default_files()
    _forget_modules()
    try:
        changed = _write_parameter_files(values)
    except Exception as e:                                    # a value that cannot be written as Python
        return fail(f"the values cannot be written into the parameter files: {type(e).__name__}: {e}")
    result["changed"] = changed
    _forget_modules()
    out_dir = os.path.join(ROOT, "Output")
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)

    # 1. parameters
    try:
        import Parameters as P
    except Exception as e:
        return fail(f"the parameter files cannot be loaded: {type(e).__name__}: {e}")
    from Generator.Checks import DesignChecks
    from Generator.Core.Conflict import Report
    from Generator.Run import OutputFolders as OF
    from Generator.Run.CheckParameters import check_parameters
    rep = check_parameters(P)
    take("Parameters", rep)
    warn_texts = list(rep.warnings)
    if rep.errors:
        return fail(f"{len(rep.errors)} parameter error(s)")
    strict = str(getattr(P, "GENERATOR_MODE", "normal")).strip().lower() == "strict"

    # 2. stator: the chain of RunCoilGenerator.py (the RX reads the parameters, the TX reads the RX, the assembly turns
    #    the board so that the TX terminal sits at 0 deg, the checks measure the result)
    from Generator.Stator import StatorAssembly
    from Generator.Stator.RX import RX_Builder
    from Generator.Stator.TX import TX_Builder
    from Generator.Rotor import RotorBuilder as RB
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(io.StringIO()):
            rx = RX_Builder.build_rx(P)
            tx = TX_Builder.build_tx(rx)
            DesignChecks.check_tx_terminal(tx)
            stator = StatorAssembly.assemble(P, rx, tx)
            DesignChecks.check_stator_clearances(stator)
    except (ValueError, RuntimeError) as e:
        failed = Report()
        failed.add_exception(e)
        take("Stator", failed)
        return fail("stator cannot be built")
    gen_rep = DesignChecks.classify_generator_output(buf.getvalue())
    gen_rep.extend(DesignChecks.check_design(P, stator))
    take("Stator", gen_rep)
    board_warn = len(gen_rep.warnings)                        # warnings about the finished boards
    warn_texts += gen_rep.warnings
    if gen_rep.errors:
        return fail(f"{len(gen_rep.errors)} geometry error(s)")

    # 3. rotor
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rotor = RB.RotorDesign(P, stator=stator)
    except (ValueError, RuntimeError) as e:
        failed = Report()
        failed.add_exception(e)
        take("Rotor", failed)
        return fail("rotor cannot be built")
    rot_rep = DesignChecks.check_design(P, stator, rotor)
    rot_rep.items = [it for it in rot_rep.items if it not in gen_rep.items]
    take("Rotor", rot_rep)
    board_warn += len(rot_rep.warnings)
    warn_texts += rot_rep.warnings
    if rot_rep.errors:
        return fail(f"{len(rot_rep.errors)} rotor error(s)")

    # 4. GENERATOR_MODE = "strict": every warning about the finished boards counts as an error
    if strict and board_warn:
        return fail(f'GENERATOR_MODE = "strict": {board_warn} warning(s) about the boards count as errors')

    # 5. write
    folder = OF.create_output_folder(stator, P)
    written = [stator.write(os.path.join(folder, P.STATOR_FILE)), rotor.write(os.path.join(folder, P.ROTOR_FILE))]
    note = ["ELECTRICAL ESTIMATE",
            "  not made: the web GUI runs the generator only (no TX_Electrics).",
            "  Run RunCoilGenerator.py on a desktop with these parameter files for the estimate."]
    OF.write_record(folder, P, written, stator=stator, rotor=rotor, electrical_lines=note,
                    warnings=warn_texts, command="Web GUI (generator only)")
    name = os.path.basename(folder)
    record = os.path.join(folder, OF.RECORD_FILE)          # the browser's folder means nothing to the reader
    with open(record, encoding="utf-8") as f:
        text = f.read()
    with open(record, "w", encoding="utf-8") as f:
        f.write(text.replace(folder, name + " (downloaded zip)"))
    zpath = os.path.join(ROOT, "out.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(folder)):
            z.write(os.path.join(folder, f), arcname=f"{name}/{f}")
        for fname in PARAMETER_FILES:                      # the parameter files of this run, for the desktop
            # inside the run's own folder, so the zip is a self-contained record of the run
            z.write(os.path.join(ROOT, "Parameters", fname), arcname=f"{name}/Parameter_Files/{fname}")
    files = {}
    for key, fname in (("stator", P.STATOR_FILE), ("rotor", P.ROTOR_FILE), ("record", OF.RECORD_FILE)):
        with open(os.path.join(folder, fname), encoding="utf-8") as fh:
            files[key] = fh.read()
    result.update(ok=True, name=name, files=files, zip=zpath,
                  summaries={"stator": stator.summary(), "rotor": rotor.summary()},
                  rx={"ri": float(stator.ri), "ro": float(stator.ro)},
                  edges={"inner": float(stator.inner_edge_radius), "outer": float(stator.outer_edge_radius)},
                  center=[float(P.CENTER_X_MM), float(P.CENTER_Y_MM)])
    return json.dumps(result)


def parameter_files(values_json):
    """{file name: text} of the parameter files with these values (Export)."""
    _paths()
    _restore_default_files()
    _forget_modules()
    _write_parameter_files(json.loads(values_json))
    out = {}
    for fname in PARAMETER_FILES:
        with open(os.path.join(ROOT, "Parameters", fname), encoding="utf-8") as fh:
            out[fname] = fh.read()
    return json.dumps(out)


def export_zip(values_json):
    """Zip of the parameter files with these values (Export).  Returns the path of the zip."""
    files = json.loads(parameter_files(values_json))
    zpath = os.path.join(ROOT, "parameters.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fname, text in files.items():
            # folder named Parameters/, so it unpacks over the repository's own Parameters/ folder
            z.writestr(f"Parameters/{fname}", text)
    return json.dumps({"zip": zpath})


def read_values(text):
    """Values found in a dropped Parameters.txt or parameter file (Import): every NAME = literal it holds.
    {"values": {name: value}, "ignored": [names the program does not know]}: a file of an older version carries
    names that were removed (e.g. TX_LAYERS, TX_START_ANGLE_DEG); they are listed so the page can say so."""
    _paths()
    from Generator.Checks import ParameterRules as PR
    known = {name for _f, name, _k, _o, _a in PR.SPEC}
    found, ignored = {}, []
    for line in text.split("\n"):
        s = line.strip()
        if "=" not in s or s.startswith("#"):
            continue
        name, _, rest = s.partition("=")
        name = name.strip()
        if name not in known:
            if re.fullmatch(r"[A-Z][A-Z0-9_]*", name) and name not in ignored:
                ignored.append(name)
            continue
        if name in HIDDEN or name in READ_ONLY:
            continue
        expr = rest.split("   (not used")[0].strip()
        for cut in range(len(expr), 0, -1):                # longest prefix that is a Python literal
            try:
                found[name] = _jsonable(ast.literal_eval(expr[:cut].strip()))
                break
            except Exception:
                continue
    return json.dumps({"values": found, "ignored": ignored})
