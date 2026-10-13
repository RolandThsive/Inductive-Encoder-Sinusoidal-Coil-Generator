"""
Board_Parameters.py  -  board, stack-up, via and output settings shared by every generator.

Units: millimetres, degrees, hertz unless a name says otherwise.
Nothing in this file is computed - edit values only.
"""

# =============================================================================
# OUTPUT
# =============================================================================
# RunCoilGenerator.py makes a NEW folder inside OUTPUT_DIR for every run (OutputDirectoryManager.py):
#     Coil_<board inside radius>_<board outside radius>_<RX loops>_<RX sub-coils>_<TX turns>_<TX wiring>_<TX shape>
#     TX wiring = Single (one TX layer), Series or Parallel (two TX layers); TX shape = Stepped or Spiral
# e.g. Coil_36.8_56.6_8_1_3_Single_Stepped; if it exists already: ..._Stepped__1, __2, ...
# It holds the two boards below and Parameters.txt (every value used for that run).
# "Output" = the Output folder of the project (next to Parameters, Generator, Analyser_And_Optimizer), whatever
# folder you run the program from.  A relative path is always taken from the project folder; a full path
# (e.g. "C:/Boards") is used as it is.
OUTPUT_DIR   = "Output"             # folder in which the Coil_... folders are made
STATOR_FILE  = "Stator.kicad_pcb"   # file names inside each Coil_... folder
ROTOR_FILE   = "Rotor.kicad_pcb"

CENTER_X_MM  = 100.0                # sensor axis position on the KiCad page
CENTER_Y_MM  = 100.0
PAGE_SIZE_MM = (200, 200)           # KiCad "User" page size (width, height)


# =============================================================================
# STATOR BOARD
# =============================================================================
# PCB_LAYERS = number of copper layers of the STATOR board.  Only 2 or 4.
#   2 : the RX coils use Top and Bottom (the proven layout).
#   4 : the RX coils use the layers named by RX_LAYER_A / RX_LAYER_B
#       (see RX_Parameters.py); the TX coil can use two layers (TX_Parameters.py).
# All vias are ordinary through-hole vias (no blind / buried vias needed).
# Keep the layers that carry no coil free of copper pours under the coil area -
# a plane there acts like an extra target and weakens the signal.
PCB_LAYERS = 4

# Via / copper-to-copper rules the generator must respect when it places vias.
VIA_DIAMETER_MM   = 0.6
VIA_DRILL_MM      = 0.3
MIN_CLEARANCE_MM  = 0.2

# ---- board outline (Edge.Cuts circles) --------------------------------------
INNER_EDGE_INSET_MM   = 1.2         # inner hole radius = RX inside radius - this ...
INNER_EDGE_RADIUS_MM  = 15          # ... or set a fixed radius here: the hole gets exactly this
                                    # radius and the RX band starts INNER_EDGE_INSET_MM outside it
                                    # (INSIDE_RADIUS_MM in RX_Parameters.py is then not used).
                                    # None = the formula above.
OUTER_EDGE_OFFSET_MM  = 4.0         # outer edge = RX outside radius + this ...
OUTER_EDGE_RADIUS_MM  = 27          # ... or set a fixed radius here: the board edge gets exactly this
                                    # radius and the RX band ends where the rule below would have put
                                    # this edge, so the TX turns, the TX tail and the bridging fingers
                                    # fit inside it with the usual margins
                                    # (OUTSIDE_RADIUS_MM in RX_Parameters.py is then not used).
                                    # None = the largest of the formula above,
                                    # (TX tail end + OUTER_EDGE_TAIL_MARGIN_MM) and
                                    # (bridging finger tip + half an RX trace + OUTER_EDGE_TAIL_MARGIN_MM)
OUTER_EDGE_TAIL_MARGIN_MM = 0.7
EDGE_LINE_WIDTH_MM    = 0.05


# =============================================================================
# MECHANICAL / PHYSICAL ASSUMPTIONS  (used by field_compensated + auto rotor)
# =============================================================================
AIR_GAP_MM           = 1.0          # stator top copper -> rotor copper
PCB_THICKNESS_MM     = 1.6          # stator board thickness
EXCITATION_FREQ_HZ   = 3.5e6        # TX oscillator frequency aimed for, with the rotor in place
                                    # (in hertz: 3.5e6 = 3.5 MHz).  The electrical estimate sizes the
                                    # tank capacitors for it; the rotor summary uses it for the skin depth.


# =============================================================================
# ELECTRICAL ESTIMATE  (CoilElectrics.py, printed by RunCoilGenerator.py, AnalyzeCoil.py and
# OptimizeCoil.py: TX inductance, tank capacitors, oscillator frequency, receiver voltage.
# These values never change a board.)
# =============================================================================
RECEIVER_IC          = "IPS2550"    # the IC the coil is checked against: "IPS2550", "IPS2200", or None
                                    # (no checks).  Its oscillator range, minimum tank resistance, TX
                                    # voltage and receiver input range are taken from the Renesas datasheets.
COPPER_THICKNESS_UM  = 35           # stator copper thickness in micrometres (35 = 1 oz): TX resistance and Q
TX_AMPLITUDE_VPP     = None         # TX voltage across the coil, peak-to-peak, if you know it (measured, or
                                    # set by the IC's coil current).  None = the range given by the IC's datasheet.
