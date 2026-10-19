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
# All vias are ordinary through-hole vias (no blind / buried vias needed).
# Keep the layers that carry no coil free of copper pours under the coil area -
# a plane there acts like an extra target and weakens the signal.
PCB_LAYERS = 2

# Via / copper-to-copper rules the generator must respect when it places vias.
VIA_DIAMETER_MM   = 0.8
VIA_DRILL_MM      = 0.4
MIN_CLEARANCE_MM  = 0.2

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
# capacitors, oscillator frequency.  These values never change a board.)
# =============================================================================
RECEIVER_IC          = "IPS2550"    # the IC the coil is checked against: "IPS2550", "IPS2200", or None
                                    # (no checks).  Its oscillator range and minimum tank resistance are
                                    # taken from the Renesas datasheets.
COPPER_THICKNESS_UM  = 35           # stator copper thickness in micrometres (35 = 1 oz): TX resistance and Q
