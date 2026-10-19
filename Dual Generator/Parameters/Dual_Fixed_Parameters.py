"""
Dual_Fixed_Parameters.py  -  the Single Generator settings that every dual board FIXES.

A dual board is built a fixed way: 4 layers, no RX bridging fingers, no TX tail copper past the ring, stepped
TX turns (series or parallel wiring, chosen in Dual_TX1 / TX2), and rotor ring 1 (the coarse, inner ring) never
covers its TX turns.  The Single Generator still wants these names, so
they live here, where you can read them, instead of hidden in the code.  Every value is FIXED: the dual
checker refuses any other value and says why.  Do not change them; to build a board with other settings use
the Single Generator.

Units: millimetres.  Nothing in this file is computed.
"""

# ---- the board -----------------------------------------------------------------------------------------------
PCB_LAYERS = 4                          # FIXED: a dual board is a 4-layer board (RX on two layers and TX on two
                                        # layers per set; two layers cannot hold two sets without fingers)
RX_RISING_EDGE_LAYER = "F.Cu"           # FIXED: a 2-layer setting; unused with 4 layers, but the Single
                                        # Generator's rule table wants it

# ---- RX bridging fingers: none ------------------------------------------------------------------------------
RX_TABS = "none"                        # FIXED: no bridging fingers (set 1's fingers would cross set 2's band)
RX_TAB_LAYER = "auto"                   # FIXED: (fingers only) unused
RX_TAB_LENGTH_MM = 0.0                  # FIXED: (fingers only) unused
RX_TAB_WIDTH_MM = 1.0                   # FIXED: (fingers only) unused

# ---- TX: stepped turns, nothing past one pitch outside the last turn ----------------------------------------
TX_SHAPE = "stepped_diagonal"           # FIXED: stepped turns only ("spiral" and "stepped_arc" are not used on a
                                        # dual board; stepped_arc's last arc would need a tail)
TX_TAIL_EXTRA_MM = 0.0                  # FIXED: no extra tail; the ring ends one pitch outside the last turn
                                        # (series: its two ends sit there, one per layer; parallel: its inner
                                        # tail ends there), so nothing runs out through the other set
TX_SERIES_UNDERPASS_LAYER = "auto"      # FIXED: (series with fingers only) unused
TX_PARALLEL_BREAK_STYLE = "stitched"    # FIXED: (parallel with fingers only) unused
TX_STEPPED_ARC_RADIUS_MM = "auto"       # FIXED: (stepped_arc only) unused

# ---- rotor ring 1 (the ring facing set 1): never over TX1 ---------------------------------------------------
# Ring 2 has its own ROTOR_AUTO_COVER_TX and ROTOR_AUTO_TX_OVERHANG_MM in Dual_Rotor2_Parameters.py.
ROTOR_AUTO_COVER_TX = False             # FIXED: ring 1 stops ROTOR_AUTO_TX_CLEARANCE_MM inside the TX1 ring;
                                        # metal over TX1 would sit right next to set 2's RX band and modulate
                                        # the fine signal once per turn (ROTOR_1_TO_RX2_MM, Dual_Board_Parameters.py)
ROTOR_AUTO_TX_OVERHANG_MM = 0.5         # FIXED: (cover only) unused for ring 1
