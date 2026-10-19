"""
Dual_SetParameters.py  -  the parameter set of ONE coil set, in the Single Generator's own names.

The dual parameter files hold two sets of RX, TX and rotor values and one board.  The Single Generator's builders
and checks take one namespace with its own names (LOOPS, TX_TURNS, INNER_EDGE_RADIUS_MM, ...), so for each set the
dual generator puts together exactly that:

    board names        from Dual_Board_Parameters.py (the same for both sets)
    RX, TX, rotor, IC  from Dual_RX<k>, Dual_TX<k>, Dual_Rotor<k>, Dual_IC<k>
    the band, the edges   as Dual_TrackLayout decided them (the mode)
    what a dual board fixes   from Dual_Fixed_Parameters.py: 4 layers, no fingers, stepped TX, no TX tail, and
                              (ring 1 only) never over TX1.  FIXED_REQUIRED below says the value each name must
                              have and why; the dual checker refuses any other value in that file.

NAMES_BY_FILE says which Single Generator name lives in which dual file; the dual checker uses it to spot a name
in the wrong file.  Nothing to edit here.
"""

import types

from Generator.Checks import ParameterRules as SingleRules          # read only: the Single Generator's table

# what a dual board fixes: name -> (the only allowed value, why), all in Dual_Fixed_Parameters.py
FIXED_FILE = "Dual_Fixed_Parameters.py"
FIXED_REQUIRED = {
    "PCB_LAYERS": (4, "a dual board is a 4-layer board"),
    "RX_RISING_EDGE_LAYER": ("F.Cu", "a 2-layer setting, unused with 4 layers"),
    "RX_TABS": ("none", "no bridging fingers: set 1's fingers would cross set 2's band"),
    "RX_TAB_LAYER": ("auto", "fingers only, unused"),
    "RX_TAB_LENGTH_MM": (0.0, "fingers only, unused"),
    "RX_TAB_WIDTH_MM": (1.0, "fingers only, unused"),
    "TX_SHAPE": ("stepped_diagonal", "stepped TX turns only"),
    "TX_TAIL_EXTRA_MM": (0.0, "no extra TX tail: the ring ends one pitch outside the last turn"),
    "TX_SERIES_UNDERPASS_LAYER": ("auto", "series with fingers only, unused"),
    "TX_PARALLEL_BREAK_STYLE": ("stitched", "parallel with fingers only, unused"),
    "TX_STEPPED_ARC_RADIUS_MM": ("auto", "stepped_arc only, which a dual board cannot use"),
}
RING_1_FIXED_REQUIRED = {
    "ROTOR_AUTO_COVER_TX": (False, "ring 1 never covers TX1: that metal would sit next to the RX2 band"),
    "ROTOR_AUTO_TX_OVERHANG_MM": (0.5, "cover only, unused for ring 1"),
}
FIXED_NAMES = tuple(FIXED_REQUIRED) + tuple(RING_1_FIXED_REQUIRED)


def _fixed_values(P, table):
    """{name: value} from Dual_Fixed_Parameters.py; a name missing there gets the required value (the checker
    reports the gap)."""
    mod = getattr(P, "FIXED", None)
    return {n: (getattr(mod, n) if mod is not None and hasattr(mod, n) else req) for n, (req, _why) in table.items()}


def fixed_values(P):
    """The fixed values for both sets, as the file has them."""
    return _fixed_values(P, FIXED_REQUIRED)


def ring_1_fixed_values(P):
    """The fixed values for ring 1 of the rotor, as the file has them."""
    return _fixed_values(P, RING_1_FIXED_REQUIRED)

# the Single Generator's names, by the dual file that holds them
BOARD_SHARED = (
    "OUTPUT_DIR", "STATOR_FILE", "ROTOR_FILE", "GENERATOR_MODE", "CENTER_X_MM", "CENTER_Y_MM", "PAGE_SIZE_MM",
    "VIA_DIAMETER_MM", "VIA_DRILL_MM", "MIN_CLEARANCE_MM",
    "INNER_EDGE_INSET_MM", "INNER_EDGE_RADIUS_MM", "OUTER_EDGE_OFFSET_MM", "OUTER_EDGE_RADIUS_MM",
    "OUTER_EDGE_TAIL_MARGIN_MM", "EDGE_LINE_WIDTH_MM", "AIR_GAP_MM", "PCB_THICKNESS_MM", "COPPER_THICKNESS_UM",
    "COPPER_CONDUCTIVITY_S_M", "TX_AC_RESISTANCE_FACTOR", "STACKUP_PREPREG_MM", "TANK_CAP_SERIES",
    "ROTOR_MODE", "ROTOR_AUTO_EDGE_CLEARANCE_MM", "ROTOR_CUSTOM_OUTLINE_RADIUS_MM", "ROTOR_CUSTOM_BORE_RADIUS_MM",
    "ROTOR_PCB_THICKNESS_MM", "ROTOR_ARC_STEPS_PER_SECTOR", "ROTOR_CHORD_TOLERANCE_MM",
    "ROTOR_SOLDER_MASK_EXPANSION_MM",
)
BOARD_DUAL = ("TRACK_GAP_MM", "BAND_SPLIT", "TERMINAL_1_DEG", "TERMINAL_2_DEG", "TX_FREQ_SEPARATION_MIN",
              "ROTOR_TRACK_GAP_MM", "ROTOR_1_TO_RX2_MM", "ROTOR_2_TO_RX1_MM")
RX_NAMES = (
    "LOOPS", "INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM", "RX_R_BASE_MM", "RX_A_MM", "RX_TRACE_WIDTH_MM",
    "RX_NET_PHASE_0_2", "RX_NET_PHASE_1_3", "RX_PROFILE", "STEPS_PER_LOOP", "RX_CHORD_TOLERANCE_MM",
    "RX_SUBCOILS", "RX_SUBCOIL_SPLIT_ELEC_DEG", "RX_LAYER_A", "RX_LAYER_B", "RX_VIA_ELECTRICAL_DEG",
)
TX_NAMES = (
    "EXCITATION_FREQ_HZ", "TX_NET", "TX_WIRING", "TX_TURNS", "TX_OFFSET_MM", "TX_PITCH_MM",
    "TX_TRACE_WIDTH_MM", "TX_STEPS", "TX_CHORD_TOLERANCE_MM", "TX_STEPPED_ANGLE_DEG", "TX_INSIDE_VIA_DISTANCE_MM",
    "TX_LAYER_A", "TX_LAYER_B",
)
IC_NAMES = ("IC_NAME", "IC_OSC_MIN_MHZ", "IC_OSC_MAX_MHZ", "IC_MIN_RP_OHM", "IC_SPLIT_TANK_CAPS")
ROTOR_NAMES = (
    "ROTOR_AUTO_DUTY", "ROTOR_AUTO_START_ANGLE_DEG", "ROTOR_AUTO_EXTENSION_MM", "ROTOR_AUTO_EXTENSION_INNER_MM",
    "ROTOR_AUTO_EXTENSION_OUTER_MM", "ROTOR_AUTO_TX_CLEARANCE_MM", "ROTOR_AUTO_COPPER_LAYERS",
    "ROTOR_CUSTOM_SECTORS", "ROTOR_CUSTOM_DUTY", "ROTOR_CUSTOM_START_ANGLE_DEG", "ROTOR_CUSTOM_INNER_RADIUS_MM",
    "ROTOR_CUSTOM_OUTER_RADIUS_MM", "ROTOR_CUSTOM_COPPER_LAYERS",
)
ROTOR_2_NAMES = ("ROTOR_AUTO_COVER_TX", "ROTOR_AUTO_TX_OVERHANG_MM")

BAND_NAMES = ("INSIDE_RADIUS_MM", "OUTSIDE_RADIUS_MM", "RX_R_BASE_MM", "RX_A_MM")
EDGE_NAMES = ("INNER_EDGE_RADIUS_MM", "OUTER_EDGE_RADIUS_MM")

NAMES_BY_FILE = {
    "Dual_Board_Parameters.py": BOARD_SHARED + BOARD_DUAL,
    "Dual_RX1_Parameters.py": RX_NAMES,
    "Dual_RX2_Parameters.py": RX_NAMES,
    "Dual_TX1_Parameters.py": TX_NAMES,
    "Dual_TX2_Parameters.py": TX_NAMES,
    "Dual_Rotor1_Parameters.py": ROTOR_NAMES,
    "Dual_Rotor2_Parameters.py": ROTOR_NAMES + ROTOR_2_NAMES,
    "Dual_IC1_Parameters.py": IC_NAMES,
    "Dual_IC2_Parameters.py": IC_NAMES,
    FIXED_FILE: FIXED_NAMES,
}
PARAMETER_FILES = tuple(NAMES_BY_FILE)

# the Single Generator's file names in its messages -> the dual file of set k
SINGLE_FILE_WORDS = {1: {"Board_Parameters.py": "Dual_Board_Parameters.py", "RX_Parameters.py": "Dual_RX1_Parameters.py",
                         "TX_Parameters.py": "Dual_TX1_Parameters.py", "Rotor_Parameters.py": "Dual_Rotor1_Parameters.py",
                         "IC_Parameters.py": "Dual_IC1_Parameters.py"},
                     2: {"Board_Parameters.py": "Dual_Board_Parameters.py", "RX_Parameters.py": "Dual_RX2_Parameters.py",
                         "TX_Parameters.py": "Dual_TX2_Parameters.py", "Rotor_Parameters.py": "Dual_Rotor2_Parameters.py",
                         "IC_Parameters.py": "Dual_IC2_Parameters.py"}}


def modules(P, k):
    """(RX, TX, ROTOR) parameter modules of set k (1 or 2)."""
    if k == 1:
        return P.RX1, P.TX1, P.ROTOR1
    if k == 2:
        return P.RX2, P.TX2, P.ROTOR2
    raise ValueError("a set is 1 (inner) or 2 (outer)")


def ic_module(P, k):
    """The IC parameter module of set k (Dual_IC<k>_Parameters.py), or None when it could not be loaded."""
    if k not in (1, 2):
        raise ValueError("a set is 1 (inner) or 2 (outer)")
    return getattr(P, f"IC{k}", None)


def supplied_names():
    """Every Single Generator name the dual generator supplies to a set (from a file or fixed)."""
    out = set(FIXED_NAMES) | set(BOARD_SHARED) | set(RX_NAMES) | set(TX_NAMES) | set(ROTOR_NAMES) \
        | set(ROTOR_2_NAMES) | set(IC_NAMES)
    return out


def names_the_single_wants_but_the_dual_lacks():
    """Names of the Single Generator's rule table that no dual file and no fixed value supplies: they appear when
    the Single Generator gains a parameter.  The dual checker reports them."""
    return sorted(SingleRules.KNOWN_NAMES - supplied_names())


def build(P, k, band=None, edges=None):
    """The namespace of set k for the Single Generator's builders and checks.
      band   : {single name: value} for the RX band, as Dual_TrackLayout decided it (the four band names not in
               it are set to None); None = the set's file values as they are
      edges  : (bore, outline) for INNER_EDGE_RADIUS_MM / OUTER_EDGE_RADIUS_MM; None = the board file's values
    A name missing from a dual file is left out, so that the Single Generator's checker reports it."""
    rx, tx, ro = modules(P, k)
    d = {}
    for n in BOARD_SHARED:
        if hasattr(P.BOARD, n):
            d[n] = getattr(P.BOARD, n)
    for src, names in ((rx, RX_NAMES), (tx, TX_NAMES), (ro, ROTOR_NAMES + (ROTOR_2_NAMES if k == 2 else ())),
                       (ic_module(P, k), IC_NAMES)):
        for n in names:
            if src is not None and hasattr(src, n):
                d[n] = getattr(src, n)
    if k == 1:
        d.update(ring_1_fixed_values(P))
    d.update(fixed_values(P))
    if band is not None:
        for n in BAND_NAMES:
            d[n] = None
        d.update(band)
    if edges is not None:
        d["INNER_EDGE_RADIUS_MM"], d["OUTER_EDGE_RADIUS_MM"] = edges
    return types.SimpleNamespace(**d)


def rename_single_files(text, k):
    """A Single Generator message with its file names replaced by the dual files of set k."""
    for old, new in SINGLE_FILE_WORDS[k].items():
        text = text.replace(old, new)
    return text
