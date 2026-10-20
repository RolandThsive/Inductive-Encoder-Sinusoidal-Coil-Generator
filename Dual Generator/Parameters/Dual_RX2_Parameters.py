"""
Dual_RX2_Parameters.py  -  the receiver (RX) coils of set 2, the outer set.  Dual_RX1_Parameters.py has the
same names for set 1.

The names are the Single Generator's own (RX_Parameters.py), so the wiki's Parameter Reference describes each
one.  Left out on purpose: the bridging fingers (RX_TABS, RX_TAB_LAYER, RX_TAB_LENGTH_MM, RX_TAB_WIDTH_MM; a dual
board has none, both RX rings are plain bands broken out by hand) and RX_RISING_EDGE_LAYER (2-layer boards only;
a dual board always has 4 layers and uses RX_LAYER_A / RX_LAYER_B).

Units: millimetres, degrees.  Nothing in this file is computed - edit values only.
Layers are numbered 1 = Top, 2 = Inner 1, 3 = Inner 2, 4 = Bottom.
"""

# LOOPS = electrical periods per mechanical turn (1 ... 16).  The outer set is the fine one: its LOOPS
# periods set the resolution, and the inner set's absolute angle says which period the rotor is in.  The inner
# set's angle error must stay below half an outer period (180 / LOOPS mechanical degrees).
LOOPS = 16

# Radial band occupied by the RX copper (centre line of the traces).  Give it in ONE of two ways, or not at all
# (DUAL_MODE, Dual_Board_Parameters.py, says which):
#   INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM : the two radii of the band          (RX_R_BASE_MM / RX_A_MM = None)
#   RX_R_BASE_MM / RX_A_MM               : its centre and how far the coils swing in and out from it:
#                                          band = RX_R_BASE_MM - RX_A_MM ... RX_R_BASE_MM + RX_A_MM
#                                          (INSIDE_RADIUS_MM / OUTSIDE_RADIUS_MM = None)
#   all four None                        : the generator places this band (DUAL_MODE = 1, or 3 when the other
#                                          band is set); the record file prints the values it chose
# Each pair goes together (both numbers or both None); both pairs set is an error (the band would be given twice).
INSIDE_RADIUS_MM  = 18.0
OUTSIDE_RADIUS_MM = 23.9
RX_R_BASE_MM      = None
RX_A_MM           = None

RX_TRACE_WIDTH_MM = 0.15

# Net names of this set.  They must differ from the other set's (KiCad would merge equal names).
RX_NET_PHASE_0_2 = "SIN_2"      # phases 0 and 2 (sine, +/-)
RX_NET_PHASE_1_3 = "COS_2"      # phases 1 and 3 (cosine, +/-)

# "equal_area" (the default) or "cosine_r" (a limacon): see the wiki, RX Profiles.
RX_PROFILE = "equal_area"

# Polyline resolution of one electrical period: "auto" or a multiple of 8 (48 ... 4096).
STEPS_PER_LOOP         = "auto"
RX_CHORD_TOLERANCE_MM  = 0.001

# Sub-coils per RX coil (1, 2 or 3) and their spacing in electrical degrees.
RX_SUBCOILS               = 1
RX_SUBCOIL_SPLIT_ELEC_DEG = 45.0

# The two layers of this set's RX coils (they must differ).  Both sets may use the same two layers: their
# copper never overlaps radially.  Keep one layer free of both sets' copper across set 2 (the recommended
# RX on 1 + 2 and TX on 1 + 3 leave Bottom free), so that set 1's six leads can be routed out by hand.
RX_LAYER_A = 1
RX_LAYER_B = 2

# Electrical angle of the outer-tip via (90 = on the tip, about 50 ... 130).
RX_VIA_ELECTRICAL_DEG = 90.0
