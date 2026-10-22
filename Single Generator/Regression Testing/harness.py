"""
harness.py  -  loads the Single Generator once and runs it in this process, with parameter overrides that live
only in memory (the parameter files are never touched), writing boards into a temporary folder.

    run(overrides, args)      run RunCoilGenerator.main(args) with the overrides applied; returns Result
    check(overrides)          run(overrides, ["--check", "--no-color"])
    write(overrides, args)    a full run that writes into a fresh temporary folder; Result.folder holds the files
    board(name)               the written boards of BOARD_CASES[name], made once per process and shared by the
                              tests (test_boards, test_invariants, test_silkscreen)

Overrides: {"LOOPS": 8, "RX_TABS": "none", "SILK.SILKSCREEN_SIDES": "top", "TX_TURNS": DELETE}.  A plain name
is a value of Parameters (the gathered module every part of the generator reads); "SILK." names a value of
SilkScreenSuggestion_Parameters.py; DELETE removes the name, as if its line were missing from the file.
Every run starts from the repository's own values: nothing an earlier test set survives.
"""

import atexit
import contextlib
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)                                  # "Single Generator"
REPO = os.path.dirname(PROJECT)
RESOURCES = os.path.join(REPO, "resources")
REFERENCES = os.path.join(HERE, "References")

sys.dont_write_bytecode = True                                   # the suite leaves no __pycache__ behind
for _p in (PROJECT, RESOURCES):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import Generator  # noqa: E402,F401   (puts the Parameters folder on the path)
from Generator.Run import RunCoilGenerator as R  # noqa: E402
from Generator.Run import OutputFolders as OF  # noqa: E402
import Parameters as P  # noqa: E402
import SilkScreenSuggestion_Parameters as SILK  # noqa: E402
import RegressionTools as RT  # noqa: E402

DELETE = object()
MODULES = {"": P, "SILK": SILK}
_SAVED = {k: {n: v for n, v in vars(m).items() if n.isupper() and not n.startswith("_")} for k, m in MODULES.items()}
UPDATE_REFERENCES = os.environ.get("REGRESSION_UPDATE_REFERENCES") == "1"
KEEP_OUTPUT = os.environ.get("REGRESSION_KEEP_OUTPUT") == "1"


def restore():
    """Every parameter module back to the values of the files."""
    for key, m in MODULES.items():
        for n in list(vars(m)):
            if n.isupper() and not n.startswith("_") and n not in _SAVED[key]:
                delattr(m, n)
        for n, v in _SAVED[key].items():
            setattr(m, n, v)


def apply(overrides):
    for name, value in (overrides or {}).items():
        key, _, attr = name.rpartition(".")
        m = MODULES[key]
        if value is DELETE:
            if hasattr(m, attr):
                delattr(m, attr)
        else:
            setattr(m, attr, value)


class Result:
    """What one run did: the return code, everything it printed, and (after a write) where the files are."""

    def __init__(self, rc, out, err, folder=None, params=None, silk=None):
        self.rc, self.out, self.err, self.folder = rc, out, err, folder
        self.params = params or {}          # every value of Parameters as the run saw it (the overrides applied)
        self.silk = silk or {}              # the same for SilkScreenSuggestion_Parameters.py
        self._boards = {}

    @property
    def lines(self):
        return self.out.splitlines()

    def _level(self, word):
        return [l.strip() for l in self.lines if re.match(r"\s*" + word + r"\b", l)]

    @property
    def errors(self):
        return self._level("ERROR")

    @property
    def warnings(self):
        return self._level("WARNING")

    @property
    def infos(self):
        return self._level("info")

    def has(self, pattern):
        return re.search(pattern, self.out) is not None

    @property
    def passed(self):
        return self.rc == 0

    def path(self, name):
        return os.path.join(self.folder, name) if self.folder else None

    @property
    def stator_path(self):
        return self.path(P.STATOR_FILE) if self.folder else None

    @property
    def rotor_path(self):
        return self.path(P.ROTOR_FILE) if self.folder else None

    @property
    def record_path(self):
        return self.path(OF.RECORD_FILE) if self.folder else None

    def text(self, name):
        with open(self.path(name), encoding="utf-8", newline="") as fh:
            return fh.read()

    def board(self, name):
        """The file parsed (RegressionTools.Board), once."""
        if name not in self._boards:
            self._boards[name] = RT.Board(self.text(name))
        return self._boards[name]

    @property
    def stator(self):
        return self.board(os.path.basename(self.stator_path))

    @property
    def rotor(self):
        return self.board(os.path.basename(self.rotor_path))

    @property
    def record(self):
        return self.text(OF.RECORD_FILE)

    @property
    def normalised_record(self):
        """The record without what changes from run to run (RegressionTools.normalise_record), the temporary
        output folder replaced by <output>."""
        text = self.record
        for d in (getattr(self, "out_dir", None), self.folder):
            if d:                       # as a path, as a path with forward slashes, and as repr() writes it (Windows)
                for form in (d, d.replace("\\", "/"), d.replace("\\", "\\\\")):
                    text = text.replace(form, "<output>")
        return RT.normalise_record(text, PROJECT)

    def __repr__(self):
        return f"Result(rc={self.rc}, folder={self.folder!r})"


def run(overrides=None, args=("--check", "--no-color")):
    restore()
    apply(overrides)
    params = {n: getattr(P, n) for n in dir(P) if n.isupper() and not n.startswith("_")}
    silk = {n: getattr(SILK, n) for n in dir(SILK) if n.isupper() and not n.startswith("_")}
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = R.main(list(args))
    finally:
        restore()
    return Result(rc, out.getvalue(), err.getvalue(), params=params, silk=silk)


def check(overrides=None, extra_args=()):
    return run(overrides, ["--check", "--no-color"] + list(extra_args))


_TMP_ROOT = None


def temp_root():
    global _TMP_ROOT
    if _TMP_ROOT is None:
        _TMP_ROOT = tempfile.mkdtemp(prefix="regression_single_")
        if not KEEP_OUTPUT:
            atexit.register(shutil.rmtree, _TMP_ROOT, True)
    return _TMP_ROOT


def write(overrides=None, args=("--no-color",), subdir=None):
    """A run that writes.  OUTPUT_DIR is pointed at a fresh temporary folder, so the repository's Output folder
    stays as it is; Result.folder is the Coil_... folder the run made (None when it wrote nothing)."""
    ov = dict(overrides or {})
    out_dir = ov.setdefault("OUTPUT_DIR", tempfile.mkdtemp(prefix=(subdir or "run") + "_", dir=temp_root()))
    res = run(ov, args)
    made = [d for d in sorted(os.listdir(out_dir)) if os.path.isdir(os.path.join(out_dir, d))]
    res.folder = os.path.join(out_dir, made[0]) if len(made) == 1 else None
    res.out_dir = out_dir
    res.made = made
    return res


# ---------------------------------------------------------------------------------------------- the board cases
# Every case is written once per process and compared with References/<case>/ by test_boards.py; the other
# board tests measure the same files.  A case is the overrides on top of the repository's parameter files.
BOARD_CASES = {
    "default": {},
    "loops_4_subcoils_2": {"LOOPS": 4, "RX_SUBCOILS": 2, "RX_TABS": "none"},
    "loops_16_tabs_single": {"LOOPS": 16, "RX_TABS": "single"},
    "four_layer_series": {"PCB_LAYERS": 4, "TX_WIRING": "series", "TX_LAYER_A": 1, "TX_LAYER_B": 4,
                          "RX_LAYER_A": 2, "RX_LAYER_B": 3, "RX_TABS": "none"},
    "four_layer_parallel_staggered": {"PCB_LAYERS": 4, "TX_WIRING": "parallel", "TX_LAYER_A": 1, "TX_LAYER_B": 4,
                                      "RX_LAYER_A": 2, "RX_LAYER_B": 3, "TX_PARALLEL_BREAK_STYLE": "staggered"},
    "series_two_layers_no_fingers": {"TX_WIRING": "series", "RX_TABS": "none"},
    "spiral_tx": {"TX_SHAPE": "spiral", "TX_TURNS": 5, "OUTER_EDGE_RADIUS_MM": None, "RX_TABS": "none"},
    "stepped_arc_tx": {"TX_SHAPE": "stepped_arc", "TX_TURNS": 2},
    "cosine_r_loops_4": {"RX_PROFILE": "cosine_r", "LOOPS": 4, "STEPS_PER_LOOP": 64},
    "band_from_centre": {"INSIDE_RADIUS_MM": None, "OUTSIDE_RADIUS_MM": None, "RX_R_BASE_MM": 18.8, "RX_A_MM": 2.6,
                         "INNER_EDGE_RADIUS_MM": None, "OUTER_EDGE_RADIUS_MM": None},
    "custom_rotor_no_cover": {"ROTOR_MODE": "custom", "ROTOR_CUSTOM_SECTORS": 1, "ROTOR_AUTO_COVER_TX": False,
                              "ROTOR_SOLDER_MASK_EXPANSION_MM": 0.1},
    "rotor_two_layers_mask_open": {"ROTOR_AUTO_COPPER_LAYERS": ["F.Cu", "B.Cu"], "ROTOR_SOLDER_MASK_EXPANSION_MM": 0.0,
                                   "ROTOR_PCB_THICKNESS_MM": 0.8, "ROTOR_AUTO_DUTY": 0.4},
    "silkscreen_top_dots_on_all": {"SILK.SILKSCREEN_SIDES": "top", "SILK.SILKSCREEN_DOT_ON_ALL_VIAS": True,
                                   "SILK.SILKSCREEN_COLOR": "#FFCC00"},
    "silkscreen_off": {"SILK.SILKSCREEN_SUGGESTION": False},
    "four_layer_blind_vias": {"PCB_LAYERS": 4, "VIA_TYPE": "blind", "VIA_DIAMETER_MM": 0.4, "VIA_DRILL_MM": 0.15,
                              "TX_WIRING": "series", "TX_LAYER_A": 1, "TX_LAYER_B": 2, "RX_LAYER_A": 3, "RX_LAYER_B": 4,
                              "RX_TABS": "none"},
    "four_layer_blind_parallel_fingers": {"PCB_LAYERS": 4, "VIA_TYPE": "blind", "VIA_DIAMETER_MM": 0.4,
                                          "VIA_DRILL_MM": 0.15, "TX_WIRING": "parallel", "TX_LAYER_A": 3,
                                          "TX_LAYER_B": 4, "RX_LAYER_A": 1, "RX_LAYER_B": 2},
}

_BOARDS = {}


def board(name):
    """The written boards of one case (Result), made the first time it is asked for."""
    if name not in _BOARDS:
        res = write(BOARD_CASES[name], subdir=name)
        if res.rc != 0 or res.folder is None:
            raise RuntimeError(f"board case {name!r} did not write (rc = {res.rc}):\n{res.out}")
        _BOARDS[name] = res
    return _BOARDS[name]


def reference_path(case, file):
    return os.path.join(REFERENCES, case, file)
