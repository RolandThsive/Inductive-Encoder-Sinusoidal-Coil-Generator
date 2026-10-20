"""
TX_Parameters.py  -  transmitter (TX) coil: concentric turns outside the RX band.

Units: millimetres, degrees.  Nothing in this file is computed - edit values only.
Layers are numbered 1 = Top, 2 = Inner 1, 3 = Inner 2, 4 = Bottom (a 2-layer board has 1 and 4).
"""

TX_NET             = "TX"

TX_TURNS           = 3              # complete turns PER TX LAYER
TX_OFFSET_MM       = 1.1            # first turn radius = RX outside radius + this
TX_PITCH_MM        = 0.6            # radial pitch between turns
TX_TRACE_WIDTH_MM  = 0.2
# Points per TX turn (every turn is a polyline):
#   TX_STEPS = "auto" : as many as TX_CHORD_TOLERANCE_MM needs on the outermost turn (a multiple of 8, at least 48)
#   TX_STEPS = number : that many (12 ... 20000).
# TX_CHORD_TOLERANCE_MM = how far a straight chord of a TX turn may lie from the true circle: 0.001 mm = 1 micron,
#   also the smallest value allowed.
TX_STEPS           = "auto"
TX_CHORD_TOLERANCE_MM = 0.001
TX_TAIL_EXTRA_MM   = 2.0            # radial tail that carries the TX terminal
# TX_SHAPE = shape of the turns (any letter case):
#   "stepped_diagonal" : concentric circles joined by short straight steps just before the TX terminal, at
#                        TX_STEPPED_ANGLE_DEG.
#   "stepped_arc"      : concentric circles joined by arcs centred on the TX terminal via.  The via sits on
#                        the first turn; arc n (radius
#                        TX_STEPPED_ARC_RADIUS_MM + n x TX_PITCH_MM) leaves turn n on one side of the via, runs
#                        round it and lands on turn n + 1 on the other side, with sharp corners.  The arcs are one
#                        pitch apart, so the copper gap between them is the same as between the turns, and the
#                        outer tail leaves from the outermost point of the last arc.  TX_STEPPED_ANGLE_DEG and
#                        TX_INSIDE_VIA_DISTANCE_MM are not used.
#   "spiral"           : one smooth Archimedean spiral, the gap between turns equals the pitch
#                        everywhere.  Use it when TX_PITCH_MM is tight (pitch - trace width close
#                        to the clearance), e.g. a 0.4 mm pitch.  Its last turn
#                        ends one pitch farther out, and the fingers must reach past it (RX_TAB_LENGTH_MM
#                        at least 3.5 with the values in these files).
TX_SHAPE           = "stepped_diagonal"
# TX_STEPPED_ARC_RADIUS_MM = radius of the innermost arc of a "stepped_arc" TX (mm, measured from the centre of the
#   terminal via); the other arcs follow at TX_PITCH_MM.
#     "auto" : the smallest radius that keeps MIN_CLEARANCE_MM from the via (via radius + half a TX trace +
#              clearance) and is larger than TX_PITCH_MM (each arc must reach the next turn), plus 0.02 mm:
#              0.72 mm with the defaults.
#     number : that radius; it must be larger than TX_PITCH_MM and smaller than TX_PITCH_MM + TX_TAIL_EXTRA_MM.
#   Only used by "stepped_arc".
TX_STEPPED_ARC_RADIUS_MM = "auto"
# TX_STEPPED_ANGLE_DEG = the angle of the steps of a "stepped_diagonal" TX (where each turn steps out to the next one,
#   just before the TX terminal), measured from the turn: 90 = straight out (radial), 45 = diagonal, smaller =
#   a longer, gentler slope.  Each step is one straight piece, and the run down to the terminal via
#   (TX_INSIDE_VIA_DISTANCE_MM) takes the same angle.
#     5 ... 90 : the angle.  Neighbouring steps are parallel, so their copper gap is
#              TX_PITCH_MM * cos(angle) - TX_TRACE_WIDTH_MM; at steep angles (above about 45 deg with the
#              defaults) that is less than MIN_CLEARANCE_MM, and each step then starts a little before the one
#              inside it to keep the clearance.  The generator prints the gap it got.
#   Only used by "stepped_diagonal" (a "stepped_arc" TX has arcs, a "spiral" TX no steps).
TX_STEPPED_ANGLE_DEG = 45
# TX_INSIDE_VIA_DISTANCE_MM = where the via at the TX terminal sits (the via that joins the inner tail
#   to the first turn, or the two spirals of a series TX).  0 = on the trace ends - only one pitch from the
#   next turn, which with a 0.8 mm via and a 0.6 mm pitch is closer than MIN_CLEARANCE_MM.  A positive value moves it that far towards the centre (a negative one: away from
#   it); every turn that starts at the terminal then leaves its circle a little earlier and runs down to
#   the via at the slope of the TX's own steps (TX_STEPPED_ANGLE_DEG for "stepped_diagonal"; 45 deg for "spiral"),
#   with a short flat piece into the via.  Keep it below
#   TX_OFFSET_MM - via radius - half an RX trace - MIN_CLEARANCE_MM (0.4 mm with the defaults), or the
#   via comes too close to the RX coils.  The generator measures it and warns.
#   Not used by "stepped_arc" (its via always sits on the first turn, at the centre of the arcs).
TX_INSIDE_VIA_DISTANCE_MM = 0.3
# Where the TX terminal goes: there is no setting.  The TX looks for the place around the ring where its
# terminal (tail, via, steps or arcs, windows) keeps the largest gap from the RX copper (vias, curves,
# fingers, junction vias); with RX_TABS = "single" it takes the place nearest the two fingers that keeps
# MIN_CLEARANCE_MM.  The whole board is then turned so that the terminal ends up at 0 deg (the right,
# on the horizontal axis).  The angle it was turned by is printed and written into Parameters.txt.

# =============================================================================
# TX LAYERS
# =============================================================================
# TX_WIRING = how many layers carry TX turns and how they are joined (any letter case):
#   "single"   : TX_TURNS turns on TX_LAYER_A (TX_LAYER_B is not used); the inner tail runs on the
#                underpass layer (TX_SERIES_UNDERPASS_LAYER).
#   "series"   : TX_TURNS turns on TX_LAYER_A and TX_TURNS turns on TX_LAYER_B in series - two spirals
#                joined by one via at the inner end (2 x TX_TURNS turns; both run the same way round,
#                so their fields add).  Both terminals leave radially at the terminal.  TX_LAYER_A
#                is the spiral that runs inwards from the terminal, TX_LAYER_B the one that runs back out.
#   "parallel" : the same turns on TX_LAYER_A and TX_LAYER_B in parallel, stitched together through
#                vias around the TX terminal: about 6 % more receiver signal than the Top layer alone
#                and about 1.2 - 1.6x the Q in the model (about 0.6x the resistance, but also a lower
#                inductance; more on thin boards and with the staggered break style).  Put TX_LAYER_A on
#                the Top layer.
# TX_LAYER_A / TX_LAYER_B : 1 = Top, 2 = Inner 1, 3 = Inner 2, 4 = Bottom (a 2-layer board has 1
#   and 4); they must differ.  Examples:
#     TX_WIRING = "single", TX_LAYER_A = 4                  : on the Bottom layer, the inner tail on the
#                                                             Top layer (the default)
#     TX_WIRING = "single", TX_LAYER_A = 1                  : on the Top layer, next to the rotor: about
#                                                             15 % (0.8 mm board) to 30 % (1.6 mm board)
#                                                             more receiver signal per TX volt in the model
#     TX_WIRING = "series", TX_LAYER_A = 1, TX_LAYER_B = 4  : the fingers run on the Top layer and the
#                                                             Top turns go around them
#     TX_WIRING = "series", TX_LAYER_A = 1, TX_LAYER_B = 3  : a 4-layer board with the RX on layers 1
#                                                             and 2
#
# Where an RX bridging finger (RX_TAB_LAYER, RX_Parameters.py) runs on a layer that carries
# TX turns, the TX makes way for it:
#   "staggered" (go-around): every turn ends a little before the finger - the outer turns farther
#        away than the inner ones, a staircase - and runs straight out, parallel to the finger, to a
#        via just outside the TX ring.  On another layer a bracket (the innermost turn on the innermost
#        bracket) carries it around the end of the finger to the matching via on the other side.  The
#        fingers must reach past the outermost bracket (about 2 mm longer with the defaults; the checker
#        gives the minimum RX_TAB_LENGTH_MM), which can push the outer board edge out.
#   "stitched" (parallel TX only): the turns on the finger's layer stop at a via on each side
#        of the finger and the turns of the other layer carry the current past it.
# All TX turns are one net, so KiCad's DRC cannot see a via touching another turn: the
# generator checks that itself and warns.
TX_WIRING  = "single"
TX_LAYER_A = 4
TX_LAYER_B = 1

# ---- SERIES block (TX_WIRING = "single" or "series") ---------------------------------------
# A series TX always makes way for the fingers with "staggered" (go-around).
# TX_SERIES_UNDERPASS_LAYER = "auto" or a layer number:
#   "single" : the layer of the inner tail and of the go-around brackets.  "auto": Top for a
#              Bottom TX, Bottom (2-layer) or Inner 1 (4-layer) for a Top TX.
#   "series" : the layer of the go-around brackets.  "auto": the other TX layer, outside its turns.
TX_SERIES_UNDERPASS_LAYER = "auto"

# ---- PARALLEL block (TX_WIRING = "parallel") -----------------------------------------------
# TX_PARALLEL_BREAK_STYLE = how the turns make way for a finger on one of the two layers:
#   "stitched"  : the turns on the finger's layer stop at a via on each side of the finger; the
#                 other layer carries the current past it (no copper outside the TX ring).
#   "staggered" : the turns on the finger's layer go around the finger (go-around), with the
#                 brackets on the other TX layer outside its turns; both layers stay complete.
TX_PARALLEL_BREAK_STYLE = "stitched"
