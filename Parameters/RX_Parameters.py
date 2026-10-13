"""
RX_Parameters.py  -  receiver (RX) coils: the SIN and COS coils of the stator.

Units: millimetres, degrees.  Nothing in this file is computed - edit values only.
"""

# =============================================================================
# SIZE AND PERIODICITY
# =============================================================================
# LOOPS = number of electrical periods (sine waves) per mechanical turn (1 ... 16).
#   - It is also the number of metal sectors the rotor must have.
#   - Unique absolute range of the sensor = 360 / LOOPS degrees.
#   - 1 loop gives true 0-360 deg absolute output; higher counts give
#     proportionally finer angular resolution/accuracy per degree.
#   (1 loop = 1 full sine period = 2 lobes: one positive and one negative.)
LOOPS = 4

# Radial band occupied by the RX copper (centre line of the traces).
# INSIDE_RADIUS_MM is not used when INNER_EDGE_RADIUS_MM (Board_Parameters.py) is set: the
# band then starts INNER_EDGE_INSET_MM outside the centre hole.
# OUTSIDE_RADIUS_MM is not used when OUTER_EDGE_RADIUS_MM (Board_Parameters.py) is set: the
# band then ends far enough inside the board edge for the TX turns, the TX tail and the
# bridging fingers (the checker prints the radius it gets).
INSIDE_RADIUS_MM  = 38.0
OUTSIDE_RADIUS_MM = 51.0

RX_TRACE_WIDTH_MM = 0.2

# Net names. Phases 0 and 2 (sine, +/-) form one coil, phases 1 and 3
# (cosine, +/-) form the other.
RX_NET_PHASE_0_2 = "SIN_Signal"
RX_NET_PHASE_1_3 = "COS_Signal"

# Rotation of the whole RX pattern, as  (fraction of one loop) + (degrees).
# -0.35 reproduces the original generator (and your 1-loop / 2-loop examples).
RX_ZERO_OFFSET_LOOP_FRACTION = -0.35
RX_ZERO_OFFSET_DEG           = 0.0


# =============================================================================
# SHAPE OF THE RX BOUNDARY  r(angle)
# =============================================================================
#   "equal_area"         r^2 = mean(r^2) + amp * sin(...)   (your current coils)
#                        The flux weight of a single curve is an exact sine for a
#                        uniform field.
#   "cosine_r"           r = mean(r) + amp * sin(...)       (a limacon; the law the
#                        Renesas IPS2200 reference design follows, measured from its
#                        layout).  For an antiphase pair (which is what every coil
#                        here is) the flux weight is also an exact sine for a
#                        uniform field.
#   "field_compensated"  same as equal_area, but bent so the weight stays an exact
#                        sine in the NON-uniform field of the TX ring. Uses
#                        AIR_GAP_MM, PCB_THICKNESS_MM and the TX settings.
RX_PROFILE = "equal_area"

# Polyline resolution of one electrical period.
#   "auto"  -> smallest multiple of 8 whose chord error is <= CHORD_TOLERANCE_MM
#   integer -> fixed value (a multiple of 8 from 48 to 4096). 200 matches the old script.
STEPS_PER_LOOP     = "auto"
CHORD_TOLERANCE_MM = 0.005


# =============================================================================
# SUB-COILS  (distributed winding, as in the Renesas IPS2200 reference design)
# =============================================================================
# Every RX coil (SIN and COS) is built from RX_SUBCOILS sub-coils.  A sub-coil is
# one antiphase pair of curves - exactly what a single coil is today.  The
# sub-coils of one coil are spread RX_SUBCOIL_SPLIT_ELEC_DEG apart (electrical
# degrees: one loop = 360) and wired in series, so each coil still is ONE closed
# series loop that you break out where you like.
#
#   RX_SUBCOILS = 1 : today's layout (the split is ignored)
#   RX_SUBCOILS = 2 : Renesas-style, 2 sub-coils per coil (use split = 45)
#   RX_SUBCOILS = 3 : three sub-coils, centred on the coil axis (use split = 30, which spaces the curves
#                     evenly; 45 puts two curves on top of each other.  Crowded: needs a wide RX band
#                     or small vias; watch the clearance warnings)
#
# Effect of a split d between two sub-coils (relative to ONE sub-coil):
#     signal      x 2*cos(d/2)            (d = 45 -> 1.85x)
#     harmonic h  x 2*cos(h*d/2)          (d = 45 -> 3rd and 5th down ~59 %,
#                                          d = 60 -> 3rd removed,  d = 36 -> 5th removed)
# The split is rounded to a whole even number of polyline nodes (with STEPS_PER_LOOP =
# "auto" the resolution is chosen so that your value is reproduced; the summary prints
# the value actually used).
# Geometry limits: with 2 sub-coils the curve tips of the SIN and COS coils are spaced
# split and (90 - split) apart, so 45 is the uniform, roomiest choice; much above 50 or below
# 35 crowds the tip vias.  At the default radii (38 ... 51 mm) 2 sub-coils were verified
# clean for 1 ... 12 loops; at 13 ... 16 loops the tip vias of neighbouring coils get too
# close (warnings are printed) - use 1 sub-coil there or a wider RX band.
RX_SUBCOILS               = 1
RX_SUBCOIL_SPLIT_ELEC_DEG = 45.0


# =============================================================================
# LAYERS  (which copper layers carry the RX coils)
# =============================================================================
# PCB_LAYERS = 2 (Board_Parameters.py): Top and Bottom are used;
#                RX_RISING_EDGE_LAYER chooses which one carries the rising edges.
# PCB_LAYERS = 4: RX_LAYER_A / RX_LAYER_B name the two layers
#         1 = Top (F.Cu)   2 = Inner 1 (In1.Cu)   3 = Inner 2 (In2.Cu)   4 = Bottom (B.Cu)
#   They must differ.  Typical choice: 1 and 2 (Top + Inner 1), which sit closest
#   together in a standard 4-layer stack-up.  A carries the rising edges, B the
#   falling edges.
RX_LAYER_A = 1
RX_LAYER_B = 2
RX_RISING_EDGE_LAYER  = "F.Cu"      # 2-layer boards only: "F.Cu" or "B.Cu"

# Layer scheme.  Every phase carries its RISING edges (radius growing with
# angle) on one layer and its FALLING edges on the other, so that at every
# azimuth the two strands of a coil sit on opposite layers (equal air-gap
# exposure for sine and cosine, no layer-induced gain/harmonic mismatch).
# The layer swap (via) happens near the outer and inner tip of every lobe:
# RX_VIA_ELECTRICAL_DEG is the electrical angle of the outer-tip via
# (90 = exactly on the tip, allowed range about 50 ... 130).
RX_VIA_ELECTRICAL_DEG = 90.0


# =============================================================================
# BRIDGING FINGERS
# =============================================================================
# At the outer tip of every lobe of every phase the trace leaves the RX band
# radially, crosses OVER the TX turns and comes back, so the RX coils can be broken
# out outside the TX ring.  The finger sits on the RX layer nearest the top that is
# not a TX layer.  No terminals are created - you break the coils out yourself.
#   "all"    = a finger at every outer tip of every phase (as in the original)
#   "single" = one finger per RX coil (one for sin, one for cos), each at the outer
#              tip nearest the TX tail that keeps MIN_CLEARANCE_MM from the TX tail,
#              the TX via and the other finger: the coils are broken out next to the
#              TX terminal.  (With TX_START_ANGLE_DEG = "auto" the tail goes to 0 deg.)
#   "none"   = plain RX band, no fingers
# In the analyser "single" was as accurate as "none" and, untuned, more accurate than
# "all" from 4 loops up (the many fingers distort the coil shape); once the rotor is
# tuned for each, the three are within about 20 %.  A 3-D check with the real TX tail,
# via and layer depths gave a constant offset below about 0.2 % of the signal for
# "single" - the same order as for "all" and "none".
RX_TABS           = "Single"
# RX_TAB_LAYER = layer of the fingers: "auto" = the RX layer nearest the top that carries
# no TX turn (the original rule) - or, when both RX layers carry TX turns (e.g. a series TX on
# [1, 4]), the RX layer nearest the top - or 1 (Top), 2 (Inner 1), 3 (Inner 2), 4 (Bottom).
# On a layer with TX turns the TX makes way for every finger (go-around or stitched,
# TX_Parameters.py).
RX_TAB_LAYER      = "auto"
RX_TAB_LENGTH_MM  = 3.0     # finger reaches OUTSIDE_RADIUS + this (3.0 = your examples,
                            # i.e. r = 54.0 mm); only lengthened if that would not clear
                            # the outermost complete TX turn
RX_TAB_WIDTH_MM   = 1.0     # spacing of the two finger legs (snapped to polyline nodes).
                            # The finger adds a small flux sliver to the coil; a narrower
                            # finger disturbs the sin/cos signal less (matters most at
                            # high LOOPS). Keep >= about 0.6 for etching.
