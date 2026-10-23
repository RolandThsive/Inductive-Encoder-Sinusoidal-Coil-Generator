"""
Board_Parameters.py  -  board, stack-up, via and output settings shared by every generator.

Units: millimetres, degrees, hertz unless a name says otherwise.
Nothing in this file is computed - edit values only.
"""

# =============================================================================
# OUTPUT
# =============================================================================
# RunCoilGenerator.py makes a NEW folder inside OUTPUT_DIR for every run (OutputFolders.py):
#     Coil_<board inside radius>_<board outside radius>_<RX loops>_<RX sub-coils>_<TX turns>_<TX wiring>_<TX shape>
#     TX wiring = Single (one TX layer), Series or Parallel (two TX layers);
#     TX shape  = SteppedDiagonal, SteppedArc or Spiral (TX_SHAPE)
# e.g. Coil_15_27_1_1_3_Single_SteppedDiagonal; if it exists already: ..._SteppedDiagonal__1, __2, ...
# It holds the two boards below and Parameters.txt (every value used for that run).
# "Output" = the Output folder in "Single Generator" (next to Parameters and Generator), whatever
# folder you run the program from.  A relative path is always taken from "Single Generator"; a full path
# (e.g. "C:/Boards") is used as it is.
OUTPUT_DIR   = "Output"             # folder in which the Coil_... folders are made
STATOR_FILE  = "Stator.kicad_pcb"   # file names inside each Coil_... folder
ROTOR_FILE   = "Rotor.kicad_pcb"
# GENERATOR_MODE = what a warning about the finished boards (clearances, outline, page, rotor) does
# (any letter case):
#   "normal" : it stays a warning; the boards are written.
#   "strict" : every such warning is an error; nothing is written.
# Copper that overlaps copper of another net (a short) is always an error.  Warnings about the
# parameters themselves (ranges, estimates) stay warnings in both modes.
GENERATOR_MODE = "normal"

CENTER_X_MM  = 100.0                # sensor axis position on the KiCad page
CENTER_Y_MM  = 100.0
PAGE_SIZE_MM = (200, 200)           # smallest KiCad "User" page (width, height); grown to the right and down
                                    # when the board or the title block needs more room.  A board too close to
                                    # the top or left edge is only warned about (raise CENTER_X_MM / CENTER_Y_MM)


# =============================================================================
# STATOR BOARD
# =============================================================================
# PCB_LAYERS = number of copper layers of the STATOR board.  Only 2 or 4.
#   2 : the RX coils use Top and Bottom (the proven layout).
#   4 : the RX coils use the layers named by RX_LAYER_A / RX_LAYER_B
#       (see RX_Parameters.py).
# With either layer count the TX can use one or two layers (TX_Parameters.py; a 2-layer board
# offers 1 and 4).
# VIA_TYPE says what the vias are (below).
# Keep the layers that carry no coil free of copper pours under the coil area -
# a plane there acts like an extra target and weakens the signal.
PCB_LAYERS = 2

# Via / copper-to-copper rules the generator must respect when it places vias.
VIA_DIAMETER_MM   = 0.8
VIA_DRILL_MM      = 0.4
MIN_CLEARANCE_MM  = 0.2

# VIA_TYPE = what every via the generator places is:
#   "through" : a plated hole through the whole board (every via, on 2 and on 4 layers).
#   "blind"   : 4-layer boards only.  Every via is written as a blind via between the two copper layers it
#               actually joins (an RX tip via: the two RX layers; a TX via: the two TX layers, or the TX layer
#               and the layer of the inner tail / the go-around brackets).  Common fabs laser-drill blind vias
#               only between an outer layer and its neighbour (Top + Inner 1, Inner 2 + Bottom) and at most
#               about 0.15 mm wide, so set VIA_DRILL_MM / VIA_DIAMETER_MM to such sizes; the checker warns about a
#               pair that skips a layer (Top + Inner 2, Inner 1 + Bottom), tells when a pair is the two inner
#               layers (a buried via, mechanically drilled) and when it is Top + Bottom (a through via after all).
#               On a 2-layer board "blind" is an error.
# The clearance checks treat every via as a through via on either setting.
VIA_TYPE = "through"

# ---- board outline (Edge.Cuts circles) --------------------------------------
INNER_EDGE_INSET_MM   = 1.2         # centre hole radius = RX band start - this ...
INNER_EDGE_RADIUS_MM  = 15.0        # ... or set a fixed radius here: the hole gets exactly this radius.
                                    # RX band given (RX_Parameters.py): both are used as given - the hole
                                    #   must be at least INNER_EDGE_INSET_MM inside the band.
                                    # RX band None: the band starts INNER_EDGE_INSET_MM outside the hole.
                                    # None = the formula above.
OUTER_EDGE_OFFSET_MM  = 4.0         # outer edge = RX band end + this ...
OUTER_EDGE_RADIUS_MM  = 27.0        # ... or set a fixed radius here: the board edge gets exactly this radius.
                                    # RX band given (RX_Parameters.py): both are used as given - the edge
                                    #   must leave at least the room the rule below needs.
                                    # RX band None: the band ends where the rule below would have put this
                                    #   edge, so the TX turns, the TX tail and the bridging fingers fit
                                    #   inside it with the usual margins.
                                    # None = the largest of the formula above,
                                    # (TX tail end + OUTER_EDGE_TAIL_MARGIN_MM) and
                                    # (bridging finger tip + half an RX trace + OUTER_EDGE_TAIL_MARGIN_MM)
OUTER_EDGE_TAIL_MARGIN_MM = 0.7
EDGE_LINE_WIDTH_MM    = 0.05


# =============================================================================
# STACK-UP AND AIR GAP  (the rotor, the electrical estimate)
# =============================================================================
AIR_GAP_MM           = 1.0          # stator top copper -> rotor copper
PCB_THICKNESS_MM     = 1.6          # stator board thickness
EXCITATION_FREQ_HZ   = 3.5e6        # TX oscillator frequency aimed for, with the rotor in place
                                    # (in hertz: 3.5e6 = 3.5 MHz).  The electrical estimate sizes the
                                    # tank capacitors for it; the rotor summary uses it for the skin depth.


# =============================================================================
# ELECTRICAL ESTIMATE  (TX_Electrics.py, printed by RunCoilGenerator.py: TX inductance, tank
# capacitors, oscillator frequency.  These values never change a board.  The receiver IC the coil is
# checked against: IC_Parameters.py.)
# =============================================================================
COPPER_THICKNESS_UM  = 35           # stator copper thickness in micrometres (35 = 1 oz): TX resistance and Q
COPPER_CONDUCTIVITY_S_M = 5.8e7     # copper conductivity in S/m (5.8e7 = annealed copper at 20 C; it drops
                                    # about 0.39 % per K above that): TX resistance, and the rotor's skin
                                    # depth and screening in the rotor summary
TX_AC_RESISTANCE_FACTOR = 2.0       # at the TX frequency skin and proximity effects raise the TX resistance
                                    # above the DC value: the estimate allows for up to this x the DC value
                                    # (Q, tank resistance and the IC check use the worst case)
STACKUP_PREPREG_MM   = 0.2          # 4-layer stator: distance from an outer copper layer to its inner
                                    # neighbour (the inner layers' depth for the TX inductance; on a board
                                    # thinner than twice this, a third of PCB_THICKNESS_MM is used)
TANK_CAP_SERIES      = "E12"        # standard capacitor values the estimate suggests for the tank: "E6",
                                    # "E12" or "E24" (any letter case)
