"""
Layers.py  -  the copper layers: their KiCad names, their depth in the board, and which layer carries what
(the RX coils, the RX fingers, the TX turns, the TX underpass).  Used by the RX and TX builders, the stator
assembly, the rotor and the checks, so all of them agree.  Nothing to edit here.

It reads the layer settings of the parameter files:

    PCB_LAYERS, RX_RISING_EDGE_LAYER (2-layer boards), RX_LAYER_A / RX_LAYER_B (4-layer boards)
    RX_TABS, RX_TAB_LAYER                                 the RX fingers
    TX_WIRING = "single"      the turns on TX_LAYER_A (the series block: TX_SERIES_UNDERPASS_LAYER)
    TX_WIRING = "series"      TX_LAYER_A and TX_LAYER_B in series (the series block)
    TX_WIRING = "parallel"    the same turns on TX_LAYER_A and TX_LAYER_B in parallel (the parallel block:
                              TX_PARALLEL_BREAK_STYLE)
"""

from Generator.Core.Conflict import ParameterConflict

LAYER_NAMES = {1: "F.Cu", 2: "In1.Cu", 3: "In2.Cu", 4: "B.Cu"}
LAYER_ORDER = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
LAYER_WORDS = {"F.Cu": "Top", "In1.Cu": "Inner-1", "In2.Cu": "Inner-2", "B.Cu": "Bottom"}   # in human text
LAYER_SETTINGS = ("TX_WIRING", "TX_LAYER_A", "TX_LAYER_B", "TX_SERIES_UNDERPASS_LAYER", "TX_PARALLEL_BREAK_STYLE")
TX_WIRING_VALUES = ("single", "series", "parallel")
STACKUP_PREPREG_MM = 0.2       # 4-layer boards: distance from an outer copper layer to its inner neighbour (mm)


def layer_depth(layer, P, prepreg=STACKUP_PREPREG_MM):
    """Distance of a copper layer below the top copper (mm): 0 for Top, the board thickness for Bottom, the prepreg
    for the inner layers (a third of the thickness on a very thin board)."""
    t = float(P.PCB_THICKNESS_MM)
    if layer == "F.Cu":
        return 0.0
    if layer == "B.Cu":
        return t
    inner = prepreg if 2.0 * prepreg < t else t / 3.0
    return inner if layer == "In1.Cu" else t - inner


def tx_wiring(P):
    """'single', 'series' or 'parallel' for TX_WIRING (any letter case).  Raises ValueError for anything else."""
    w = str(getattr(P, "TX_WIRING", "single")).strip().lower()
    if w not in TX_WIRING_VALUES:
        raise ValueError('TX_WIRING must be "single", "series" or "parallel"')
    return w


def _is_auto(v):
    return isinstance(v, str) and v.strip().lower() == "auto"


def _board_layers(P):
    return (1, 4) if int(P.PCB_LAYERS) == 2 else (1, 2, 3, 4)


def _layer_number(P, name, v, auto=True):
    """A layer setting -> its number (1 Top ... 4 Bottom), None for "auto"."""
    if auto and _is_auto(v):
        return None
    ok = _board_layers(P)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v not in ok:
        raise ValueError(f'{name} must be {chr(34) + "auto" + chr(34) + " or " if auto else ""}one of '
                         f'{", ".join(str(x) for x in ok)} (1 = Top, 2 = Inner 1, 3 = Inner 2, 4 = Bottom; a '
                         f'{int(P.PCB_LAYERS)}-layer board); it is {v!r}')
    return int(v)


def tx_settings(P):
    """(series, [layer numbers], underpass setting (number or None = auto), finger break style).
    The style is "staggered" (go-around) for a series TX; "stitched" or "staggered" for a parallel one."""
    wiring = tx_wiring(P)
    series, n = wiring != "parallel", 1 if wiring == "single" else 2
    a = _layer_number(P, "TX_LAYER_A", P.TX_LAYER_A, auto=False)
    layers = [a]
    if n == 2:
        b = _layer_number(P, "TX_LAYER_B", P.TX_LAYER_B, auto=False)
        if a == b:
            raise ParameterConflict(("TX_LAYER_A", "TX_LAYER_B"), f"the two TX layers must be different layers; both are "
                                    f"{LAYER_NAMES[a]} ({a})")
        layers.append(b)
    if series or n == 1:
        under = _layer_number(P, "TX_SERIES_UNDERPASS_LAYER", getattr(P, "TX_SERIES_UNDERPASS_LAYER", "auto"))
        return True, layers, under, "staggered"
    style = str(getattr(P, "TX_PARALLEL_BREAK_STYLE", "stitched")).strip().lower()
    if style not in ("stitched", "staggered"):
        raise ValueError(f'TX_PARALLEL_BREAK_STYLE must be "stitched" or "staggered"; it is '
                         f'{getattr(P, "TX_PARALLEL_BREAK_STYLE")!r}')
    return False, layers, None, style


def rx_layer_names(P):
    """(layer of the rising edges, layer of the falling edges) of the RX coils."""
    if int(P.PCB_LAYERS) == 2:
        rising = P.RX_RISING_EDGE_LAYER
        return rising, ("B.Cu" if rising == "F.Cu" else "F.Cu")
    return LAYER_NAMES[P.RX_LAYER_A], LAYER_NAMES[P.RX_LAYER_B]


def _auto_underpass(P, base):
    """The automatic layer of the inner tail and the go-around brackets of a TX on one layer."""
    if base == "B.Cu":
        return "F.Cu"                                  # (the default layout: TX on Bottom, tail on Top)
    if base == "F.Cu":
        return "B.Cu" if int(P.PCB_LAYERS) == 2 else "In1.Cu"
    return "F.Cu" if base == "In1.Cu" else "B.Cu"


def layer_plan(P):
    """Everything the generator needs to know about the TX layers, as a dict:
      series, mode ("single" | "series" | "parallel", = TX_WIRING), layers (names, in the order given),
      turn_layers (set), field_layers [(layer, share of the current)], tab_layer (the RX fingers),
      windows_on (a finger crosses the TX on a TX layer), style (finger windows: "staggered" = go-around,
      "stitched"; None without windows), goaround, bracket_layer (go-around brackets), tail_layer (inner tail of a
      one-layer TX; parallel: the layer of the stitched arcs), arc_layer / base_layer (parallel).
    Raises ValueError for settings that cannot be built."""
    series, nums, under, style_set = tx_settings(P)
    names = [LAYER_NAMES[x] for x in nums]
    rising, falling = rx_layer_names(P)
    tabs_on = str(P.RX_TABS).lower() in ("all", "single")
    turn_layers = set(names)
    if series and len(names) == 1:
        mode = "single"
        field = [(names[0], 1.0)]
    elif series:
        mode = "series"
        field = [(names[0], 1.0), (names[1], 1.0)]
    else:
        mode = "parallel"
        field = [(names[0], 0.5), (names[1], 0.5)]
    # the fingers: RX_TAB_LAYER, or "auto" = the RX layer nearest the top that carries no TX turn; when both RX layers
    # carry TX turns, the RX layer nearest the top (the TX then makes way for every finger)
    chosen = _layer_number(P, "RX_TAB_LAYER", getattr(P, "RX_TAB_LAYER", "auto"))
    if chosen is not None:
        tab = LAYER_NAMES[chosen]
    else:
        cand = [l for l in (rising, falling) if l not in turn_layers]
        if cand:
            tab = min(cand, key=LAYER_ORDER.index)
        elif tabs_on:
            tab = min((rising, falling), key=LAYER_ORDER.index)
        else:
            tab = rising
    windows_on = tabs_on and tab in turn_layers
    style = style_set if windows_on else None
    goaround = windows_on and style == "staggered"
    out = dict(series=series, mode=mode, layers=names, turn_layers=turn_layers, field_layers=field, tab_layer=tab,
               windows_on=windows_on, style=style, goaround=goaround,
               bracket_layer=None, tail_layer=None, arc_layer=None, base_layer=None)
    if mode == "single":
        base = names[0]
        ul = LAYER_NAMES[under] if under is not None else _auto_underpass(P, base)
        if ul == base:
            raise ParameterConflict(("TX_SERIES_UNDERPASS_LAYER", "TX_LAYER_A"), f"the inner tail and the brackets must be "
                                    f"on another layer than the TX turns; both are {base}")
        out.update(base_layer=base, tail_layer=ul, bracket_layer=ul)
    elif mode == "series":
        if under is not None:
            ul = LAYER_NAMES[under]
        else:
            ul = names[1] if tab == names[0] else names[0]
        if windows_on and ul == tab:
            raise ParameterConflict(("TX_SERIES_UNDERPASS_LAYER", "RX_TAB_LAYER"), f"the go-around brackets must be on "
                                    f"another layer than the RX fingers; both are {tab}")
        out.update(bracket_layer=ul if windows_on else None)
    else:
        arc = tab if tab in turn_layers else names[0]
        base = names[1] if arc == names[0] else names[0]
        out.update(arc_layer=arc, base_layer=base, tail_layer=arc, bracket_layer=base)
    return out
