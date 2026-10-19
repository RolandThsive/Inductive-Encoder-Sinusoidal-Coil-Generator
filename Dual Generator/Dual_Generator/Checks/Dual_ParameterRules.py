"""
Dual_ParameterRules.py  -  the rules the Single Generator cannot know: which name belongs in which dual file, the
values that only a dual board has (the gap between the sets, the band split, the terminal angles, the gap between
the rotor rings, the frequency warning), and the rules between the two sets (distinct nets, frequencies apart,
a TX shape that needs a tail, a layer left free for set 1's leads).  Every rule about one set on its own is the
Single Generator's (ParameterRules.py, ConflictRules.py), run by Dual_CheckParameters.py on each set.
Nothing to edit here.
"""

import difflib
import math
import os

from Generator.Checks import ParameterRules as SingleRules

from Dual_Generator.Core import Dual_SetParameters as SP

BOARD_FILE = "Dual_Board_Parameters.py"

# the dual-only values: (name, kind, options) for ParameterRules._check_value
DUAL_SPEC = (
    ("TRACK_GAP_MM", "num_or_none", dict(lo=0, lo_ex=True)),
    ("BAND_SPLIT", "num", dict(lo=0, hi=1, lo_ex=True, hi_ex=True)),
    ("TERMINAL_1_DEG", "num", dict()),
    ("TERMINAL_2_DEG", "num", dict()),
    ("TX_FREQ_SEPARATION_MIN", "num", dict(lo=0, hi=1, hi_ex=True)),
    ("ROTOR_TRACK_GAP_MM", "num", dict(lo=0)),
    ("ROTOR_1_TO_RX2_MM", "num", dict(lo=0)),
    ("ROTOR_2_TO_RX1_MM", "num", dict(lo=0)),
)
_SINGLE_OPTIONAL = {name: opt for _file, name, _kind, opt, _active in SingleRules.SPEC if opt.get("optional")}
_FILE_ATTR = {"Dual_Board_Parameters.py": "BOARD", "Dual_RX1_Parameters.py": "RX1", "Dual_RX2_Parameters.py": "RX2",
              "Dual_TX1_Parameters.py": "TX1", "Dual_TX2_Parameters.py": "TX2",
              "Dual_Rotor1_Parameters.py": "ROTOR1", "Dual_Rotor2_Parameters.py": "ROTOR2",
              SP.FIXED_FILE: "FIXED"}


def _where(name):
    """The dual file(s) a Single Generator name belongs in, or None."""
    return [f for f, names in SP.NAMES_BY_FILE.items() if name in names]


def _same(a, b):
    """Two parameter values alike (strings without case or spaces, numbers as numbers, bools exactly)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().lower() == b.strip().lower()
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-12
    return a == b


def check_fixed(P, rep):
    """Every value in Dual_Fixed_Parameters.py is what a dual board fixes it at; anything else is an error that says
    why the value is fixed."""
    mod = getattr(P, "FIXED", None)
    if mod is None:
        return
    for table, who in ((SP.FIXED_REQUIRED, ""), (SP.RING_1_FIXED_REQUIRED, " for ring 1 of the rotor")):
        for name, (req, why) in table.items():
            if not hasattr(mod, name):
                continue                                   # check_files reports it as missing
            val = getattr(mod, name)
            if not _same(val, req):
                rep.error(f"{name} = {val!r} in {SP.FIXED_FILE} is FIXED at {req!r}{who} for every dual board ({why}). "
                          f"Put it back; a board with another value is a Single Generator board")


def check_files(P, rep):
    """Every dual file: the names it must have are there; a name it should not have is reported (a typo, a line
    that belongs in another file, or a setting a dual board fixes)."""
    all_known = set(SingleRules.KNOWN_NAMES) | {n for n, _k, _o in DUAL_SPEC}
    for file, attr in _FILE_ATTR.items():
        mod = getattr(P, attr, None)
        if mod is None:
            rep.error(f"{file} could not be loaded (Dual_Parameters.py imports it as {attr})")
            continue
        expected = SP.NAMES_BY_FILE[file]
        present = {n for n in dir(mod) if n.isupper() and not n.startswith("_")}
        for name in expected:
            if name in present:
                continue
            opt = _SINGLE_OPTIONAL.get(name)
            if opt is not None:
                default = opt.get("default")
                shown = ("None" if default is None else f"the default {default!r}"
                         if isinstance(default, (bool, str, list, tuple)) else f"the default {default:g}")
                rep.info(f"{name} is not in {file}: {'treated as ' if default is None else 'using '}{shown}")
            else:
                rep.error(f"{name} is missing - add it to {file}")
        for name in sorted(present - set(expected)):
            if name in SP.FIXED_REQUIRED:
                rep.warn(f"{name} in {file} is ignored: a dual board fixes it at {SP.FIXED_REQUIRED[name][0]!r} "
                         f"({SP.FIXED_FILE})")
            elif name in SP.RING_1_FIXED_REQUIRED and attr == "ROTOR1":
                rep.warn(f"{name} in {file} is ignored: ring 1 never covers its TX turns "
                         f"({name} = {SP.RING_1_FIXED_REQUIRED[name][0]!r} in {SP.FIXED_FILE})")
            elif _where(name):
                rep.warn(f"{name} in {file} is ignored: it belongs in {' / '.join(_where(name))}")
            else:
                close = difflib.get_close_matches(name, all_known, n=1, cutoff=0.7)
                hint = f" - did you mean {close[0]}?" if close else ""
                rep.warn(f"{name} in {file} is not a parameter of this program and is ignored{hint}")


def check_dual_values(P, rep):
    """The dual-only values, one at a time.  Returns {name: value} of the valid ones."""
    v = {}
    for name, kind, opt in DUAL_SPEC:
        if not hasattr(P.BOARD, name):
            rep.error(f"{name} is missing - add it to {BOARD_FILE}")
            continue
        val, err = SingleRules._check_value(name, getattr(P.BOARD, name), kind, opt)
        if err:
            rep.error(err + f"   ({BOARD_FILE})")
        else:
            v[name] = val
    return v


def dual_rules(P, v, rep):
    """The rules between the two sets and the dual-only rules."""
    B = P.BOARD
    # the wiring of each set: series or parallel (a single-layer TX is not a dual option)
    for k in (1, 2):
        tx = SP.modules(P, k)[1]
        w = getattr(tx, "TX_WIRING", None)
        if isinstance(w, str) and w.strip().lower() == "single":
            rep.conflict(("TX_WIRING",), f'TX_WIRING = "single" in Dual_TX{k}_Parameters.py: a dual board uses "series" '
                         f'or "parallel" (turns on both TX layers); a single-layer TX has no place on it')
    # the six nets must differ (KiCad merges equal names)
    nets = []
    for k in (1, 2):
        rx, tx, _ = SP.modules(P, k)
        for name, src, file in (("RX_NET_PHASE_0_2", rx, f"Dual_RX{k}_Parameters.py"),
                                ("RX_NET_PHASE_1_3", rx, f"Dual_RX{k}_Parameters.py"),
                                ("TX_NET", tx, f"Dual_TX{k}_Parameters.py")):
            val = getattr(src, name, None)
            if isinstance(val, str):
                nets.append((val, f"{name} ({file})"))
    seen = {}
    for val, where in nets:
        if val in seen:
            rep.error(f"the net name {val!r} is used twice: {seen[val]} and {where}. KiCad would join the two coils "
                      f"into one net; give every net of the two sets its own name")
        seen.setdefault(val, where)
    # the two excitation frequencies (see TX_FREQ_SEPARATION_MIN in Dual_Board_Parameters.py)
    f1, f2 = (getattr(SP.modules(P, k)[1], "EXCITATION_FREQ_HZ", None) for k in (1, 2))
    sep = v.get("TX_FREQ_SEPARATION_MIN")
    if all(isinstance(f, (int, float)) and not isinstance(f, bool) and f > 0 for f in (f1, f2)) and sep is not None:
        lo, hi = min(f1, f2), max(f1, f2)
        ratio = hi / lo
        names = ("EXCITATION_FREQ_HZ", "TX_FREQ_SEPARATION_MIN")
        if ratio - 1.0 < sep - 1e-12:
            rep.warn(f"the two TX frequencies differ by {100 * (ratio - 1):.1f} % (EXCITATION_FREQ_HZ {f1 / 1e6:g} MHz in "
                     f"Dual_TX1_Parameters.py, {f2 / 1e6:g} MHz in Dual_TX2_Parameters.py), less than "
                     f"TX_FREQ_SEPARATION_MIN ({100 * sep:g} %): each IC's demodulator passes the other carrier at "
                     f"|f2 - f1| = {(hi - lo) / 1e3:g} kHz, and the tank tolerances can close the rest. Move one "
                     f"frequency, or drive both tanks from one IC (the CN317 reference way) so that there is one carrier")
        else:
            best = min(((abs(ratio / (p / q) - 1.0), p, q) for p in range(1, 5) for q in range(1, 5) if p > q
                        and p / q > 1.0 and math.gcd(p, q) == 1), default=None)
            if best is not None and best[0] < 0.02:
                rep.warn(f"the two TX frequencies sit on the ratio {best[1]}:{best[2]} (EXCITATION_FREQ_HZ {lo / 1e6:g} and "
                         f"{hi / 1e6:g} MHz, ratio {ratio:.3f}): harmonic {best[2]} of the higher carrier lands on "
                         f"harmonic {best[1]} of the lower one, which a switching demodulator mixes down to DC. Move "
                         f"one frequency off every p:q with p, q <= 4 (for example 3.0 and 4.3 MHz)")
        if ratio - 1.0 >= sep - 1e-12:
            rep.info(f"the two TX frequencies, {lo / 1e6:g} and {hi / 1e6:g} MHz, differ by {100 * (ratio - 1):.0f} %. "
                     f"Published dual boards drive one tank only (the CN317 reference board: the second IC's TX current set to 0, "
                     f"its TX pins on the same tank); two free-running tanks have not been shown to work and must be "
                     f"proven on the first board: read each IC's AGC gain with the other TX on and off")
    # one layer free of set 2's copper, for set 1's leads to cross it by hand (radially, as tight pairs, at one
    # azimuth, on the layer farthest from the rotor: a lead running along an RX trace couples the TX in as offset)
    rx2, tx2, _ = SP.modules(P, 2)
    used = {getattr(rx2, "RX_LAYER_A", None), getattr(rx2, "RX_LAYER_B", None),
            getattr(tx2, "TX_LAYER_A", None), getattr(tx2, "TX_LAYER_B", None)}
    if used >= {1, 2, 3, 4}:
        rep.warn("set 2 uses all four layers (RX_LAYER_A / B in Dual_RX2_Parameters.py, TX_LAYER_A / B in "
                 "Dual_TX2_Parameters.py), so no layer is free for set 1's six leads to cross set 2 on their way "
                 "to its IC. The recommended layers leave Bottom (the layer farthest from the rotor) free: RX on "
                 "1 + 2, TX on 1 + 3")
    # the rotor ring gap against the extensions is checked on the built rotor (Dual_DesignChecks)
    # the output folder
    if hasattr(B, "OUTPUT_DIR") and isinstance(B.OUTPUT_DIR, str) and B.OUTPUT_DIR.strip():
        from Dual_Generator.Run import Dual_OutputFolders
        d = Dual_OutputFolders.output_dir(B)
        if os.path.exists(d) and not os.path.isdir(d):
            rep.error(f"OUTPUT_DIR {d!r} exists but is not a folder")
        elif os.path.isdir(d) and not os.access(d, os.W_OK):
            rep.error(f"OUTPUT_DIR {d!r} is not writable")
        elif not os.path.exists(d):
            rep.info(f"OUTPUT_DIR {d!r} does not exist yet and will be created (the DualCoil_... folder goes inside it)")
