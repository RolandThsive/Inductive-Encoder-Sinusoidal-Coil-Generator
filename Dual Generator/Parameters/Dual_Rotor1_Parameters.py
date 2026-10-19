"""
Dual_Rotor1_Parameters.py  -  ring 1 of the rotor disc: the metal sectors that face set 1 (the inner set).
Dual_Rotor2_Parameters.py has the same names for ring 2.  The disc itself (ROTOR_MODE, bore, outline,
thickness, arc resolution, solder mask) is set once in Dual_Board_Parameters.py.

The names are the Single Generator's own (Rotor_Parameters.py).  Left out on purpose: ROTOR_AUTO_COVER_TX and
ROTOR_AUTO_TX_OVERHANG_MM - ring 1 never covers its TX turns, because metal over TX1 would sit right next to
set 2's RX band; it stops ROTOR_AUTO_TX_CLEARANCE_MM inside the TX1 ring (the reference dual boards stop their
1x target about 1.4 mm inside its own RX band).  Ring 1 is a half moon when LOOPS of set 1 is 1: any of its
field that reaches the RX2 band modulates the fine signal once per turn, so its outer radius must stay
ROTOR_1_TO_RX2_MM (Dual_Board_Parameters.py) inside set 2's RX copper; the generator warns when it does not.
Covering TX1 would gain a few percent of coarse signal (the IPS2550's AGC does not need it) and put that half
moon about half a millimetre from the fine band.

Units: millimetres, degrees.  Nothing in this file is computed - edit values only.
"""

# ---- ROTOR_MODE = "according_to_stator" (Dual_Board_Parameters.py): LOOPS of set 1 sectors ----------------
ROTOR_AUTO_DUTY             = 0.5   # metal fraction of each period (0.5 = 180 deg electrical)
ROTOR_AUTO_START_ANGLE_DEG  = 0.0   # angle of the first sector edge, measured from set 1's RX pattern zero
                                    # (the generator adds the angle the set was turned by, so that both rings
                                    # start at their own set's zero; the record file prints both).  Keep this
                                    # and ring 2's value equal: both tracks then read 0 at the same shaft angle
                                    # (no nominal shift between coarse and fine), which is what the coarse-to-
                                    # fine decision needs; the firmware calibrates the residual.
ROTOR_AUTO_EXTENSION_MM       = None  # past the RX band, both edges.  None = AIR_GAP_MM
ROTOR_AUTO_EXTENSION_INNER_MM = None  # inner edge only.  None = ROTOR_AUTO_EXTENSION_MM
ROTOR_AUTO_EXTENSION_OUTER_MM = 0.0   # outer edge only.  None = ROTOR_AUTO_EXTENSION_MM.  0 = the ring ends at
                                      # the RX1 band end; it never goes past ROTOR_AUTO_TX_CLEARANCE_MM inside TX1
ROTOR_AUTO_TX_CLEARANCE_MM  = 0.1   # copper stays this far inside the TX1 ring
ROTOR_AUTO_COPPER_LAYERS    = ["F.Cu"]   # layer(s) carrying this ring's sectors; mount the copper side towards
                                         # the stator

# ---- ROTOR_MODE = "custom" -----------------------------------------------------------------------------------
ROTOR_CUSTOM_SECTORS            = 1
ROTOR_CUSTOM_DUTY               = 0.5
ROTOR_CUSTOM_START_ANGLE_DEG    = 0.0
ROTOR_CUSTOM_INNER_RADIUS_MM    = 9.0
ROTOR_CUSTOM_OUTER_RADIUS_MM    = 16.0
ROTOR_CUSTOM_COPPER_LAYERS      = ["F.Cu"]
