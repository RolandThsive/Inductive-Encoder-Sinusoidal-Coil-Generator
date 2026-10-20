"""
ParameterRules.py  -  the rules about ONE parameter at a time: is it there, is it the right kind of value (number,
whole number, one of the allowed words, True / False ...), is it in range, and the warnings about a single value
(a trace finer than typical fabs make, a frequency far from the usual range ...).  Names in the parameter files
that the program does not know are reported too (typos).  Rules between parameters are in ConflictRules.py.

load_values(P, rep) returns {name: normalised value} of every valid parameter; the rules below work on that.
"""

import difflib
import math
import os
import types

from Generator.Core import BoardLayout, Layers
from Generator.Stator.TX.TX_Shapes import DEFAULT_INSIDE_VIA_DISTANCE_MM

KICAD_EDGE_CLEARANCE_MM = 0.5      # KiCad's default "copper to edge clearance" (Board Setup > Constraints)
# parameters of earlier versions that are no longer read: what replaced them
RETIRED = {"RECEIVER_IC": "the receiver IC is now set in IC_Parameters.py (IC_NAME, IC_OSC_MIN_MHZ, IC_OSC_MAX_MHZ, "
                          "IC_MIN_RP_OHM)"}


# Each entry: (file, name, kind, options, active_when)
#   active_when(P) -> False means the value is ignored by the generators and is not checked.
SPEC = []


def _add(file, name, kind, active=None, **opt):
    SPEC.append((file, name, kind, opt, active))


def _get(P, name, default=None):
    return getattr(P, name, default)


_B, _RX, _TX, _RO = "Board_Parameters.py", "RX_Parameters.py", "TX_Parameters.py", "Rotor_Parameters.py"
_IC = "IC_Parameters.py"

_pcb4 = lambda P: _get(P, "PCB_LAYERS") == 4
_pcb2 = lambda P: _get(P, "PCB_LAYERS") == 2
_sub = lambda P: _get(P, "RX_SUBCOILS") in (2, 3)
_tabs = lambda P: str(_get(P, "RX_TABS", "all")).lower() in ("all", "single")   # bridging fingers at all
_wiring = lambda P: str(_get(P, "TX_WIRING", "")).strip().lower()
_tx2 = lambda P: _wiring(P) in ("series", "parallel")                              # two TX layers
_ser = lambda P: _wiring(P) in ("single", "series")                                # a series TX (one or two layers)
_par = lambda P: _wiring(P) == "parallel"                                          # a parallel TX


def _shape(P):
    """'diagonal' | 'arc' | 'spiral' (BoardLayout.tx_shape), None for a TX_SHAPE that is not valid (reported)."""
    try:
        return BoardLayout.tx_shape(P)
    except ValueError:
        return None
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
# electrical estimate (TX_Electrics.py); default = what it uses when the line is missing
_add(_B, "COPPER_THICKNESS_UM", "num", optional=True, default=35.0, lo=0, lo_ex=True, hi=500)
_add(_B, "COPPER_CONDUCTIVITY_S_M", "num", optional=True, default=5.8e7, lo=1e6, hi=1e8)
_add(_B, "TX_AC_RESISTANCE_FACTOR", "num", optional=True, default=2.0, lo=1.0, hi=20.0)
_add(_B, "STACKUP_PREPREG_MM", "num", optional=True, default=0.2, lo=0, lo_ex=True, hi=5.0, active=_pcb4)
_add(_B, "TANK_CAP_SERIES", "choice", values=("e6", "e12", "e24"), ci=True, optional=True, default="e12")
_add(_B, "GENERATOR_MODE", "choice", values=("normal", "strict"), ci=True, optional=True, default="normal")

# ---- RX_Parameters.py
_add(_RX, "LOOPS", "int", lo=1, hi=16)
_add(_RX, "INSIDE_RADIUS_MM", "num_or_none", lo=0, lo_ex=True)
_add(_RX, "OUTSIDE_RADIUS_MM", "num_or_none", lo=0, lo_ex=True)
_add(_RX, "RX_R_BASE_MM", "num_or_none", optional=True, default=None, lo=0, lo_ex=True)
_add(_RX, "RX_A_MM", "num_or_none", optional=True, default=None, lo=0, lo_ex=True)
_add(_RX, "RX_TRACE_WIDTH_MM", "num", lo=0, lo_ex=True)
_add(_RX, "RX_NET_PHASE_0_2", "net")
_add(_RX, "RX_NET_PHASE_1_3", "net")
_add(_RX, "RX_PROFILE", "choice", values=("equal_area", "cosine_r"))
_add(_RX, "STEPS_PER_LOOP", "steps")
_add(_RX, "RX_CHORD_TOLERANCE_MM", "num", optional=True, default=0.001, lo=0.001)
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
_add(_TX, "TX_STEPS", "auto_or_int", optional=True, default="auto", lo=12, hi=20000)
_add(_TX, "TX_CHORD_TOLERANCE_MM", "num", optional=True, default=0.001, lo=0.001)
_add(_TX, "TX_TAIL_EXTRA_MM", "num", lo=0)
_add(_TX, "TX_SHAPE", "choice", values=BoardLayout.TX_SHAPE_VALUES, ci=True)
_add(_TX, "TX_INSIDE_VIA_DISTANCE_MM", "num", lambda P: _shape(P) != "arc", optional=True,
     default=DEFAULT_INSIDE_VIA_DISTANCE_MM, lo=-3.0, hi=3.0)
_add(_TX, "TX_STEPPED_ANGLE_DEG", "num", lambda P: _shape(P) == "diagonal", lo=5.0, hi=90.0)
_add(_TX, "TX_STEPPED_ARC_RADIUS_MM", "auto_or_num", lambda P: _shape(P) == "arc",
     optional=True, default="auto", lo=0.0, lo_ex=True, hi=20.0, unit="mm")
# TX layers (Layers.py): TX_WIRING, TX_LAYER_A / TX_LAYER_B and the series / parallel block
_add(_TX, "TX_WIRING", "choice", values=Layers.TX_WIRING_VALUES, ci=True)
_add(_TX, "TX_LAYER_A", "choice", values=(1, 2, 3, 4))
_add(_TX, "TX_LAYER_B", "choice", active=_tx2, values=(1, 2, 3, 4))
_add(_TX, "TX_SERIES_UNDERPASS_LAYER", "choice", active=_ser, values=("auto", 1, 2, 3, 4), ci=True, optional=True,
     default="auto")
_add(_TX, "TX_PARALLEL_BREAK_STYLE", "choice", active=_par, values=("stitched", "staggered"), ci=True,
     optional=True, default="stitched")

# ---- Rotor_Parameters.py
_add(_RO, "ROTOR_MODE", "choice", values=("according_to_stator", "custom"), ci=True)
_add(_RO, "ROTOR_AUTO_DUTY", "num", active=_auto, lo=0, hi=1, lo_ex=True, hi_ex=True)
_add(_RO, "ROTOR_AUTO_START_ANGLE_DEG", "num", active=_auto)
_add(_RO, "ROTOR_AUTO_EXTENSION_MM", "num_or_none", active=_auto)
_add(_RO, "ROTOR_AUTO_EXTENSION_INNER_MM", "num_or_none", active=_auto, optional=True)
_add(_RO, "ROTOR_AUTO_EXTENSION_OUTER_MM", "num_or_none", active=lambda P: _auto(P) and not _cover(P), optional=True)
_add(_RO, "ROTOR_AUTO_TX_CLEARANCE_MM", "num", active=lambda P: _auto(P) and not _cover(P), lo=0)
# default: what RotorBuilder.py uses (DEFAULT_COVER_TX, DEFAULT_TX_OVERHANG_MM) when the lines are missing
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
_add(_RO, "ROTOR_PCB_THICKNESS_MM", "num_or_none", optional=True, default=None, lo=0, lo_ex=True, hi=20.0)
_add(_RO, "ROTOR_ARC_STEPS_PER_SECTOR", "auto_or_int", optional=True, default="auto", lo=8, hi=5000)
_add(_RO, "ROTOR_CHORD_TOLERANCE_MM", "num", optional=True, default=0.001, lo=0.001)
# default: what RotorBuilder.py uses (DEFAULT_SOLDER_MASK_EXPANSION_MM) when the line is missing
_add(_RO, "ROTOR_SOLDER_MASK_EXPANSION_MM", "mask_expansion", optional=True, default=0.05, hi=5.0)

# ---- IC_Parameters.py  (electrical estimate, TX_Electrics.py; default = what it uses when the line is missing:
#      the IPS2550)
_add(_IC, "IC_NAME", "str_or_none", optional=True, default="IPS2550")
_add(_IC, "IC_OSC_MIN_MHZ", "num_or_none", optional=True, default=2.0, lo=0, lo_ex=True, hi=100.0)
_add(_IC, "IC_OSC_MAX_MHZ", "num_or_none", optional=True, default=5.6, lo=0, lo_ex=True, hi=100.0)
_add(_IC, "IC_MIN_RP_OHM", "num_or_none", optional=True, default=250.0, lo=0, hi=1e6)
_add(_IC, "IC_SPLIT_TANK_CAPS", "bool", optional=True, default=True)

KNOWN_NAMES = {s[1] for s in SPEC}

def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _range_text(o):
    lo, hi = o.get("lo"), o.get("hi")
    lo_txt = None if lo is None else f"{'greater than' if o.get('lo_ex') else 'at least'} {lo:g}"
    hi_txt = None if hi is None else f"{'less than' if o.get('hi_ex') else 'at most'} {hi:g}"
    if lo is not None and hi is not None:
        if not o.get("lo_ex") and not o.get("hi_ex"):
            return f"between {lo:g} and {hi:g}"
        return f"{lo_txt} and {hi_txt}"                # (each bound says whether it is excluded)
    return lo_txt or hi_txt or ""


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
    if kind == "str_or_none":
        if val is None:
            return None, None
        if not isinstance(val, str) or not val.strip():
            return None, f"{name} = {val!r}: must be None or a non-empty text"
        return val.strip(), None
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
    if kind == "auto_or_int":
        if isinstance(val, str) and val.lower() == "auto":
            return "auto", None
        if isinstance(val, int) and not isinstance(val, bool):
            if not _in_range(val, o):
                return None, f'{name} = {val}: must be "auto" or a whole number {rng}'
            return int(val), None
        return None, f'{name} = {val!r}: must be "auto" or a whole number' + (f" ({rng})" if rng else "")
    if kind == "auto_or_num":
        if isinstance(val, str) and val.lower() == "auto":
            return "auto", None
        if _is_num(val):
            if not _in_range(val, o):
                return None, f'{name} = {val:g}: must be "auto" or a number of {o.get("unit", "mm")} {rng}'
            return float(val), None
        return None, (f'{name} = {val!r}: must be a number of {o.get("unit", "mm")} or "auto"'
                      + (f" ({rng})" if rng else ""))
    if kind == "rotor_layers":
        if (isinstance(val, (list, tuple)) and len(val) >= 1
                and all(l in ("F.Cu", "B.Cu") for l in val) and len(set(val)) == len(val)):
            return list(val), None
        return None, f'{name} = {val!r}: must be a list such as ["F.Cu"] or ["F.Cu", "B.Cu"]'
    if kind == "bool":
        if isinstance(val, bool):
            return val, None
        return None, f"{name} = {val!r}: must be True or False"
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
                if not unused:
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
        if name in RETIRED:
            rep.warn(f"{name} is no longer used and is ignored: {RETIRED[name]}")
        elif name not in KNOWN_NAMES:
            close = difflib.get_close_matches(name, KNOWN_NAMES, n=1, cutoff=0.7)
            hint = f" - did you mean {close[0]}?" if close else ""
            rep.warn(f"{name} is not a parameter of this program and is ignored{hint}")
    return v



def single_value_warnings(v, rep):
    """Warnings and notes about one value on its own (the value is valid; it is just unusual) - and the errors about
    OUTPUT_DIR (a folder that cannot be written or created)."""
    has = lambda *names: all(n in v and v[n] is not None for n in names)
    for nm in ("RX_TRACE_WIDTH_MM", "TX_TRACE_WIDTH_MM"):
        if has(nm) and v[nm] < 0.1:
            rep.warn(f"{nm} = {v[nm]:g} mm is very fine (typical fabs start around 0.1 mm); "
                     f"check your manufacturer's limit")
    if has("MIN_CLEARANCE_MM") and v["MIN_CLEARANCE_MM"] < 0.1:
        rep.warn(f"MIN_CLEARANCE_MM = {v['MIN_CLEARANCE_MM']:g} mm is tighter than typical fab limits (about 0.1 mm)")
    if has("EXCITATION_FREQ_HZ") and not 1e5 <= v["EXCITATION_FREQ_HZ"] <= 5e7:
        rep.warn(f"EXCITATION_FREQ_HZ = {v['EXCITATION_FREQ_HZ']:g} Hz is far from the 1 ... 10 MHz that inductive "
                 f"position sensors run at (the value is in hertz: 3.5e6 = 3.5 MHz)")
    if has("COPPER_THICKNESS_UM") and not 9.0 <= v["COPPER_THICKNESS_UM"] <= 210.0:
        rep.warn(f"COPPER_THICKNESS_UM = {v['COPPER_THICKNESS_UM']:g} um is far outside the usual 18 ... 105 um "
                 f"(the value is in micrometres: 35 = 1 oz copper)")
    if v.get("RX_TABS") in ("all", "single") and has("RX_TAB_WIDTH_MM") and v["RX_TAB_WIDTH_MM"] < 0.6:
        rep.warn(f"RX_TAB_WIDTH_MM = {v['RX_TAB_WIDTH_MM']:g}: narrower than about 0.6 mm is hard to etch")
    if has("STATOR_FILE", "ROTOR_FILE"):
        for nm in ("STATOR_FILE", "ROTOR_FILE"):
            if not v[nm].lower().endswith(".kicad_pcb"):
                rep.warn(f"{nm} = {v[nm]!r} does not end in .kicad_pcb; KiCad will not offer to open it")
    if has("OUTPUT_DIR"):
        from Generator.Run import OutputFolders
        d = OutputFolders.output_dir(types.SimpleNamespace(OUTPUT_DIR=v["OUTPUT_DIR"]))
        if os.path.islink(d) and not os.path.exists(d):
            rep.error(f"OUTPUT_DIR {d!r} is a link to something that does not exist")
        elif os.path.exists(d) and not os.path.isdir(d):
            rep.error(f"OUTPUT_DIR {d!r} exists but is not a folder")
        elif os.path.isdir(d) and not os.access(d, os.W_OK):
            rep.error(f"OUTPUT_DIR {d!r} is not writable")
        elif not os.path.exists(d):
            # it is created in step 6: the nearest folder above it that exists must be a writable folder
            up = os.path.dirname(os.path.abspath(d))
            while up and not os.path.lexists(up) and os.path.dirname(up) != up:
                up = os.path.dirname(up)
            if not os.path.isdir(up):
                rep.error(f"OUTPUT_DIR {d!r} cannot be created: {up!r} is not a folder")
            elif not os.access(up, os.W_OK):
                rep.error(f"OUTPUT_DIR {d!r} cannot be created: {up!r} is not writable")
            else:
                rep.info(f"OUTPUT_DIR {d!r} does not exist yet and will be created (the Coil_... folder goes inside "
                         f"it)")
    e_mask = v.get("ROTOR_SOLDER_MASK_EXPANSION_MM")             # -1 = no mask opening
    if e_mask is not None and e_mask > 0.25:
        rep.warn(f"ROTOR_SOLDER_MASK_EXPANSION_MM = {e_mask:g}: the mask opening is that much wider than the "
                 f"copper on every side, which leaves a wide ring of bare laminate around each sector. Typical "
                 f"values are 0 ... 0.1 mm")
