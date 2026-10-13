"""
ParameterChecker.py  -  every rule the parameters must obey, in one place.

It is used by RunCoilGenerator.py, but can also be run alone to check the parameter
files without generating anything:

    python ParameterChecker.py

Two stages:
  1. check_parameters(P)            rules that need only the parameter values
                                     (types, ranges, combinations that cannot work)
  2. check_design(P, stator, rotor) rules that need the finished geometry
                                     (board edge, via clearances, page size ...)

Findings have three levels:
  ERROR    the board would be wrong or impossible - nothing is written
  WARNING  the board can be made, but something is likely to be a problem
  INFO     plain facts worth knowing (printed without colour)

Thresholds named "typical" below are general PCB-fab rules of thumb, not the limits of
any particular manufacturer: check yours.
"""

import difflib
import math
import os
import sys
import types

import BandLayout
import TXLayout

LAYER_NAME = {1: "F.Cu", 2: "In1.Cu", 3: "In2.Cu", 4: "B.Cu"}
_LAYER_ORDER = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
COPPER_CONDUCTIVITY = 5.8e7
MU0 = 4.0e-7 * math.pi
KICAD_EDGE_CLEARANCE_MM = 0.5      # KiCad's default "copper to edge clearance" (Board Setup > Constraints)
RECEIVER_ICS = ("IPS2550", "IPS2200")   # the ICs CoilElectrics.py knows the limits of (RECEIVER_IC)


# =============================================================================
# colours
# =============================================================================
class Colour:
    enabled = False

    @classmethod
    def setup(cls, force=None):
        if force is None:
            force = None if "FORCE_COLOR" not in os.environ else True
        if "NO_COLOR" in os.environ and force is None:
            cls.enabled = False
        elif force is not None:
            cls.enabled = bool(force)
        else:
            cls.enabled = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
        if cls.enabled and os.name == "nt":
            os.system("")                      # switches the Windows console to ANSI mode

    @classmethod
    def _wrap(cls, code, s):
        return f"\033[{code}m{s}\033[0m" if cls.enabled else s

    red = classmethod(lambda c, s: c._wrap("1;31", s))
    yellow = classmethod(lambda c, s: c._wrap("1;33", s))
    green = classmethod(lambda c, s: c._wrap("1;32", s))
    dim = classmethod(lambda c, s: c._wrap("2", s))
    bold = classmethod(lambda c, s: c._wrap("1", s))


# =============================================================================
# report
# =============================================================================
class Report:
    def __init__(self):
        self.items = []                         # (level, message)

    def error(self, msg):
        self.items.append(("error", msg))

    def warn(self, msg):
        self.items.append(("warning", msg))

    def info(self, msg):
        self.items.append(("info", msg))

    def extend(self, other):
        self.items.extend(other.items)

    @property
    def errors(self):
        return [m for l, m in self.items if l == "error"]

    @property
    def warnings(self):
        return [m for l, m in self.items if l == "warning"]

    def print(self, indent="  "):
        for level, msg in self.items:
            paint = {"error": Colour.red, "warning": Colour.yellow}.get(level, lambda t: t)
            tag = {"error": "ERROR  ", "warning": "WARNING", "info": "info   "}[level]
            lines = msg.split("\n")
            print(f"{indent}{paint(tag + ' ' + lines[0])}" if level != "info"
                  else f"{indent}{Colour.dim(tag)} {lines[0]}")
            for ln in lines[1:]:
                print(indent + " " * 8 + paint(ln))


# =============================================================================
# the parameter table
# =============================================================================
# Each entry: (file, name, kind, options, active_when)
#   active_when(P) -> False means the value is ignored by the generators and is not checked.
SPEC = []


def _add(file, name, kind, active=None, **opt):
    SPEC.append((file, name, kind, opt, active))


def _get(P, name, default=None):
    return getattr(P, name, default)


_B, _RX, _TX, _RO = "Board_Parameters.py", "RX_Parameters.py", "TX_Parameters.py", "Rotor_Parameters.py"

_pcb4 = lambda P: _get(P, "PCB_LAYERS") == 4
_pcb2 = lambda P: _get(P, "PCB_LAYERS") == 2
_sub = lambda P: _get(P, "RX_SUBCOILS") in (2, 3)
_tabs = lambda P: str(_get(P, "RX_TABS", "all")).lower() in ("all", "single")   # bridging fingers at all
_tx_old = lambda P: not hasattr(P, "TX_SERIES")                      # a parameter file of an earlier version
_tx2 = lambda P: _get(P, "TX_LAYERS") == 2
_txa = lambda P: not _tx_old(P) or _tx2(P)                         # (earlier versions: TX_LAYERS = 1 meant Bottom)
_ser = lambda P: not _tx_old(P) and (_get(P, "TX_SERIES") is True or _get(P, "TX_LAYERS") == 1)
_par = lambda P: not _tx_old(P) and _get(P, "TX_SERIES") is False and _tx2(P)
_auto = lambda P: str(_get(P, "ROTOR_MODE", "")).lower() == "according_to_stator"
_custom = lambda P: str(_get(P, "ROTOR_MODE", "")).lower() == "custom"
_cover = lambda P: _get(P, "ROTOR_AUTO_COVER_TX", True) is True        # auto rotor over the TX turns (default)

# ---- Board_Parameters.py
_add(_B, "OUTPUT_DIR", "str")
_add(_B, "STATOR_FILE", "file")
_add(_B, "ROTOR_FILE", "file")
_add(_B, "CENTER_X_MM", "num")
_add(_B, "CENTER_Y_MM", "num")
_add(_B, "PAGE_SIZE_MM", "pair")
_add(_B, "PCB_LAYERS", "choice", values=(2, 4))
_add(_B, "VIA_DIAMETER_MM", "num", lo=0, lo_ex=True)
_add(_B, "VIA_DRILL_MM", "num", lo=0, lo_ex=True)
_add(_B, "MIN_CLEARANCE_MM", "num", lo=0, lo_ex=True)
_add(_B, "INNER_EDGE_INSET_MM", "num", lo=0)
_add(_B, "INNER_EDGE_RADIUS_MM", "num_or_none", optional=True, lo=0, lo_ex=True)
_add(_B, "OUTER_EDGE_OFFSET_MM", "num", lo=0)
_add(_B, "OUTER_EDGE_RADIUS_MM", "num_or_none", lo=0, lo_ex=True)
_add(_B, "OUTER_EDGE_TAIL_MARGIN_MM", "num", lo=0)
_add(_B, "EDGE_LINE_WIDTH_MM", "num", lo=0, lo_ex=True, hi=1.0)
_add(_B, "AIR_GAP_MM", "num", lo=0, lo_ex=True)
_add(_B, "PCB_THICKNESS_MM", "num", lo=0, lo_ex=True)
_add(_B, "EXCITATION_FREQ_HZ", "num", lo=0, lo_ex=True)
# electrical estimate (CoilElectrics.py); default = what it uses when the line is missing
_add(_B, "RECEIVER_IC", "ic", optional=True, default="IPS2550", values=RECEIVER_ICS)
_add(_B, "COPPER_THICKNESS_UM", "num", optional=True, default=35.0, lo=0, lo_ex=True, hi=500)
_add(_B, "TX_AMPLITUDE_VPP", "num_or_none", optional=True, default=None, lo=0, lo_ex=True, hi=100)

# ---- RX_Parameters.py
_add(_RX, "LOOPS", "int", lo=1, hi=16)
_add(_RX, "INSIDE_RADIUS_MM", "num_or_none", lo=0, lo_ex=True)
_add(_RX, "OUTSIDE_RADIUS_MM", "num_or_none", lo=0, lo_ex=True)
_add(_RX, "RX_R_BASE_MM", "num_or_none", optional=True, default=None, lo=0, lo_ex=True)
_add(_RX, "RX_A_MM", "num_or_none", optional=True, default=None, lo=0, lo_ex=True)
_add(_RX, "RX_TRACE_WIDTH_MM", "num", lo=0, lo_ex=True)
_add(_RX, "RX_NET_PHASE_0_2", "net")
_add(_RX, "RX_NET_PHASE_1_3", "net")
_add(_RX, "RX_ZERO_OFFSET_LOOP_FRACTION", "num")
_add(_RX, "RX_ZERO_OFFSET_DEG", "num")
_add(_RX, "RX_PROFILE", "choice", values=("equal_area", "cosine_r", "field_compensated"))
_add(_RX, "STEPS_PER_LOOP", "steps")
_add(_RX, "CHORD_TOLERANCE_MM", "num", lo=0, lo_ex=True)
_add(_RX, "RX_SUBCOILS", "choice", values=(1, 2, 3))
_add(_RX, "RX_SUBCOIL_SPLIT_ELEC_DEG", "num", active=_sub, lo=0, lo_ex=True)
_add(_RX, "RX_LAYER_A", "choice", active=_pcb4, values=(1, 2, 3, 4))
_add(_RX, "RX_LAYER_B", "choice", active=_pcb4, values=(1, 2, 3, 4))
_add(_RX, "RX_RISING_EDGE_LAYER", "choice", active=_pcb2, values=("F.Cu", "B.Cu"))
_add(_RX, "RX_VIA_ELECTRICAL_DEG", "num", lo=50.0, hi=130.0)
_add(_RX, "RX_TABS", "choice", values=("all", "single", "none"), ci=True)
_add(_RX, "RX_TAB_LENGTH_MM", "num", active=_tabs, lo=0)
_add(_RX, "RX_TAB_WIDTH_MM", "num", active=_tabs, lo=0, lo_ex=True)
_add(_RX, "RX_TAB_LAYER", "choice", values=("auto", 1, 2, 3, 4), ci=True, optional=True, default="auto")

# ---- TX_Parameters.py
_add(_TX, "TX_NET", "net")
_add(_TX, "TX_TURNS", "int", lo=1, hi=50)
_add(_TX, "TX_OFFSET_MM", "num", lo=0, lo_ex=True)
_add(_TX, "TX_PITCH_MM", "num", lo=0, lo_ex=True)
_add(_TX, "TX_TRACE_WIDTH_MM", "num", lo=0, lo_ex=True)
_add(_TX, "TX_STEPS", "int", lo=12, hi=20000)
_add(_TX, "TX_TAIL_EXTRA_MM", "num", lo=0)
_add(_TX, "TX_TURN_SHAPE", "choice", values=("stepped", "spiral"), ci=True)
_add(_TX, "TX_START_ANGLE_DEG", "auto_or_num")
_add(_TX, "TX_INSIDE_VIA_DISTANCE_MM", "num", optional=True, default=0.0, lo=-3.0, hi=3.0)
_add(_TX, "TX_STEPPED_ANGLE_DEG", "auto_or_num", lambda P: str(_get(P, "TX_TURN_SHAPE", "")).lower() != "spiral",
     optional=True, default="auto", lo=5.0, hi=90.0)
# TX layers (TXLayout.py): TX_LAYERS, TX_LAYER_A / TX_LAYER_B, TX_SERIES and its series / parallel block
_add(_TX, "TX_LAYERS", "choice", values=(1, 2))
_add(_TX, "TX_LAYER_A", "choice", active=_txa, values=(1, 2, 3, 4))
_add(_TX, "TX_LAYER_B", "choice", active=_tx2, values=(1, 2, 3, 4))
_add(_TX, "TX_SERIES", "bool", optional=True, default=None,
     missing="TX_SERIES is not in TX_Parameters.py: the TX layers are read as in the earlier version this file comes "
             "from (TX_LAYERS = 1 = the Bottom layer or TX_PLACEMENT, TX_LAYERS = 2 = series). Copy the TX LAYERS "
             "section from the TX_Parameters.py that came with this version to use TX_SERIES")
_add(_TX, "TX_SERIES_UNDERPASS_LAYER", "choice", active=_ser, values=("auto", 1, 2, 3, 4), ci=True, optional=True,
     default="auto")
_add(_TX, "TX_PARALLEL_BREAK_STYLE", "choice", active=_par, values=("stitched", "staggered", "auto"), ci=True,
     optional=True, default="stitched")
# settings of earlier versions (used only when TX_SERIES is not in the file)
_add(_TX, "TX_PLACEMENT", "choice", active=_tx_old, values=("bottom", "top", "both"), ci=True, optional=True,
     default="bottom")
_add(_TX, "TX_SECOND_LAYER", "choice", active=_tx_old, values=("auto", 1, 2, 3, 4), ci=True, optional=True,
     default="auto")
_add(_TX, "TX_BREAK_STYLE", "choice", active=_tx_old, values=("auto", "staggered", "stitched"), ci=True,
     optional=True, default="auto")

# ---- Rotor_Parameters.py
_add(_RO, "ROTOR_MODE", "choice", values=("according_to_stator", "custom"), ci=True)
_add(_RO, "ROTOR_AUTO_DUTY", "num", active=_auto, lo=0, hi=1, lo_ex=True, hi_ex=True)
_add(_RO, "ROTOR_AUTO_START_ANGLE_DEG", "num", active=_auto)
_add(_RO, "ROTOR_AUTO_EXTENSION_MM", "num_or_none", active=_auto)
_add(_RO, "ROTOR_AUTO_EXTENSION_INNER_MM", "num_or_none", active=_auto, optional=True)
_add(_RO, "ROTOR_AUTO_EXTENSION_OUTER_MM", "num_or_none", active=lambda P: _auto(P) and not _cover(P), optional=True)
_add(_RO, "ROTOR_AUTO_TX_CLEARANCE_MM", "num", active=lambda P: _auto(P) and not _cover(P), lo=0)
# default: what RotorGenerator.py uses (DEFAULT_COVER_TX, DEFAULT_TX_OVERHANG_MM) when the lines are missing
_add(_RO, "ROTOR_AUTO_COVER_TX", "bool", active=_auto, optional=True, default=True)
_add(_RO, "ROTOR_AUTO_TX_OVERHANG_MM", "num", active=lambda P: _auto(P) and _cover(P), optional=True, default=0.5,
     lo=-20.0, hi=20.0)
_add(_RO, "ROTOR_AUTO_EDGE_CLEARANCE_MM", "num", active=_auto, lo=0)
_add(_RO, "ROTOR_AUTO_COPPER_LAYERS", "rotor_layers", active=_auto)
_add(_RO, "ROTOR_CUSTOM_SECTORS", "int", active=_custom, lo=1, hi=64)
_add(_RO, "ROTOR_CUSTOM_DUTY", "num", active=_custom, lo=0, hi=1, lo_ex=True, hi_ex=True)
_add(_RO, "ROTOR_CUSTOM_START_ANGLE_DEG", "num", active=_custom)
_add(_RO, "ROTOR_CUSTOM_INNER_RADIUS_MM", "num", active=_custom, lo=0, lo_ex=True)
_add(_RO, "ROTOR_CUSTOM_OUTER_RADIUS_MM", "num", active=_custom, lo=0, lo_ex=True)
_add(_RO, "ROTOR_CUSTOM_COPPER_LAYERS", "rotor_layers", active=_custom)
_add(_RO, "ROTOR_CUSTOM_OUTLINE_RADIUS_MM", "num_or_none", active=_custom, lo=0, lo_ex=True)
_add(_RO, "ROTOR_CUSTOM_BORE_RADIUS_MM", "num_or_none", active=_custom, lo=0, lo_ex=True)
_add(_RO, "ROTOR_ARC_STEPS_PER_SECTOR", "int", lo=8, hi=5000)
# default: what RotorGenerator.py uses (DEFAULT_SOLDER_MASK_EXPANSION_MM) when the line is missing
_add(_RO, "ROTOR_SOLDER_MASK_EXPANSION_MM", "mask_expansion", optional=True, default=0.05, hi=5.0)

KNOWN_NAMES = {s[1] for s in SPEC}


# =============================================================================
# single-value checks
# =============================================================================
def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _range_text(o):
    lo, hi = o.get("lo"), o.get("hi")
    if lo is not None and hi is not None:
        return f"between {lo:g} and {hi:g}" + (" (both excluded)" if o.get("lo_ex") and o.get("hi_ex") else "")
    if lo is not None:
        return f"{'greater than' if o.get('lo_ex') else 'at least'} {lo:g}"
    if hi is not None:
        return f"{'less than' if o.get('hi_ex') else 'at most'} {hi:g}"
    return ""


def _in_range(x, o):
    lo, hi = o.get("lo"), o.get("hi")
    if lo is not None and (x <= lo if o.get("lo_ex") else x < lo):
        return False
    if hi is not None and (x >= hi if o.get("hi_ex") else x > hi):
        return False
    return True


def _check_value(name, val, kind, o):
    """-> (normalised value or None, error text or None)"""
    rng = _range_text(o)
    if kind == "num":
        if not _is_num(val):
            return None, f"{name} = {val!r}: must be a number" + (f" {rng}" if rng else "")
        if not _in_range(val, o):
            return None, f"{name} = {val:g}: must be {rng}"
        return float(val), None
    if kind == "num_or_none":
        if val is None:
            return None, None
        r, e = _check_value(name, val, "num", o)
        return r, (e.replace("must be a number", "must be None or a number") if e else None)
    if kind == "int":
        if isinstance(val, bool) or not isinstance(val, int):
            if _is_num(val) and float(val).is_integer():
                val = int(val)
            else:
                return None, f"{name} = {val!r}: must be a whole number" + (f" {rng}" if rng else "")
        if not _in_range(val, o):
            return None, f"{name} = {val}: must be {rng}"
        return int(val), None
    if kind == "choice":
        values = o["values"]
        if o.get("ci") and isinstance(val, str):
            key = val.lower()
            if key in values:
                return key, None
        elif not isinstance(val, bool) and val in values:
            return val, None
        opts = ", ".join(repr(x) for x in values)
        return None, f"{name} = {val!r}: must be one of {opts}"
    if kind == "str":
        if not isinstance(val, str) or not val.strip():
            return None, f"{name} = {val!r}: must be a non-empty text"
        return val, None
    if kind == "net":
        # the name is written between double quotes into the KiCad file: a quote, a backslash or a line break
        # in it would break the file
        if not isinstance(val, str) or not val.strip():
            return None, f"{name} = {val!r}: must be a non-empty text (a net name)"
        if any(c in val for c in '"\\') or any(ord(c) < 32 for c in val):
            return None, f"{name} = {val!r}: a net name must not contain double quotes, backslashes or line breaks"
        return val, None
    if kind == "file":
        if not isinstance(val, str) or not val.strip():
            return None, f"{name} = {val!r}: must be a file name"
        if os.path.basename(val) != val:
            return None, f"{name} = {val!r}: give only a file name; the folder is made by RunCoilGenerator.py"
        return val, None
    if kind == "pair":
        if (isinstance(val, (tuple, list)) and len(val) == 2 and all(_is_num(x) and x > 0 for x in val)):
            return (float(val[0]), float(val[1])), None
        return None, f"{name} = {val!r}: must be two positive numbers, e.g. (200, 200)"
    if kind == "steps":
        if val == "auto":
            return "auto", None
        if isinstance(val, int) and not isinstance(val, bool) and val % 8 == 0 and 48 <= val <= 4096:
            return val, None
        return None, f'{name} = {val!r}: must be "auto" or a multiple of 8 from 48 to 4096'
    if kind == "auto_or_num":
        if isinstance(val, str) and val.lower() == "auto":
            return "auto", None
        if _is_num(val):
            if not _in_range(val, o):
                return None, f'{name} = {val:g}: must be "auto" or a number of degrees {rng}'
            return float(val), None
        return None, f'{name} = {val!r}: must be a number of degrees or "auto"' + (f" ({rng})" if rng else "")
    if kind == "rotor_layers":
        if (isinstance(val, (list, tuple)) and len(val) >= 1
                and all(l in ("F.Cu", "B.Cu") for l in val) and len(set(val)) == len(val)):
            return list(val), None
        return None, f'{name} = {val!r}: must be a list such as ["F.Cu"] or ["F.Cu", "B.Cu"]'
    if kind == "bool":
        if isinstance(val, bool):
            return val, None
        return None, f"{name} = {val!r}: must be True or False"
    if kind == "ic":
        # a receiver IC name in any letter case, or None
        if val is None:
            return None, None
        if isinstance(val, str) and val.strip().upper() in o["values"]:
            return val.strip().upper(), None
        opts = ", ".join(repr(x) for x in o["values"])
        return None, f"{name} = {val!r}: must be one of {opts}, or None (no receiver IC checks)"
    if kind == "mask_expansion":
        # 0 or more = mask opening that many mm wider than the copper; exactly -1 = no opening
        what = "0 or more (mm), or exactly -1 for no mask opening"
        if not _is_num(val):
            return None, f"{name} = {val!r}: must be a number: {what}"
        if val == -1:
            return -1.0, None
        if val < 0:
            return None, f"{name} = {val:g}: must be {what}"
        if val > o["hi"]:
            return None, f"{name} = {val:g}: must be at most {o['hi']:g} mm (typical values are 0 ... 0.1)"
        return float(val), None
    raise AssertionError(kind)


# =============================================================================
# stage 1: parameters only
# =============================================================================
def load_values(P, rep):
    """Validate every individual parameter. Returns {name: normalised value} of the valid ones."""
    v = {}
    for file, name, kind, o, active in SPEC:
        if not hasattr(P, name):
            if o.get("optional"):               # added in a later version: a parameter file without it still works
                default = o.get("default")      # what the generators use when the line is missing (None if unset)
                v[name] = default
                try:
                    unused = active is not None and not active(P)
                except Exception:
                    unused = False
                if not unused and o.get("missing"):
                    rep.info(o["missing"])
                elif not unused:
                    shown = ("None" if default is None else
                             f"the default {default!r}" if isinstance(default, (bool, str, list, tuple)) else
                             f"the default {default:g}")
                    rep.info(f"{name} is not in {file}: {'treated as ' if default is None else 'using '}{shown} "
                             f"(copy the line from the {file} that came with this version to set it)")
            else:
                rep.error(f"{name} is missing - add it to {file}")
            continue
        raw = getattr(P, name)
        if active is not None:
            try:
                if not active(P):
                    continue                    # the generators ignore it in this configuration
            except Exception:
                pass
        val, err = _check_value(name, raw, kind, o)
        if err:
            rep.error(err + f"   ({file})")
        elif name in ("INNER_EDGE_RADIUS_MM", "OUTER_EDGE_RADIUS_MM", "ROTOR_AUTO_EXTENSION_MM",
                      "ROTOR_AUTO_EXTENSION_INNER_MM", "ROTOR_AUTO_EXTENSION_OUTER_MM",
                      "ROTOR_CUSTOM_OUTLINE_RADIUS_MM", "ROTOR_CUSTOM_BORE_RADIUS_MM"):
            v[name] = val                       # may legitimately be None
        else:
            v[name] = val
    # names that exist in the parameter files but are not known: probably typos
    for name in sorted(n for n in dir(P) if n.isupper() and not n.startswith("_")):
        if name not in KNOWN_NAMES:
            close = difflib.get_close_matches(name, KNOWN_NAMES, n=1, cutoff=0.7)
            hint = f" - did you mean {close[0]}?" if close else ""
            rep.warn(f"{name} is not a parameter of this program and is ignored{hint}")
    return v


def _rx_layers(v):
    if v.get("PCB_LAYERS") == 2:
        return {"F.Cu", "B.Cu"}
    if v.get("PCB_LAYERS") == 4 and "RX_LAYER_A" in v and "RX_LAYER_B" in v:
        return {LAYER_NAME[v["RX_LAYER_A"]], LAYER_NAME[v["RX_LAYER_B"]]}
    return None


_LAYOUT_NAMES = ("PCB_LAYERS", "RX_RISING_EDGE_LAYER", "RX_LAYER_A", "RX_LAYER_B", "RX_TABS", "RX_TAB_LAYER",
                 "TX_TURNS", "TX_OFFSET_MM", "TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "TX_TURN_SHAPE", "RX_TRACE_WIDTH_MM",
                 "VIA_DIAMETER_MM", "MIN_CLEARANCE_MM") + TXLayout.SHARED_NAMES + TXLayout.LEGACY_NAMES \
                + TXLayout.NEW_NAMES[1:]


def _tx_layout(P, v, rep):
    """TXLayout.tx_layout on the checked values (None when a value it needs is missing or invalid; an impossible
    combination is reported as an error)."""
    if v.get("PCB_LAYERS") not in (2, 4) or v.get("RX_TABS") is None:
        return None
    if v["PCB_LAYERS"] == 2 and v.get("RX_RISING_EDGE_LAYER") is None:
        return None
    if v["PCB_LAYERS"] == 4 and (v.get("RX_LAYER_A") is None or v.get("RX_LAYER_B") is None):
        return None
    new = hasattr(P, "TX_SERIES")
    if new and v.get("TX_SERIES") is None:
        return None                                        # (TX_SERIES itself is wrong: reported)
    d = {}
    for name in _LAYOUT_NAMES:
        if name in TXLayout.LEGACY_NAMES and new:
            continue
        if name in TXLayout.NEW_NAMES and not new:
            continue
        if v.get(name) is not None:
            d[name] = v[name]
        elif hasattr(P, name) and name in TXLayout.SHARED_NAMES + TXLayout.LEGACY_NAMES + TXLayout.NEW_NAMES:
            # a TX layer setting that failed its own check (reported): leave the layout alone
            active = next((s[4] for s in SPEC if s[1] == name), None)
            if active is None or active(P):
                return None
    if new:
        d["TX_SERIES"] = v["TX_SERIES"]
    try:
        return TXLayout.tx_layout(types.SimpleNamespace(**d))
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        rep.error(str(e) + "   (TX_Parameters.py)")
        return None


class _Skip(Exception):
    """a value BandLayout needs is missing or invalid (its own error is already reported)"""


def _outer_edge_room(v, lay=None):
    """StatorGenerator.outer_edge_room on checked values: how far inside a fixed OUTER_EDGE_RADIUS_MM the RX band
    ends.  None when a value it needs is missing or invalid (its own error is reported)."""
    need = ("OUTER_EDGE_OFFSET_MM", "OUTER_EDGE_TAIL_MARGIN_MM", "TX_OFFSET_MM", "TX_TURNS", "TX_PITCH_MM",
            "TX_TAIL_EXTRA_MM", "RX_TABS")
    if any(v.get(n) is None for n in need):
        return None
    margin = v["OUTER_EDGE_TAIL_MARGIN_MM"]
    room = max(v["OUTER_EDGE_OFFSET_MM"],
               v["TX_OFFSET_MM"] + v["TX_TURNS"] * v["TX_PITCH_MM"] + v["TX_TAIL_EXTRA_MM"] + margin)
    if str(v["RX_TABS"]).lower() in ("all", "single"):
        tab_need = ("RX_TAB_LENGTH_MM", "TX_TRACE_WIDTH_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM")
        if any(v.get(n) is None for n in tab_need):
            return None
        tab = max(v["RX_TAB_LENGTH_MM"],
                  v["TX_OFFSET_MM"] + (v["TX_TURNS"] - 1) * v["TX_PITCH_MM"] + v["TX_TRACE_WIDTH_MM"] / 2.0
                  + v["RX_TRACE_WIDTH_MM"] / 2.0 + v["MIN_CLEARANCE_MM"] + 0.2)
        if lay is not None and lay["goaround"]:
            tab = max(tab, _go_dims(v)["tip_off"])
        room = max(room, tab + v["RX_TRACE_WIDTH_MM"] / 2.0 + margin)
    return float(room)


def _go_dims(v):
    """TXLayout.goaround_dims on the checked values (None when one is missing)."""
    need = ("TX_TURNS", "TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "RX_TRACE_WIDTH_MM", "VIA_DIAMETER_MM", "MIN_CLEARANCE_MM",
            "TX_TURN_SHAPE", "TX_OFFSET_MM")
    if any(v.get(n) is None for n in need):
        return None
    return TXLayout.goaround_dims(types.SimpleNamespace(**{n: v[n] for n in need}))


def _check_tx_layout(P, v, rep, has, lay):
    """TX_SERIES and its blocks (or the settings of an earlier version), RX_TAB_LAYER."""
    if hasattr(P, "TX_SERIES"):
        old = [n for n in TXLayout.LEGACY_NAMES if hasattr(P, n)]
        if old:
            rep.warn(f"{', '.join(old)} {'is' if len(old) == 1 else 'are'} ignored: TX_LAYERS, TX_LAYER_A / TX_LAYER_B and TX_SERIES "
                     f"set the TX layers (delete the old line{'s' if len(old) > 1 else ''})")
        if v.get("TX_SERIES") is False and v.get("TX_LAYERS") == 1:
            rep.warn("TX_SERIES = False (a parallel TX) needs TX_LAYERS = 2: with TX_LAYERS = 1 the TX is on "
                     "TX_LAYER_A only")
    if lay is None:
        return
    T = v.get("TX_TURNS")
    tab, mode = lay["tab_layer"], lay["mode"]
    tabs = v.get("RX_TABS") in ("all", "single")
    go = lay["goaround"]
    if mode == "single":
        base, tail = lay["base_layer"], lay["tail_layer"]
        if not (base == "B.Cu" and tail == "F.Cu") or lay["windows_on"]:
            rep.info(f"series TX on {base}, the inner tail on {tail}"
                     + (f"; the turns go around every finger on {base} (go-around), with the brackets on "
                        f"{lay['bracket_layer']}" if go else (f"; the fingers cross it on {tab}" if tabs else "")))
    elif mode == "series2":
        p, q = lay["layers"]
        rep.info(f"series TX on two layers: {T} turns on {p} + {T} turns on {q}, joined by a via at the inner end"
                 + (f"; the turns on {tab} go around every finger (go-around), with the brackets on "
                    f"{lay['bracket_layer']} outside its turns" if go else (f"; the fingers cross it on {tab}" if tabs else "")))
    else:
        rep.info(f"parallel TX: the same {T} turns on {lay['layers'][0]} and {lay['layers'][1]}, stitched together "
                 f"through vias around the TX terminal"
                 + ((f" and around every finger on {tab}" if lay["style"] == "stitched" else
                     f"; the turns on {tab} go around every finger (go-around), with the brackets on "
                     f"{lay['bracket_layer']} outside its turns") if lay["windows_on"] else ""))
        style = v.get("TX_PARALLEL_BREAK_STYLE")
        if style == "staggered" and not lay["windows_on"]:
            rep.info('TX_PARALLEL_BREAK_STYLE = "staggered" is not used: no finger crosses the TX on its own layer')
    if lay["legacy"] and lay["windows_on"] and go:
        rep.info("the fingers cross the TX on its own layer: the turns now go around them (go-around, as in Hoxha et al. "
                 "2022), not under them")
    if go and mode != "parallel" and v.get("RX_TABS") == "all" and v.get("TX_START_ANGLE_DEG") != "auto":
        rep.info('fingers at every tip cross the TX on its own layer: the TX terminal has to fit between two of their '
                 'go-around windows; TX_START_ANGLE_DEG = "auto" puts it in the widest gap')
    if go:
        d = _go_dims(v)
        if d is not None and has("RX_TAB_LENGTH_MM") and v["RX_TAB_LENGTH_MM"] < d["tip_off"]:
            rep.info(f"go-around: the fingers run out past the outermost bracket, to the RX outside radius + "
                     f"{d['tip_off']:.2f} mm (RX_TAB_LENGTH_MM = {v['RX_TAB_LENGTH_MM']:g}); the board edge moves "
                     f"out with them")
    # the stitching vias of a parallel TX: a turn next to a via has to bend away from its pad
    if mode == "parallel" and has("TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "VIA_DIAMETER_MM", "MIN_CLEARANCE_MM",
                                  "TX_TURNS") and v["TX_TURNS"] > 1:
        p, tw, vr, clr = v["TX_PITCH_MM"], v["TX_TRACE_WIDTH_MM"], v["VIA_DIAMETER_MM"] / 2.0, v["MIN_CLEARANCE_MM"]
        delta = max(0.0, vr + tw / 2.0 + clr + 0.03 - p)
        if p - tw - delta < clr - 1e-9:
            rep.error(f"TX_PITCH_MM = {p:g} is too small for the stitching vias of the parallel TX (a turn next to a "
                      f"{2 * vr:g} mm via must bend {delta:.2f} mm away and would then touch the turn beyond it). "
                      f"Raise TX_PITCH_MM to at least {(vr + tw / 2.0 + clr + 0.03 + tw + clr) / 2.0:.2f} or use "
                      f"smaller vias (VIA_DIAMETER_MM)")


def check_parameters(P):
    """Stage 1.  Returns a Report; the values themselves are never changed."""
    rep = Report()
    v = load_values(P, rep)
    has = lambda *names: all(n in v and v[n] is not None for n in names)
    lay = _tx_layout(P, v, rep)                     # TX layers and the finger layer (TXLayout.py)

    # the RX band and the board edges (BandLayout.py): the band from INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM, from
    # RX_R_BASE_MM / RX_A_MM, or (both pairs None) from the board edges; an edge that is set is used as given
    inner_derived = outer_derived = False
    band = None
    band_names = BandLayout.RADII + BandLayout.CENTRE + BandLayout.EDGES + ("INNER_EDGE_INSET_MM",)
    band_ok = all(n in v for n in band_names) and v.get("INNER_EDGE_INSET_MM") is not None
    if band_ok:
        def _room():
            r = _outer_edge_room(v, lay)
            if r is None:
                raise _Skip()
            return r
        try:
            band = BandLayout.resolve(lambda n: v.get(n), _room)
        except _Skip:
            band = None
        except ValueError as e:
            rep.error(str(e))
            band = None
        for n in BandLayout.RADII:
            v.pop(n, None)                              # every rule below sees the band actually used
        if band is not None:
            v["INSIDE_RADIUS_MM"], v["OUTSIDE_RADIUS_MM"] = band["ri"], band["ro"]
            inner_derived, outer_derived = band["inner_from"] == "edge", band["outer_from"] == "edge"
            if band["mode"] == "centre":
                rep.info(f"RX_R_BASE_MM = {v['RX_R_BASE_MM']:g}, RX_A_MM = {v['RX_A_MM']:g}: the RX band runs from "
                         f"r = {band['ri']:g} to {band['ro']:g} mm")
            if inner_derived:
                rep.info(f"INNER_EDGE_RADIUS_MM = {v['INNER_EDGE_RADIUS_MM']:g} sets the centre hole: the RX band starts "
                         f"INNER_EDGE_INSET_MM = {v['INNER_EDGE_INSET_MM']:g} outside it, at r = {band['ri']:g} mm")
            if outer_derived:
                rep.info(f"OUTER_EDGE_RADIUS_MM = {v['OUTER_EDGE_RADIUS_MM']:g} sets the outer board edge: the RX band "
                         f"ends {v['OUTER_EDGE_RADIUS_MM'] - band['ro']:g} mm inside it (room for the TX turns, the TX "
                         f"tail and the margins), at r = {band['ro']:g} mm")
            both = [n for n, how in (("INNER_EDGE_RADIUS_MM", band["inner_from"]),
                                     ("OUTER_EDGE_RADIUS_MM", band["outer_from"])) if how == "both"]
            if both:
                rep.info(f"the RX band and {' and '.join(both)} are all set: each is used as given (the board is "
                         f"not fitted to the band)")

    # ------------------------------------------------------------ RX geometry
    if has("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM"):
        ri, ro = v["INSIDE_RADIUS_MM"], v["OUTSIDE_RADIUS_MM"]
        if ri < ro:
            if has("VIA_DIAMETER_MM", "MIN_CLEARANCE_MM", "RX_TRACE_WIDTH_MM"):
                width = ro - ri
                if width < v["VIA_DIAMETER_MM"]:
                    rep.error(f"the RX band ({width:g} mm) is narrower than one via "
                              f"({v['VIA_DIAMETER_MM']:g} mm): the outer and inner tip vias would overlap")
                elif width < v["VIA_DIAMETER_MM"] + v["MIN_CLEARANCE_MM"] + v["RX_TRACE_WIDTH_MM"]:
                    rep.warn(f"the RX band ({width:g} mm) is very narrow for {v['VIA_DIAMETER_MM']:g} mm vias: "
                             f"outer and inner tip vias of the same curve will be crowded")
    if has("LOOPS", "INSIDE_RADIUS_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM") and v["LOOPS"] >= 1:
        # the curves of a coil run side by side near the band centre: spacing there is about
        # circumference / (4 * loops) per quarter period; it must hold two traces plus a gap
        quarter = 2 * math.pi * v["INSIDE_RADIUS_MM"] / (4 * v["LOOPS"])
        need = v["RX_TRACE_WIDTH_MM"] + v["MIN_CLEARANCE_MM"]
        if quarter < 3 * need:
            rep.warn(f"at the inner radius a quarter of one loop is only {quarter:.2f} mm of arc for "
                     f"{v['LOOPS']} loops: the RX traces will be tightly packed (trace + clearance = "
                     f"{need:g} mm); check the clearance warnings printed while building")

    # ------------------------------------------------------------ widths, vias, clearance
    for nm in ("RX_TRACE_WIDTH_MM", "TX_TRACE_WIDTH_MM"):
        if has(nm) and v[nm] < 0.1:
            rep.warn(f"{nm} = {v[nm]:g} mm is very fine (typical fabs start around 0.1 mm); "
                     f"check your manufacturer's limit")
    if has("MIN_CLEARANCE_MM") and v["MIN_CLEARANCE_MM"] < 0.1:
        rep.warn(f"MIN_CLEARANCE_MM = {v['MIN_CLEARANCE_MM']:g} mm is tighter than typical fab limits (about 0.1 mm)")
    if has("VIA_DIAMETER_MM", "VIA_DRILL_MM"):
        d, dr = v["VIA_DIAMETER_MM"], v["VIA_DRILL_MM"]
        if dr >= d:
            rep.error(f"VIA_DRILL_MM ({dr:g}) must be smaller than VIA_DIAMETER_MM ({d:g})")
        elif (d - dr) / 2 < 0.1:
            rep.warn(f"via annular ring is {(d - dr) / 2:.3f} mm; below about 0.1 mm many fabs cannot "
                     f"guarantee the pad around the drill")

    # ------------------------------------------------------------ layers
    rx_l, tx_l = _rx_layers(v), (lay["turn_layers"] if lay else None)
    if v.get("PCB_LAYERS") == 4 and has("RX_LAYER_A", "RX_LAYER_B"):
        a, b = v["RX_LAYER_A"], v["RX_LAYER_B"]
        if a == b:
            rep.error("RX_LAYER_A and RX_LAYER_B must be different layers")
        elif {a, b} != {1, 2}:
            rep.warn(f"RX coils on {LAYER_NAME[a]} + {LAYER_NAME[b]}: in a standard 4-layer stack-up "
                     f"Top + Inner 1 (RX_LAYER_A=1, RX_LAYER_B=2) are the closest pair; a larger "
                     f"spacing between the two coil layers weakens and distorts the signal")
    _check_tx_layout(P, v, rep, has, lay)

    # ------------------------------------------------------------ RX sub-coils / profile
    n_sub = v.get("RX_SUBCOILS")
    n_sub = None if n_sub is None else int(n_sub)              # (2.0 is accepted as 2)
    if n_sub in (2, 3) and has("RX_SUBCOIL_SPLIT_ELEC_DEG"):
        sp = v["RX_SUBCOIL_SPLIT_ELEC_DEG"]
        # the receiver curves sit at (sub-coil offset + k * 90) electrical degrees: two of them on the same angle
        # are the same curve twice, and no layout exists (the generator would search for a long time and fail)
        even = 90.0 / n_sub                                         # the split that spaces all curves evenly
        offs = [(s - (n_sub - 1) / 2.0) * sp for s in range(n_sub)]
        angs = sorted((o + 90.0 * k) % 360.0 for o in offs for k in range(4))
        spacing = min((angs[(i + 1) % len(angs)] - angs[i]) % 360.0 for i in range(len(angs)))
        if (n_sub - 1) * sp >= 180.0:
            rep.error(f"RX_SUBCOIL_SPLIT_ELEC_DEG ({sp:g}) is too large: (RX_SUBCOILS - 1) * split "
                      f"must stay below 180")
        elif spacing < 1e-6:
            rep.error(f"RX_SUBCOIL_SPLIT_ELEC_DEG = {sp:g} with RX_SUBCOILS = {n_sub} puts two receiver curves on "
                      f"top of each other (within a sub-coil the curves are 90 electrical degrees apart), so no "
                      f"layout exists.\nUse {even:g}: it spaces all the curves evenly.")
        elif n_sub == 2 and not (35.0 <= sp <= 55.0):
            rep.warn(f"RX_SUBCOIL_SPLIT_ELEC_DEG = {sp:g}: the tip vias of the sin and cos coils end up "
                     f"{sp:g} and {90 - sp:g} electrical degrees apart; far from 45 they crowd each "
                     f"other (about 35 ... 55 was verified workable)")
        elif n_sub == 3 and spacing < 0.8 * even:
            rep.warn(f"RX_SUBCOIL_SPLIT_ELEC_DEG = {sp:g} with 3 sub-coils: some receiver curves are only "
                     f"{spacing:.0f} electrical degrees apart, which crowds their vias; {even:g} spaces them evenly")
        if n_sub == 3:
            rep.warn(f"RX_SUBCOILS = 3 is crowded: on the default 38 ... 51 mm band with 0.8 mm vias it was not "
                     f"clean at any loop count tried (1 ... 12), even at the even split of {even:g} electrical "
                     f"degrees; it needs a wide RX band or small vias - watch the clearance warnings")
        if n_sub == 2 and has("LOOPS") and v["LOOPS"] >= 13:
            rep.warn(f"RX_SUBCOILS = 2 with {v['LOOPS']} loops failed the via clearances at the default "
                     f"38 ... 51 mm band; a wider band or 1 sub-coil is safer")
    # ------------------------------------------------------------ electrical estimate: units
    if has("EXCITATION_FREQ_HZ") and not 1e5 <= v["EXCITATION_FREQ_HZ"] <= 5e7:
        rep.warn(f"EXCITATION_FREQ_HZ = {v['EXCITATION_FREQ_HZ']:g} Hz is far from the 1 ... 10 MHz that inductive "
                 f"position sensors run at (the value is in hertz: 3.5e6 = 3.5 MHz)")
    if has("COPPER_THICKNESS_UM") and not 9.0 <= v["COPPER_THICKNESS_UM"] <= 210.0:
        rep.warn(f"COPPER_THICKNESS_UM = {v['COPPER_THICKNESS_UM']:g} um is far outside the usual 18 ... 105 um "
                 f"(the value is in micrometres: 35 = 1 oz copper)")
    if v.get("RX_PROFILE") == "field_compensated":
        rep.info("RX_PROFILE = field_compensated uses AIR_GAP_MM, PCB_THICKNESS_MM and the TX turns to "
                 "shape the curves; change any of them and the RX copper changes with it")

    # ------------------------------------------------------------ RX resolution
    if has("STEPS_PER_LOOP", "LOOPS", "OUTSIDE_RADIUS_MM") and v["STEPS_PER_LOOP"] != "auto":
        d = 2 * math.pi / (v["LOOPS"] * v["STEPS_PER_LOOP"])
        sag = v["OUTSIDE_RADIUS_MM"] * d * d / 8
        if sag > 0.01:
            rep.warn(f"STEPS_PER_LOOP = {v['STEPS_PER_LOOP']} gives about {sag:.3f} mm chord error at the "
                     f"outer radius for {v['LOOPS']} loops; use \"auto\" or a larger value")

    # ------------------------------------------------------------ fingers
    if v.get("RX_TABS") in ("all", "single") and has("RX_TAB_WIDTH_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM"):
        gap = v["RX_TAB_WIDTH_MM"] - v["RX_TRACE_WIDTH_MM"]
        if gap < v["MIN_CLEARANCE_MM"]:
            rep.error(f"the two legs of a bridging finger are only {gap:.3f} mm apart "
                      f"(RX_TAB_WIDTH_MM - RX_TRACE_WIDTH_MM); need at least MIN_CLEARANCE_MM = "
                      f"{v['MIN_CLEARANCE_MM']:g}. Raise RX_TAB_WIDTH_MM.")
        if v["RX_TAB_WIDTH_MM"] < 0.6:
            rep.warn(f"RX_TAB_WIDTH_MM = {v['RX_TAB_WIDTH_MM']:g}: narrower than about 0.6 mm is hard to etch")
    if (v.get("RX_TABS") in ("all", "single") and has("OUTSIDE_RADIUS_MM", "RX_TAB_LENGTH_MM", "TX_OFFSET_MM", "TX_PITCH_MM",
                                           "TX_TURNS", "TX_TRACE_WIDTH_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM")):
        ro = v["OUTSIDE_RADIUS_MM"]
        tx_outer = ro + v["TX_OFFSET_MM"] + (v["TX_TURNS"] - 1) * v["TX_PITCH_MM"]
        need = tx_outer + v["TX_TRACE_WIDTH_MM"] / 2 + v["RX_TRACE_WIDTH_MM"] / 2 + v["MIN_CLEARANCE_MM"] + 0.2
        if ro + v["RX_TAB_LENGTH_MM"] < need:
            rep.info(f"RX_TAB_LENGTH_MM = {v['RX_TAB_LENGTH_MM']:g} does not clear the outermost TX turn; "
                     f"the fingers will be lengthened to reach r = {need:.2f} mm")

    # ------------------------------------------------------------ TX
    if has("TX_PITCH_MM", "TX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM"):
        gap = v["TX_PITCH_MM"] - v["TX_TRACE_WIDTH_MM"]
        if v.get("TX_TURNS", 1) > 1 or (lay is not None and lay["mode"] != "single"):
            if gap < v["MIN_CLEARANCE_MM"]:
                rep.error(f"TX turns are only {gap:.3f} mm apart (TX_PITCH_MM - TX_TRACE_WIDTH_MM); need at "
                          f"least MIN_CLEARANCE_MM = {v['MIN_CLEARANCE_MM']:g}. Raise TX_PITCH_MM.")
            elif gap < v["MIN_CLEARANCE_MM"] + 0.02:
                rep.warn(f"TX turns are {gap:.3f} mm apart, practically equal to MIN_CLEARANCE_MM = "
                         f"{v['MIN_CLEARANCE_MM']:g}: the polyline chords make the real gap a hair smaller "
                         f"(a 0.4 mm pitch with 0.2 mm traces and 0.2 mm clearance was measured to fail). "
                         f"Raise TX_PITCH_MM a little")
    if has("OUTSIDE_RADIUS_MM", "TX_OFFSET_MM", "TX_TRACE_WIDTH_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM") \
            and rx_l and tx_l and (rx_l & tx_l):
        room = v["TX_OFFSET_MM"] - (v["RX_TRACE_WIDTH_MM"] + v["TX_TRACE_WIDTH_MM"]) / 2
        if room < v["MIN_CLEARANCE_MM"]:
            rep.error(f"the first TX turn is only {room:.3f} mm from the outer RX copper on the same layer "
                      f"({', '.join(sorted(rx_l & tx_l))}); need MIN_CLEARANCE_MM = {v['MIN_CLEARANCE_MM']:g}. "
                      f"Raise TX_OFFSET_MM to at least "
                      f"{v['MIN_CLEARANCE_MM'] + (v['RX_TRACE_WIDTH_MM'] + v['TX_TRACE_WIDTH_MM']) / 2:.2f}.")
    if has("TX_INSIDE_VIA_DISTANCE_MM", "TX_OFFSET_MM", "VIA_DIAMETER_MM", "RX_TRACE_WIDTH_MM", "MIN_CLEARANCE_MM"):
        dv = v["TX_INSIDE_VIA_DISTANCE_MM"]
        room = v["TX_OFFSET_MM"] - v["VIA_DIAMETER_MM"] / 2 - v["RX_TRACE_WIDTH_MM"] / 2 - v["MIN_CLEARANCE_MM"]
        if dv > room + 1e-9:
            rep.warn(f"TX_INSIDE_VIA_DISTANCE_MM = {dv:g} puts the TX terminal via within MIN_CLEARANCE_MM of the RX band "
                     f"(its outer tips reach the RX outside radius): at most {room:.2f} mm with these settings, or raise "
                     f"TX_OFFSET_MM")
        elif dv < 0:
            rep.warn(f"TX_INSIDE_VIA_DISTANCE_MM = {dv:g} moves the TX terminal via outwards, onto the next TX turns; "
                     f"use 0 or a positive value")
    if has("TX_STEPS", "OUTSIDE_RADIUS_MM", "TX_OFFSET_MM"):
        r = v["OUTSIDE_RADIUS_MM"] + v["TX_OFFSET_MM"]
        sag = r * (1 - math.cos(math.pi / v["TX_STEPS"]))
        if sag > 0.01:
            rep.warn(f"TX_STEPS = {v['TX_STEPS']} gives about {sag:.3f} mm chord error on the TX turns; "
                     f"raise TX_STEPS")

    # ------------------------------------------------------------ nets
    if has("RX_NET_PHASE_0_2", "RX_NET_PHASE_1_3", "TX_NET"):
        names = [v["RX_NET_PHASE_0_2"], v["RX_NET_PHASE_1_3"], v["TX_NET"]]
        if len(set(names)) != 3:
            rep.error(f"net names must all be different (RX_NET_PHASE_0_2 = {names[0]!r}, "
                      f"RX_NET_PHASE_1_3 = {names[1]!r}, TX_NET = {names[2]!r})")

    # ------------------------------------------------------------ board outline
    if (not outer_derived and has("OUTER_EDGE_RADIUS_MM", "OUTSIDE_RADIUS_MM")
            and v["OUTER_EDGE_RADIUS_MM"] <= v["OUTSIDE_RADIUS_MM"]):
        rep.error(f"OUTER_EDGE_RADIUS_MM ({v['OUTER_EDGE_RADIUS_MM']:g}) is inside the RX band "
                  f"(OUTSIDE_RADIUS_MM = {v['OUTSIDE_RADIUS_MM']:g})")

    # ------------------------------------------------------------ output files
    if has("STATOR_FILE", "ROTOR_FILE"):
        if v["STATOR_FILE"] == v["ROTOR_FILE"]:
            rep.error("STATOR_FILE and ROTOR_FILE are the same file name: the rotor would overwrite the stator")
        for nm in ("STATOR_FILE", "ROTOR_FILE"):
            if not v[nm].lower().endswith(".kicad_pcb"):
                rep.warn(f"{nm} = {v[nm]!r} does not end in .kicad_pcb; KiCad will not offer to open it")
    if has("OUTPUT_DIR"):
        try:
            import OutputDirectoryManager as _ODM
            d = _ODM.output_dir(types.SimpleNamespace(OUTPUT_DIR=v["OUTPUT_DIR"]))
        except ImportError:
            d = v["OUTPUT_DIR"]
        if os.path.exists(d) and not os.path.isdir(d):
            rep.error(f"OUTPUT_DIR {d!r} exists but is not a folder")
        elif os.path.isdir(d) and not os.access(d, os.W_OK):
            rep.error(f"OUTPUT_DIR {d!r} is not writable")
        elif not os.path.exists(d):
            rep.info(f"OUTPUT_DIR {d!r} does not exist yet and will be created (the Coil_... folder goes inside it)")

    # ------------------------------------------------------------ rotor
    mode = v.get("ROTOR_MODE")
    duty = v.get("ROTOR_AUTO_DUTY") if mode == "according_to_stator" else v.get("ROTOR_CUSTOM_DUTY")
    if duty is not None:
        factor = math.sin(math.pi * duty)
        # a metal fraction k/h removes the h-th harmonic of the rotor pattern (sin(h*pi*duty) = 0)
        nulled = [h for h in (3, 5, 7) if abs(duty * h - round(duty * h)) < 0.005 * h]
        extra = f"; it removes harmonic {nulled[0]} of the rotor pattern" if nulled else ""
        if factor < 0.7:
            rep.warn(f"rotor metal fraction {duty:g}: the fundamental signal is only {100 * factor:.0f} % of the "
                     f"maximum (reached at 0.5){extra}")
        elif nulled:
            rep.info(f"rotor metal fraction {duty:g} removes harmonic {nulled[0]} of the rotor pattern; "
                     f"the fundamental signal is {100 * factor:.0f} % of the maximum (reached at 0.5)")
        elif factor < 0.9:
            rep.info(f"rotor metal fraction {duty:g}: the fundamental signal is {100 * factor:.0f} % of the "
                     f"maximum (reached at 0.5)")
    if mode == "according_to_stator":
        e_all = v.get("ROTOR_AUTO_EXTENSION_MM")
        e_in, e_out = v.get("ROTOR_AUTO_EXTENSION_INNER_MM"), v.get("ROTOR_AUTO_EXTENSION_OUTER_MM")
        if e_all is not None and e_in is not None and e_out is not None:
            rep.info("ROTOR_AUTO_EXTENSION_MM is not used: the inner and the outer edge each have their own value")
        cover = v.get("ROTOR_AUTO_COVER_TX") is not False
        if cover and (e_out is not None or (e_all is not None and e_in is not None)):
            rep.info("ROTOR_AUTO_COVER_TX = True: the outer edge of the rotor copper is set by ROTOR_AUTO_TX_OVERHANG_MM "
                     "(ROTOR_AUTO_EXTENSION_OUTER_MM is not used)")
        over = v.get("ROTOR_AUTO_TX_OVERHANG_MM")
        if cover and over is not None and over < 0:
            rep.info(f"ROTOR_AUTO_TX_OVERHANG_MM = {over:g}: the rotor copper ends over the TX turns, {-over:g} mm "
                     f"inside the outer edge of the outermost one")
        if has("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM", "AIR_GAP_MM") and not cover:
            default = e_all if e_all is not None else v["AIR_GAP_MM"]
            w_in = default if e_in is None else e_in
            w_out = default if e_out is None else e_out
            band = v["OUTSIDE_RADIUS_MM"] - v["INSIDE_RADIUS_MM"]
            if band > 0 and band + w_in + w_out <= 0:        # (a band of no width is reported above)
                rep.error(f"the rotor copper would have no width: the RX band is {band:g} mm wide and the copper "
                          f"would reach {w_in:+g} mm (inner edge) and {w_out:+g} mm (outer edge) past it.\n"
                          f"Raise ROTOR_AUTO_EXTENSION_INNER_MM / ROTOR_AUTO_EXTENSION_OUTER_MM "
                          f"(or ROTOR_AUTO_EXTENSION_MM).")
    if mode == "custom":
        n = v.get("ROTOR_CUSTOM_SECTORS")
        if n is not None and has("LOOPS") and n != v["LOOPS"]:
            rep.warn(f"ROTOR_CUSTOM_SECTORS = {n} but LOOPS = {v['LOOPS']}: the rotor needs one sector per "
                     f"loop, otherwise the sensor does not give a single clean sine period per sector")
        ri_, ro_ = v.get("ROTOR_CUSTOM_INNER_RADIUS_MM"), v.get("ROTOR_CUSTOM_OUTER_RADIUS_MM")
        if ri_ is not None and ro_ is not None:
            if ri_ >= ro_:
                rep.error(f"ROTOR_CUSTOM_INNER_RADIUS_MM ({ri_:g}) must be smaller than "
                          f"ROTOR_CUSTOM_OUTER_RADIUS_MM ({ro_:g})")
            else:
                bore, outline = v.get("ROTOR_CUSTOM_BORE_RADIUS_MM"), v.get("ROTOR_CUSTOM_OUTLINE_RADIUS_MM")
                if bore is not None and bore >= ri_:
                    rep.error(f"ROTOR_CUSTOM_BORE_RADIUS_MM ({bore:g}) must be smaller than the inner copper "
                              f"radius ({ri_:g})")
                if outline is not None and outline <= ro_:
                    rep.error(f"ROTOR_CUSTOM_OUTLINE_RADIUS_MM ({outline:g}) must be larger than the outer "
                              f"copper radius ({ro_:g})")
                # copper close to the board edge: KiCad's design-rule check flags it (measured to the edge line)
                if bore is not None and 0 < ri_ - bore < KICAD_EDGE_CLEARANCE_MM:
                    rep.warn(f"the custom rotor copper starts only {ri_ - bore:.2f} mm outside the bore "
                             f"(ROTOR_CUSTOM_INNER_RADIUS_MM {ri_:g}, ROTOR_CUSTOM_BORE_RADIUS_MM {bore:g}): KiCad's "
                             f"design-rule check asks for {KICAD_EDGE_CLEARANCE_MM:g} mm between copper and the board "
                             f"edge by default. Raise ROTOR_CUSTOM_INNER_RADIUS_MM to "
                             f"{bore + KICAD_EDGE_CLEARANCE_MM:g} or lower the bore")
                if outline is not None and 0 < outline - ro_ < KICAD_EDGE_CLEARANCE_MM:
                    rep.warn(f"the custom rotor copper ends only {outline - ro_:.2f} mm inside the outline "
                             f"(ROTOR_CUSTOM_OUTER_RADIUS_MM {ro_:g}, ROTOR_CUSTOM_OUTLINE_RADIUS_MM {outline:g}): "
                             f"KiCad's design-rule check asks for {KICAD_EDGE_CLEARANCE_MM:g} mm between copper and "
                             f"the board edge by default. Lower ROTOR_CUSTOM_OUTER_RADIUS_MM to "
                             f"{outline - KICAD_EDGE_CLEARANCE_MM:g} or raise the outline")
                if has("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM"):
                    if ri_ > v["INSIDE_RADIUS_MM"] or ro_ < v["OUTSIDE_RADIUS_MM"]:
                        rep.warn(f"the custom rotor copper ({ri_:g} ... {ro_:g} mm) does not cover the whole RX "
                                 f"band ({v['INSIDE_RADIUS_MM']:g} ... {v['OUTSIDE_RADIUS_MM']:g} mm): the signal "
                                 f"drops and distorts near the uncovered edge")
                    if has("TX_OFFSET_MM", "TX_TRACE_WIDTH_MM"):
                        tx_in = v["OUTSIDE_RADIUS_MM"] + v["TX_OFFSET_MM"] - v["TX_TRACE_WIDTH_MM"] / 2
                        if ro_ > tx_in:
                            rep.info(f"the custom rotor copper reaches r = {ro_:g} mm, over the TX turns (first turn "
                                     f"at {tx_in:g} mm), as the automatic rotor does by default: more signal, and a "
                                     f"larger change of the TX inductance (see the electrical estimate)")
    e_mask = v.get("ROTOR_SOLDER_MASK_EXPANSION_MM")             # -1 = no mask opening
    if e_mask is not None and e_mask > 0.25:
        rep.warn(f"ROTOR_SOLDER_MASK_EXPANSION_MM = {e_mask:g}: the mask opening is that much wider than the "
                 f"copper on every side, which leaves a wide ring of bare laminate around each sector. Typical "
                 f"values are 0 ... 0.1 mm")
    if mode == "custom" and e_mask is not None and e_mask > 0 and has("ROTOR_CUSTOM_INNER_RADIUS_MM") \
            and e_mask >= v["ROTOR_CUSTOM_INNER_RADIUS_MM"]:
        rep.error(f"ROTOR_SOLDER_MASK_EXPANSION_MM ({e_mask:g}) must be smaller than the inner copper radius "
                  f"(ROTOR_CUSTOM_INNER_RADIUS_MM = {v['ROTOR_CUSTOM_INNER_RADIUS_MM']:g}): the mask opening "
                  f"would reach the rotor centre")
    if has("ROTOR_ARC_STEPS_PER_SECTOR", "OUTSIDE_RADIUS_MM"):
        n = (v.get("ROTOR_CUSTOM_SECTORS") if mode == "custom" else v.get("LOOPS")) or 1
        d = (duty or 0.5) * 2 * math.pi / n / v["ROTOR_ARC_STEPS_PER_SECTOR"]
        sag = (v.get("ROTOR_CUSTOM_OUTER_RADIUS_MM") if mode == "custom" and v.get("ROTOR_CUSTOM_OUTER_RADIUS_MM")
               else v["OUTSIDE_RADIUS_MM"]) * (1 - math.cos(d / 2))
        if sag > 0.05:
            rep.warn(f"ROTOR_ARC_STEPS_PER_SECTOR = {v['ROTOR_ARC_STEPS_PER_SECTOR']} gives about "
                     f"{sag:.3f} mm chord error on the rotor edge; raise it")
    return rep


# =============================================================================
# stage 2: finished geometry
# =============================================================================
def check_design(P, stator, rotor=None):
    """Rules that need the generated stator (and rotor).  Returns a Report."""
    rep = Report()
    R = stator.outer_edge_radius
    cx, cy = stator.cx, stator.cy
    ew = float(P.EDGE_LINE_WIDTH_MM)

    # board outline against what it must contain
    if P.OUTER_EDGE_RADIUS_MM is not None:
        need_tx = stator.tx_outer_radius + P.TX_TRACE_WIDTH_MM / 2 + ew / 2
        if R < need_tx - 1e-6:
            rep.error(f"OUTER_EDGE_RADIUS_MM = {R:g} cuts through the outermost TX turn "
                      f"(r = {stator.tx_outer_radius:g} mm); it must be at least {need_tx:.2f}")
        if stator.tab_end_radius is not None and R < stator.tab_end_radius + P.RX_TRACE_WIDTH_MM / 2 + ew / 2 - 1e-6:
            rep.error(f"OUTER_EDGE_RADIUS_MM = {R:g} cuts through the RX bridging fingers "
                      f"(they reach r = {stator.tab_end_radius:.2f} mm); raise it or set RX_TABS = \"none\" "
                      f"or shorten RX_TAB_LENGTH_MM")
        if R < stator.tx_tail_end_radius + ew / 2 - 1e-6:
            rep.error(f"OUTER_EDGE_RADIUS_MM = {R:g} cuts off the TX tail (it ends at r = "
                      f"{stator.tx_tail_end_radius:g} mm); raise it or lower TX_TAIL_EXTRA_MM")
        elif R < stator.tx_tail_end_radius + P.OUTER_EDGE_TAIL_MARGIN_MM - 1e-6:
            rep.warn(f"OUTER_EDGE_RADIUS_MM = {R:g}: the TX tail ends at r = {stator.tx_tail_end_radius:g} mm, "
                     f"only {R - stator.tx_tail_end_radius:.2f} mm from the board edge "
                     f"(OUTER_EDGE_TAIL_MARGIN_MM = {P.OUTER_EDGE_TAIL_MARGIN_MM:g})")

    # inner hole against the inner tip vias
    clear = stator.inner_edge_clear()
    if clear is not None and clear < 0:
        # the vias sit on the inner edge of the RX band, INNER_EDGE_INSET_MM from the hole: only the inset matters
        rep.error(f"the inner-tip vias run {-clear:.2f} mm over the centre-hole edge: raise "
                  f"INNER_EDGE_INSET_MM (now {P.INNER_EDGE_INSET_MM:g}) to at least "
                  f"{P.VIA_DIAMETER_MM / 2.0 + 0.3:g} (half a via plus 0.3 mm)")

    # copper touching copper
    if stator.min_via_clearance is not None and stator.min_via_clearance <= 0:
        rep.error(f"a via touches copper of another net (clearance {stator.min_via_clearance:.3f} mm): "
                  f"the board would short")

    # board against the KiCad page: the page grows (right and down) so that the board stays clear of the drawing
    # frame and the title block; only the top and left side depend on the centre position
    import StatorGenerator as SG                       # (already loaded: the stator was built with it)
    px, py = P.PAGE_SIZE_MM
    margin = SG.SHEET_FRAME_MM + SG.PAGE_GAP_MM
    if cx - R - ew / 2 < margin or cy - R - ew / 2 < margin:
        rep.warn(f"the board (outer radius {R:g} mm at {cx:g}, {cy:g}) comes within {margin:g} mm of the top or left "
                 f"edge of the KiCad page (the drawing frame); it will still be written, but it crosses the frame. "
                 f"Raise CENTER_X_MM / CENTER_Y_MM to at least {math.ceil(R + ew / 2 + margin):g}")
    else:
        w, h = SG.page_size(P, cx, cy, R)
        if (w, h) != (float(px), float(py)):
            rep.info(f"KiCad page {w:g} x {h:g} mm (PAGE_SIZE_MM {px:g} x {py:g} grown so that the board stays clear "
                     f"of the drawing frame and the title block)")

    # rotor
    if rotor is not None:
        for note in rotor.notes:
            rep.info(note)
        # a solder-mask opening that reaches the bore or the outline is cut off by the board edge
        e_mask = getattr(rotor, "mask_expansion", None)
        if e_mask:
            auto = rotor.mode == "according_to_stator"
            if rotor.bore_radius is not None and rotor.r_in - e_mask < rotor.bore_radius + ew / 2.0:
                fix = ("Raise ROTOR_AUTO_EDGE_CLEARANCE_MM or lower the expansion" if auto else
                       "Raise ROTOR_CUSTOM_INNER_RADIUS_MM, lower ROTOR_CUSTOM_BORE_RADIUS_MM or lower the expansion")
                rep.warn(f"the solder-mask opening (ROTOR_SOLDER_MASK_EXPANSION_MM = {e_mask:g}) reaches the "
                         f"bore edge: the copper is only {max(rotor.r_in - rotor.bore_radius - ew / 2.0, 0.0):.2f} "
                         f"mm from it, so the board edge cuts the opening. {fix}")
            if rotor.outline_radius is not None and rotor.r_out + e_mask > rotor.outline_radius - ew / 2.0:
                fix = ("Lower the expansion" if auto else
                       "Lower ROTOR_CUSTOM_OUTER_RADIUS_MM, raise ROTOR_CUSTOM_OUTLINE_RADIUS_MM or lower the "
                       "expansion")
                rep.warn(f"the solder-mask opening (ROTOR_SOLDER_MASK_EXPANSION_MM = {e_mask:g}) reaches the "
                         f"outline: the copper is only "
                         f"{max(rotor.outline_radius - ew / 2.0 - rotor.r_out, 0.0):.2f} mm from it, so the board "
                         f"edge cuts the opening. {fix}")
        if rotor.mode == "according_to_stator":
            cut = getattr(rotor, "cut_overhang", None)
            if cut is not None and cut[0] - cut[1] > 0.01:
                rep.warn(f"ROTOR_AUTO_TX_OVERHANG_MM = {cut[0]:g} does not fit: the rotor copper must stay "
                         f"ROTOR_AUTO_EDGE_CLEARANCE_MM = {P.ROTOR_AUTO_EDGE_CLEARANCE_MM:g} mm inside the board "
                         f"outline, so it ends {cut[1]:+.2f} mm past the outermost TX turn")
            # an edge that was asked for with ROTOR_AUTO_EXTENSION_INNER_MM / _OUTER_MM but had to be cut back
            for side, name, cut, why in (
                    ("inner", "ROTOR_AUTO_EXTENSION_INNER_MM", getattr(rotor, "cut_in", None),
                     f"ROTOR_AUTO_EDGE_CLEARANCE_MM = {P.ROTOR_AUTO_EDGE_CLEARANCE_MM:g} mm from the bore"),
                    ("outer", "ROTOR_AUTO_EXTENSION_OUTER_MM", getattr(rotor, "cut_out", None),
                     f"ROTOR_AUTO_TX_CLEARANCE_MM = {getattr(P, 'ROTOR_AUTO_TX_CLEARANCE_MM', '?')} mm inside "
                     f"the TX ring")):
                if cut is not None and cut[0] - cut[1] > 0.01:             # (less than 10 um is not worth a warning)
                    asked, allowed = cut
                    rep.warn(f"{name} = {asked:g} does not fit: the copper must stay {why}, so at the {side} edge "
                             f"it reaches {allowed:+.2f} mm past the RX band and the rotor is made with that")
            # copper that stops far short of the RX band leaves part of the receiver uncovered
            gap = float(P.AIR_GAP_MM)
            for side, ext in (("inner", rotor.ext_in), ("outer", rotor.ext_out)):
                if ext < -gap:
                    rep.warn(f"the rotor copper stops {-ext:.2f} mm short of the {side} edge of the RX band (more "
                             f"than one air gap): part of the receiver is not covered, so the signal drops and "
                             f"the harmonics grow")
    return rep


def classify_generator_output(text):
    """Turn the generator's own stderr lines into report items.
    "WARNING: ..." lines become warnings; a WARNING that reports a distance of zero or less means
    copper overlaps copper, which is an error (the board would short)."""
    import re
    rep = Report()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper().startswith("WARNING:"):
            msg = line[len("WARNING:"):].strip()
            m = re.search(r"(?:only|within)\s+(-?\d+(?:\.\d+)?)\s*mm", msg)
            if m and float(m.group(1)) <= 0.0:
                rep.error(msg + "  - the copper overlaps, the board would short")
            else:
                rep.warn(msg)
        else:
            rep.info(line)
    return rep


# =============================================================================
if __name__ == "__main__":
    # The project folders sit next to each other: Parameters, Generator, Analyser_And_Optimizer (and Output).
    # Put all three on the import path, so every program runs from any folder.  (All files in one folder works too.)
    _PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _sub in ("Analyser_And_Optimizer", "Generator", "Parameters"):
        _p = os.path.join(_PROJECT, _sub)
        if os.path.isdir(_p) and _p not in sys.path:
            sys.path.insert(0, _p)
    if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    Colour.setup()
    import Parameters as _P
    r = check_parameters(_P)
    r.print()
    if r.errors:
        print(Colour.red(f"{len(r.errors)} error(s) - fix the parameters before generating"))
        sys.exit(1)
    print(Colour.green("Parameters OK") + (Colour.yellow(f" ({len(r.warnings)} warning(s))") if r.warnings else ""))
