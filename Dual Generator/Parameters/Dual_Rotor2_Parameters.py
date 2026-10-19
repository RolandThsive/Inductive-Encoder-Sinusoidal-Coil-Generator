"""
Dual_Rotor2_Parameters.py  -  ring 2 of the rotor disc: the metal sectors that face set 2 (the outer set).
Dual_Rotor1_Parameters.py has the same names for ring 1.  The disc itself (ROTOR_MODE, bore, outline,
thickness, arc resolution, solder mask) is set once in Dual_Board_Parameters.py.

The names are the Single Generator's own (Rotor_Parameters.py).  Ring 2 may cover its TX turns like a single
board's rotor does (ROTOR_AUTO_COVER_TX = True: the outline has room for it; ring 1 has the same setting and
keeps it False); its inner edge must stay ROTOR_TRACK_GAP_MM (Dual_Board_Parameters.py) outside ring 1 and
ROTOR_2_TO_RX1_MM outside set 1's RX copper (the generator warns when it does not).

Units: millimetres, degrees.  Nothing in this file is computed - edit values only.
"""

# ---- ROTOR_MODE = "according_to_stator" (Dual_Board_Parameters.py): LOOPS of set 2 sectors ----------------
ROTOR_AUTO_DUTY             = 0.5   # metal fraction of each period (0.5 = 180 deg electrical)
ROTOR_AUTO_START_ANGLE_DEG  = 0.0   # angle of the first sector edge, measured from set 2's RX pattern zero
                                    # (the generator adds the angle the set was turned by; see Dual_Rotor1)
# The outer edge of this ring: over the TX2 turns (True, ending ROTOR_AUTO_TX_OVERHANG_MM past the outermost
# one) or inside the TX2 ring (False, ROTOR_AUTO_EXTENSION_OUTER_MM past the RX band, at most
# ROTOR_AUTO_TX_CLEARANCE_MM inside the TX ring).
ROTOR_AUTO_COVER_TX         = True
ROTOR_AUTO_TX_OVERHANG_MM   = 0.5
ROTOR_AUTO_EXTENSION_MM       = None  # past the RX band, both edges.  None = AIR_GAP_MM
ROTOR_AUTO_EXTENSION_INNER_MM = 0.5   # inner edge only.  None = ROTOR_AUTO_EXTENSION_MM.  Kept short so that
                                      # ring 2 stays ROTOR_TRACK_GAP_MM away from ring 1
ROTOR_AUTO_EXTENSION_OUTER_MM = None  # outer edge only (ROTOR_AUTO_COVER_TX = False).  None = ROTOR_AUTO_EXTENSION_MM
ROTOR_AUTO_TX_CLEARANCE_MM  = 0.1   # ROTOR_AUTO_COVER_TX = False only: copper stays this far inside the TX2 ring
ROTOR_AUTO_COPPER_LAYERS    = ["F.Cu"]   # layer(s) carrying this ring's sectors

# ---- ROTOR_MODE = "custom" -----------------------------------------------------------------------------------
ROTOR_CUSTOM_SECTORS            = 16
ROTOR_CUSTOM_DUTY               = 0.5
ROTOR_CUSTOM_START_ANGLE_DEG    = 0.0
ROTOR_CUSTOM_INNER_RADIUS_MM    = 19.0
ROTOR_CUSTOM_OUTER_RADIUS_MM    = 28.8
ROTOR_CUSTOM_COPPER_LAYERS      = ["F.Cu"]
