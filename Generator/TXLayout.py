"""
TXLayout.py  -  how the TX coil is laid out on the copper layers (shared by StatorGenerator.py and
ParameterChecker.py; not a tool of its own and nothing to edit here).

It reads the TX layer settings of TX_Parameters.py:

    TX_LAYERS = 1                      the turns on TX_LAYER_A
    TX_LAYERS = 2, TX_SERIES = True    TX_LAYER_A and TX_LAYER_B in series (the series block:
                                       TX_SERIES_UNDERPASS_LAYER, also used with TX_LAYERS = 1)
    TX_LAYERS = 2, TX_SERIES = False   the same turns on TX_LAYER_A and TX_LAYER_B in parallel (the
                                       parallel block: TX_PARALLEL_BREAK_STYLE)

Parameter files of earlier versions (no TX_SERIES) still work as they did: there TX_LAYERS = 1 meant
the Bottom layer (or TX_PLACEMENT / TX_SECOND_LAYER / TX_BREAK_STYLE), TX_LAYERS = 2 a series TX.

"Go-around" (the staggered style, Hoxha et al., Sensors 2022, 22, 4683, Fig. 2): where an RX finger
crosses the TX on the TX's own layer, every turn ends a little before the finger, the outer turns
farther away than the inner ones (a staircase), and runs straight out, parallel to the finger, to a
via just outside the TX ring.  On the underpass layer a bracket - the innermost turn on the innermost
one - carries the turn around the outer end of the finger to the matching via on the other side.  The
finger runs out past the outermost bracket.
"""

LAYER_NAMES = {1: "F.Cu", 2: "In1.Cu", 3: "In2.Cu", 4: "B.Cu"}
LAYER_ORDER = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
SHARED_NAMES = ("TX_LAYERS", "TX_LAYER_A", "TX_LAYER_B")
LEGACY_NAMES = ("TX_PLACEMENT", "TX_SECOND_LAYER", "TX_BREAK_STYLE")         # only without TX_SERIES
NEW_NAMES = ("TX_SERIES", "TX_SERIES_UNDERPASS_LAYER", "TX_PARALLEL_BREAK_STYLE")


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
    if hasattr(P, "TX_SERIES"):
        series = P.TX_SERIES
        if not isinstance(series, bool):
            raise ValueError(f"TX_SERIES must be True (series TX) or False (parallel TX); it is {series!r}")
        n = getattr(P, "TX_LAYERS", 1)
        if isinstance(n, bool) or n not in (1, 2):
            raise ValueError(f"TX_LAYERS must be 1 or 2; it is {n!r}")
        a = _layer_number(P, "TX_LAYER_A", getattr(P, "TX_LAYER_A", 4), auto=False)
        layers = [a]
        if n == 2:
            b = _layer_number(P, "TX_LAYER_B", getattr(P, "TX_LAYER_B", 1), auto=False)
            if a == b:
                raise ValueError("TX_LAYER_A and TX_LAYER_B must be different layers")
            layers.append(b)
        if series or n == 1:
            under = _layer_number(P, "TX_SERIES_UNDERPASS_LAYER", getattr(P, "TX_SERIES_UNDERPASS_LAYER", "auto"))
            return True, layers, under, "staggered"
        style = str(getattr(P, "TX_PARALLEL_BREAK_STYLE", "stitched")).strip().lower()
        if style == "auto":
            style = "stitched"
        if style not in ("stitched", "staggered"):
            raise ValueError(f'TX_PARALLEL_BREAK_STYLE must be "stitched" or "staggered"; it is '
                             f'{getattr(P, "TX_PARALLEL_BREAK_STYLE")!r}')
        return False, layers, None, style
    # ---- parameter files without TX_SERIES (earlier versions)
    n = getattr(P, "TX_LAYERS", 1)
    if isinstance(n, bool) or n not in (1, 2):
        raise ValueError("TX_LAYERS must be 1 or 2")
    placement = str(getattr(P, "TX_PLACEMENT", "bottom")).strip().lower()
    if placement not in ("bottom", "top", "both"):
        raise ValueError('TX_PLACEMENT must be "bottom", "top" or "both"')
    style = str(getattr(P, "TX_BREAK_STYLE", "auto")).strip().lower()
    if style not in ("auto", "staggered", "stitched"):
        raise ValueError('TX_BREAK_STYLE must be "auto", "staggered" or "stitched"')
    if n == 2:
        if placement != "bottom":
            raise ValueError(f'TX_PLACEMENT = "{placement}" needs TX_LAYERS = 1 (TX_LAYERS = 2 is the series '
                             f"two-layer TX of TX_LAYER_A / TX_LAYER_B)")
        a = _layer_number(P, "TX_LAYER_A", getattr(P, "TX_LAYER_A", 1), auto=False)
        b = _layer_number(P, "TX_LAYER_B", getattr(P, "TX_LAYER_B", 3), auto=False)
        if a == b:
            raise ValueError("TX_LAYER_A and TX_LAYER_B must be different layers")
        return True, [a, b], None, "staggered"
    second = _layer_number(P, "TX_SECOND_LAYER", getattr(P, "TX_SECOND_LAYER", "auto"))
    if placement == "both":
        if second is None:
            second = 4 if int(P.PCB_LAYERS) == 2 else 2
        if second == 1:
            raise ValueError("TX_SECOND_LAYER must be another layer than the TX layer (F.Cu)")
        return False, [1, second], None, ("staggered" if style == "staggered" else "stitched")
    if style == "stitched":
        raise ValueError('TX_BREAK_STYLE = "stitched" needs the TX on two layers in parallel (TX_PLACEMENT = "both")')
    base = 1 if placement == "top" else 4
    if second == base:
        raise ValueError(f"TX_SECOND_LAYER must be another layer than the TX layer ({LAYER_NAMES[base]})")
    return True, [base], second, "staggered"


def _rx_layer_names(P):
    if int(P.PCB_LAYERS) == 2:
        rising = P.RX_RISING_EDGE_LAYER
        return rising, ("B.Cu" if rising == "F.Cu" else "F.Cu")
    return LAYER_NAMES[P.RX_LAYER_A], LAYER_NAMES[P.RX_LAYER_B]


def _auto_underpass(P, base):
    """The automatic layer of the inner tail and the go-around brackets of a TX on one layer."""
    if base == "B.Cu":
        return "F.Cu"                                  # (the original layout: TX on Bottom, tail on Top)
    if base == "F.Cu":
        return "B.Cu" if int(P.PCB_LAYERS) == 2 else "In1.Cu"
    return "F.Cu" if base == "In1.Cu" else "B.Cu"


def tx_layout(P):
    """Everything the generator needs to know about the TX layers, as a dict:
      series, mode ("single" | "series2" | "parallel"), layers (names, in the order given),
      turn_layers (set), field_layers [(layer, share of the current)], tab_layer (the RX fingers),
      windows_on (a finger crosses the TX on a TX layer), style (finger windows: "staggered" = go-around,
      "stitched"; None without windows), goaround, bracket_layer (go-around brackets), tail_layer (inner tail of a
      one-layer TX; parallel: the layer of the stitched arcs), arc_layer / base_layer (parallel),
      new_builder (False = one of the original builders, kept byte for byte), legacy (no TX_SERIES in the file).
    Raises ValueError for settings that cannot be built."""
    series, nums, under, style_set = tx_settings(P)
    names = [LAYER_NAMES[x] for x in nums]
    rising, falling = _rx_layer_names(P)
    tabs_on = str(P.RX_TABS).lower() in ("all", "single")
    turn_layers = set(names)
    if series and len(names) == 1:
        mode = "single"
        field = [(names[0], 1.0)]
    elif series:
        mode = "series2"
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
               windows_on=windows_on, style=style, goaround=goaround, legacy=not hasattr(P, "TX_SERIES"),
               bracket_layer=None, tail_layer=None, arc_layer=None, base_layer=None, underpass_set=under)
    if mode == "single":
        base = names[0]
        ul = LAYER_NAMES[under] if under is not None else _auto_underpass(P, base)
        if ul == base:
            raise ValueError(f"TX_SERIES_UNDERPASS_LAYER must be another layer than the TX layer ({base}, TX_LAYER_A)")
        out.update(base_layer=base, tail_layer=ul, bracket_layer=ul,
                   new_builder=not (base == "B.Cu" and ul == "F.Cu" and not windows_on))
    elif mode == "series2":
        if under is not None:
            ul = LAYER_NAMES[under]
        else:
            ul = names[1] if tab == names[0] else names[0]
        if windows_on and ul == tab:
            raise ValueError(f"TX_SERIES_UNDERPASS_LAYER = {under}: the go-around brackets must be on another layer "
                             f"than the fingers ({tab})")
        out.update(bracket_layer=ul if windows_on else None, new_builder=windows_on)
    else:
        arc = tab if tab in turn_layers else names[0]
        base = names[1] if arc == names[0] else names[0]
        out.update(arc_layer=arc, base_layer=base, tail_layer=arc, bracket_layer=base, new_builder=True)
    return out


def goaround_dims(P):
    """Sizes of a go-around window (mm), relative to the RX outside radius where they are radii:
      g[n]      : distance of turn n's run-out (and via) from the centre line of the finger leg (n = 0 innermost)
      via_off   : radius of the via circle, minus the RX outside radius
      bracket_off[n] : radius of bracket n, minus the RX outside radius (bracket 0 runs at the via circle)
      reach     : how far the window reaches beyond the finger leg (with half a clearance)
      tip_off   : the radius the finger tips must reach, minus the RX outside radius."""
    T = int(P.TX_TURNS)
    pitch, tw, rw = float(P.TX_PITCH_MM), float(P.TX_TRACE_WIDTH_MM), float(P.RX_TRACE_WIDTH_MM)
    vr, clr = float(P.VIA_DIAMETER_MM) / 2.0, float(P.MIN_CLEARANCE_MM)
    spiral = str(P.TX_TURN_SHAPE).lower() == "spiral"
    r_out = float(P.TX_OFFSET_MM) + (T if spiral else T - 1) * pitch     # outermost TX copper (centre line)
    via_off = r_out + tw / 2.0 + clr + vr + 0.02
    first = vr + tw / 2.0 + clr + 0.02                 # bracket 1 must pass over the vias of bracket 0
    s = max(pitch, tw + clr + 0.02)
    bracket_off = [via_off] + [via_off + first + (n - 1) * s for n in range(1, T)]
    g0 = rw / 2.0 + max(vr, tw / 2.0) + clr + 0.05
    dg = max(2.0 * vr + clr, tw + clr) + 0.02
    g = [g0 + n * dg for n in range(T)]
    reach = g[-1] + vr + clr / 2.0 + 0.02
    tip_off = bracket_off[-1] + tw / 2.0 + rw / 2.0 + clr + 0.2
    return dict(T=T, g=g, dg=dg, g0=g0, via_off=via_off, bracket_off=bracket_off, reach=reach, tip_off=tip_off,
                vr=vr, tw=tw, clr=clr, s=s)


def outer_edge_room(P):
    """Distance from the RX outside radius to the outer board edge that the automatic edge rule gives (mm).
    Every term of that rule is the RX outside radius plus a constant, so this does not depend on the radius:
        the larger of  OUTER_EDGE_OFFSET_MM,
                       the TX tail end + OUTER_EDGE_TAIL_MARGIN_MM,
                       the end of the RX bridging fingers + half a trace + OUTER_EDGE_TAIL_MARGIN_MM (RX_TABS = "all"
                       or "single"; with go-around windows the fingers reach past the outermost bracket)."""
    margin = float(P.OUTER_EDGE_TAIL_MARGIN_MM)
    room = max(float(P.OUTER_EDGE_OFFSET_MM),
               P.TX_OFFSET_MM + P.TX_TURNS * P.TX_PITCH_MM + P.TX_TAIL_EXTRA_MM + margin)
    if str(P.RX_TABS).lower() in ("all", "single"):
        tab = max(P.RX_TAB_LENGTH_MM,
                  P.TX_OFFSET_MM + (P.TX_TURNS - 1) * P.TX_PITCH_MM + P.TX_TRACE_WIDTH_MM / 2.0
                  + P.RX_TRACE_WIDTH_MM / 2.0 + P.MIN_CLEARANCE_MM + 0.2)
        try:
            go = tx_layout(P)["goaround"]
        except (ValueError, TypeError, AttributeError, KeyError):
            go = False                                 # (reported by the layer checks)
        if go:
            tab = max(tab, goaround_dims(P)["tip_off"])
        room = max(room, tab + P.RX_TRACE_WIDTH_MM / 2.0 + margin)
    return float(room)
