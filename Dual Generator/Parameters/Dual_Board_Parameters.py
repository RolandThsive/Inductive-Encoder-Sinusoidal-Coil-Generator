"""
Dual_Board_Parameters.py  -  the one stator board and the one rotor disc that both coil sets share.

Units: millimetres, degrees, hertz unless a name says otherwise.
Nothing in this file is computed - edit values only.

The names are the Single Generator's own (Board_Parameters.py, Rotor_Parameters.py) wherever the meaning is the
same, so the wiki's Parameter Reference applies.  What a dual board fixes is not here at all: PCB_LAYERS (always 4),
the RX fingers (none), the TX tails (none) and the TX shape (stepped).  What each coil set has for itself
(its excitation frequency, its RX band, its TX ring, its rotor ring, its IC) is in the Dual_RX1 / RX2, TX1 / TX2,
Rotor1 / Rotor2 and IC1 / IC2 files.
"""

# =============================================================================
# OUTPUT
# =============================================================================
# Dual_RunCoilGenerator.py makes a NEW folder inside OUTPUT_DIR for every run:
#     DualCoil_<bore radius>_<outline radius>_<set 1 loops>x<set 2 loops>_<set 1 TX turns>x<set 2 TX turns>
# e.g. DualCoil_8.5_29.5_1x16_2x3; if it exists already: ..._2x3__1, __2, ...
# It holds the two boards below and Parameters.txt (every value used for that run).
# "Output" = the Output folder in "Dual Generator" (next to Parameters and Dual_Generator), whatever folder
# you run the program from.  A relative path is always taken from "Dual Generator"; a full path
# (e.g. "C:/Boards") is used as it is.
OUTPUT_DIR   = "Output"             # folder in which the DualCoil_... folders are made
STATOR_FILE  = "Stator.kicad_pcb"   # file names inside each DualCoil_... folder
ROTOR_FILE   = "Rotor.kicad_pcb"
# GENERATOR_MODE = what a clearance warning on the finished boards does (any letter case):
#   "normal" : a gap smaller than MIN_CLEARANCE_MM is a warning; the boards are written.
#   "strict" : every such warning is an error; nothing is written.
# Copper that overlaps copper of another net (a short) is always an error, and so is copper of one
# set inside the other set's ring.  Warnings about the parameters themselves stay warnings in both modes.
GENERATOR_MODE = "normal"

CENTER_X_MM  = 100.0                # sensor axis position on the KiCad page
CENTER_Y_MM  = 100.0
PAGE_SIZE_MM = (150, 150)           # KiCad "User" page size (width, height)


# =============================================================================
# STATOR BOARD  (always 4 copper layers: 1 = Top, 2 = Inner 1, 3 = Inner 2, 4 = Bottom)
# =============================================================================
# Via / copper-to-copper rules the generator must respect when it places vias.  Through vias go
# through every layer, so a via of one set is checked against the copper of the other set on every layer.
VIA_DIAMETER_MM   = 0.6             # (the Single Generator's example uses 0.8 / 0.4; 0.6 / 0.3 leaves room in
VIA_DRILL_MM      = 0.3             #  the inner set's tight TX ring)
MIN_CLEARANCE_MM  = 0.15

# ---- board edges (Edge.Cuts circles) and the gap between the sets ----------
# From the centre out, the stator is:
#     bore | RX1 band | TX1 ring | TRACK_GAP_MM | RX2 band | TX2 ring | outline
# Which of these you give and which the generator computes is DUAL_MODE, one of FOUR MODES:
#
#   DUAL_MODE = 1  you give TRACK_GAP_MM, INNER_EDGE_RADIUS_MM, OUTER_EDGE_RADIUS_MM and BAND_SPLIT; both RX bands
#                  stay None (Dual_RX1 / RX2: all four radii None)
#                  -> both bands are fitted between the edges; BAND_SPLIT shares the free width between them
#   DUAL_MODE = 2  you give both RX bands (Dual_RX1 and Dual_RX2); TRACK_GAP_MM and both edges stay None
#                  -> bore and outline come from the bands; the gap is measured and reported
#   DUAL_MODE = 3  you give ONE RX band (Dual_RX1 or Dual_RX2) and TRACK_GAP_MM; the other band and both edges
#                  stay None
#                  -> the other band is placed across the gap with the same half width (RX_A_MM); then as mode 2
#   DUAL_MODE = 4  you give both RX bands and both edges; TRACK_GAP_MM stays None
#                  -> everything as given; each edge is checked for room; the gap is measured and reported
#
# The checker holds what is set against the chosen mode: a value the mode needs that is None, or a value that
# must be None for the mode and is set, is an error that names it (and names the mode that matches what is set,
# when one does).  Change the values, or change DUAL_MODE.
DUAL_MODE = 2

INNER_EDGE_RADIUS_MM  = None         # the centre hole.  Must sit INNER_EDGE_INSET_MM inside the RX1 band.
OUTER_EDGE_RADIUS_MM  = None        # the board edge.  Must leave OUTER_EDGE_OFFSET_MM past the RX2 band, and
                                    # OUTER_EDGE_TAIL_MARGIN_MM past the TX2 ring.
INNER_EDGE_INSET_MM   = 1.2         # bore = RX1 band start - this (the RX1 inner-tip vias sit on the band start)
OUTER_EDGE_OFFSET_MM  = 2.0         # outline = RX2 band end + this, at least
OUTER_EDGE_TAIL_MARGIN_MM = 0.7     # outline = TX2 ring end + this, at least (there is no tail: the ring ends one
                                    # pitch outside the last turn, where the two TX ends sit)
EDGE_LINE_WIDTH_MM    = 0.05

# TRACK_GAP_MM = the copper-free ring between the two sets: from the outermost copper of set 1 (the ends of its
# TX1 ring, half a trace past one pitch outside the last turn) to the innermost copper of set 2 (the RX2 band
# start minus half an RX trace or a via radius, whichever is larger).  The TX rooms come from the Single
# Generator's own TX ring formula and are verified on the built copper.
#   DUAL_MODE 1 and 3: the gap to leave.  DUAL_MODE 2 and 4: must be None; the measured gap must be at least
#   MIN_CLEARANCE_MM.
#   What the gap does NOT do: it is not what isolates the two sets.  A balanced RX band sees no net flux from a
#   round TX ring, however close; the residual TX1 -> RX2 coupling comes from asymmetry (the exits, the vias,
#   layer misregistration) and falls only slowly with distance (dual boards in practice leave 1.1 ... 1.4 mm
#   between the two RX bands, all of it TX turns).  Keep the gap for the copper clearance and the solder mask; what keeps the fine track clean is the
#   distance from ring 1 of the rotor to the RX2 band (ROTOR_1_TO_RX2_MM below).
TRACK_GAP_MM = None

# LAYOUT_TOLERANCE_MM = the generator's rounding allowance: the built copper may differ from the layout formulas
# above by this much before the run warns (the Single Generator rounds its radii), and the outline gets this
# much extra room when ring 2 of the rotor covers the TX2 turns (so the disc's edge clearance is never a hair
# short).  0.05 is enough for every board tried; 0 = no allowance.
LAYOUT_TOLERANCE_MM = 0.05

# BAND_SPLIT (DUAL_MODE = 1 only) = set 1's share of the free radial width: 0.5 = equal RX band widths (a 1x/16x board
# is usually near 0.5, a 1x/32x board near 0.35: the fine track gets the width).
BAND_SPLIT = 0.5


# =============================================================================
# TX TERMINALS
# =============================================================================
# Each set is turned on its own so that its TX ends (there is no tail: the two ends of the series TX sit one
# pitch outside the last turn, on TX_LAYER_A and TX_LAYER_B) end up at this angle.  Different angles keep the
# two sets' breakouts apart.  The RX pattern's zero of each set lands wherever the turn puts it; the record
# file prints both.
TERMINAL_1_DEG = 180.0              # set 1 (inner)
TERMINAL_2_DEG = 0.0                # set 2 (outer)

# The two TX oscillators run free at their own EXCITATION_FREQ_HZ (Dual_TX1 / TX2).  Two free-running carriers
# over one coil area are unproven: two-IC dual boards usually drive ONE tank and set the second IC's TX current
# to zero, or couple the two tanks so that they lock to one frequency and phase.  If the two tanks here are
# driven separately, the IC's switching demodulator mixes the other carrier down to |f2 - n*f1|, and the AGC
# sees both carriers, so:
#   - the two frequencies must differ by at least TX_FREQ_SEPARATION_MIN of the lower one (0.2 = 20 %, the
#     usual rule for neighbouring LC sensors; closer is a warning), and
#   - they must not sit on a small integer ratio (3.0 / 4.5 MHz = 2:3 puts the 2nd harmonic of TX2 onto the
#     3rd harmonic of IC1's demodulator; 3.0 / 4.3 MHz does not): a ratio within TX_FREQ_RATIO_TOLERANCE of
#     any p:q with p, q <= TX_FREQ_RATIO_MAX_ORDER is a warning (0.02 = 2 %; the order 4 covers 2:1, 3:1, 4:1,
#     3:2, 4:3).  TX_FREQ_RATIO_MAX_ORDER = 1 turns the ratio warning off.
# Pulling the two tanks onto each other (injection locking) is not the risk: the lock range is about
# f0 * k / (2 Q), a few tens of kHz for coupling k < 0.3, nowhere near 1 MHz.
TX_FREQ_SEPARATION_MIN   = 0.2
TX_FREQ_RATIO_MAX_ORDER  = 4
TX_FREQ_RATIO_TOLERANCE  = 0.02


# =============================================================================
# STACK-UP AND AIR GAP  (the rotor, the electrical estimate)
# =============================================================================
AIR_GAP_MM           = 1.0          # stator top copper -> rotor copper (one rotor, one air gap)
PCB_THICKNESS_MM     = 3.2          # stator board thickness


# =============================================================================
# ELECTRICAL ESTIMATE  (TX_Electrics.py, printed by Dual_RunCoilGenerator.py for each set: TX inductance,
# tank capacitors, oscillator frequency.  These values never change a board.  They are the one board's, so
# they hold for both sets; the IC each set is checked against is in Dual_IC1 / IC2_Parameters.py.)
# =============================================================================
COPPER_THICKNESS_UM  = 35           # stator copper thickness in micrometres (35 = 1 oz): TX resistance and Q
COPPER_CONDUCTIVITY_S_M = 5.8e7     # copper conductivity in S/m (5.8e7 = annealed copper at 20 C; it drops
                                    # about 0.39 % per K above that): TX resistance, and the rotor's skin
                                    # depth and screening in the rotor summary
TX_AC_RESISTANCE_FACTOR = 2.0       # at the TX frequency skin and proximity effects raise the TX resistance
                                    # above the DC value: the estimate allows for up to this x the DC value
                                    # (Q, tank resistance and the IC check use the worst case)
STACKUP_PREPREG_MM   = 0.2          # distance from an outer copper layer to its inner neighbour (the inner
                                    # layers' depth for the TX inductance; on a board thinner than twice this,
                                    # a third of PCB_THICKNESS_MM is used)
TANK_CAP_SERIES      = "E12"        # standard capacitor values the estimate suggests for the tank: "E6",
                                    # "E12" or "E24" (any letter case)


# =============================================================================
# ROTOR DISC  (one disc, two rings of metal sectors; the rings are set in Dual_Rotor1 / Rotor2)
# =============================================================================
# ROTOR_MODE, once for the disc:
#   "according_to_stator" : each ring follows its own set: LOOPS sectors, radial extent from the set's RX band
#                           and TX ring (the ROTOR_AUTO_* values in Dual_Rotor1 / Rotor2); the disc's bore and
#                           outline are the stator's
#   "custom"              : each ring from its ROTOR_CUSTOM_* values; the disc's edges from the two lines below
ROTOR_MODE = "according_to_stator"
ROTOR_AUTO_EDGE_CLEARANCE_MM = 0.5  # according_to_stator: ring copper stays this far from the bore and the outline

# ROTOR_START_ANGLE_ZERO = where each ring's start angle (ROTOR_AUTO_START_ANGLE_DEG / ROTOR_CUSTOM_START_ANGLE_DEG
# in Dual_Rotor1 / Rotor2) is measured from (any letter case):
#   "rx_zero" : from its own set's RX pattern zero.  Each set is turned by its own angle (TERMINAL_1 / 2_DEG
#               above), and the generator adds that turn to the ring's start angle, so that both rings start at
#               their own set's zero and the coarse and the fine track read 0 at the same shaft angle (what the
#               coarse-to-fine decision needs; the firmware calibrates the residual).
#   "board"   : from the board's +x axis, as the Single Generator measures it; the turn of each set is not added.
#               The record file prints each set's zero, so you can add it by hand.
ROTOR_START_ANGLE_ZERO = "rx_zero"
ROTOR_CUSTOM_OUTLINE_RADIUS_MM  = 26.875 # custom: outer edge of the disc (None = no outline); the values here are what
ROTOR_CUSTOM_BORE_RADIUS_MM     = 7.25   # custom: centre hole (None = no hole);  "according_to_stator" computes for the default board

# ROTOR_TRACK_GAP_MM = the bare ring that must stay between ring 1's outer radius and ring 2's inner radius
# (an error when smaller, naming the extension to change).  Dual boards in practice keep 2.3 ... 3.0 mm.  It is
# a proxy: the quantity that matters is how far each ring's metal stays from the OTHER set's RX band, below.
ROTOR_TRACK_GAP_MM = 2.0

# ROTOR_1_TO_RX2_MM = the least distance from ring 1's outer radius to the innermost RX2 copper (a warning
# when smaller).  Ring 1 is the dangerous one: a 1x target is a half moon, so any of its field reaching the
# RX2 band modulates the fine signal once per turn, a first-harmonic error that no fine-track calibration
# removes (nearby metal adds a first-order harmonic to the measured angle).  The usual layout rule for any
# copper near a coil is 3 mm, 5 mm if the design allows: copper 0.9 mm from a coil leaves about 12 % of the
# RX voltage, copper 2.6 mm away about 45 %.  Dual 1x/16x boards in practice sit at about 3 mm.  Use 5.0 when
# the radius allows it.
ROTOR_1_TO_RX2_MM = 3.0

# ROTOR_2_TO_RX1_MM = the least distance from ring 2's inner radius to the outermost RX1 copper (a warning
# when smaller).  Ring 2 near the coarse band only adds a ripple at LOOPS of set 2 per turn, which a 1x RX
# rejects by symmetry and the coarse decision averages out, so it may come closer than ring 1 may.
ROTOR_2_TO_RX1_MM = 2.0

ROTOR_PCB_THICKNESS_MM = None   # thickness of the rotor disc written into the KiCad file (mm); None = the
                                # stator's PCB_THICKNESS_MM.  It changes nothing in the copper.

# Points on every circular arc of a rotor sector:
#   ROTOR_ARC_STEPS_PER_SECTOR = "auto" : as many as ROTOR_CHORD_TOLERANCE_MM needs (at least 8)
#   ROTOR_ARC_STEPS_PER_SECTOR = number : that many (8 ... 5000).
# ROTOR_CHORD_TOLERANCE_MM = how far the polygon may lie outside the true circle: 0.001 mm = 1 micron, also the
#   smallest value allowed.
ROTOR_ARC_STEPS_PER_SECTOR = "auto"
ROTOR_CHORD_TOLERANCE_MM   = 0.001

# Solder mask expansion over the rotor copper, the same for every ring and layer:
#   0.05  the opening is 0.05 mm wider than the copper on every side
#   0     the opening is exactly the copper outline
#   -1    no opening: the solder mask stays over the copper
ROTOR_SOLDER_MASK_EXPANSION_MM = -1
