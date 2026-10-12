"""
Rotor_Parameters.py  -  the rotor (the metal "target") made by RotorGenerator.py.

Units: millimetres, degrees.  Nothing in this file is computed - edit values only.
"""

# "according_to_stator" : everything below ROTOR_AUTO_* is applied on top of
#                         the stator settings (sector count = LOOPS, radial
#                         extent from the RX band and the TX ring, ...).
# "custom"              : only the ROTOR_CUSTOM_* values are used.
ROTOR_MODE = "according_to_stator"

# ---- according_to_stator ----------------------------------------------------
ROTOR_AUTO_DUTY             = 0.5   # metal fraction of each period (0.5 = 180 deg electrical).  A
                                    # copper pattern of fraction k/h has no h-th harmonic (1/3: no
                                    # 3rd), but the field it leaves has: the eddy currents crowd the
                                    # field at the copper edges, which moves the fraction that removes
                                    # the 3rd harmonic of the field above 1/3 and changes the signal.
                                    # OptimizeCoil.py finds the best value for your coil with the
                                    # eddy-current model; check it on a test rotor.
ROTOR_AUTO_START_ANGLE_DEG  = 0.0   # mechanical angle of the first sector edge

# ---- outer edge of the copper: over the TX turns (default) -----------------
# True: the copper runs over the TX turns and ends ROTOR_AUTO_TX_OVERHANG_MM past the outer edge
# of the outermost TX turn, as in the Renesas reference designs.  Every sector is a shorted turn
# driven by the TX flux it encloses, and that flux is densest right beside the TX conductors: in
# the eddy-current model (AnalyzeCoil.py) that gives 5-8 % more receiver signal than ending the
# copper inside the TX ring; most of the gain is reached 0.5 mm past the outer turn.  Whether it
# also lowers the angle error depends on the coil (in the model it does for 1 loop and not for
# 16), so OptimizeCoil.py searches the outer edge together with the metal fraction.
# False: the older rule (ROTOR_AUTO_EXTENSION_OUTER_MM, ROTOR_AUTO_TX_CLEARANCE_MM below).
ROTOR_AUTO_COVER_TX         = True
ROTOR_AUTO_TX_OVERHANG_MM   = 0.5   # mm past the outer edge of the outermost TX turn (negative = ends
                                    # over the TX turns).  The copper always stays
                                    # ROTOR_AUTO_EDGE_CLEARANCE_MM inside the board outline.

# How far the rotor copper reaches past the RX band, in mm: positive = past the band,
# negative = stops short of it.  None = not set (see each line).  The copper always stays
# ROTOR_AUTO_EDGE_CLEARANCE_MM away from the bore (and, with ROTOR_AUTO_COVER_TX = False,
# ROTOR_AUTO_TX_CLEARANCE_MM inside the TX ring); a value that does not fit is cut back to
# that limit and reported.
ROTOR_AUTO_EXTENSION_MM       = None  # both edges (the outer one only with ROTOR_AUTO_COVER_TX = False).
                                      # None = AIR_GAP_MM
ROTOR_AUTO_EXTENSION_INNER_MM = None  # inner edge only.  None = ROTOR_AUTO_EXTENSION_MM.
                                      # Not critical; the bore limits it.
ROTOR_AUTO_EXTENSION_OUTER_MM = None  # outer edge only, used only with ROTOR_AUTO_COVER_TX = False.
                                      # None = ROTOR_AUTO_EXTENSION_MM.  (The older advice to end the
                                      # copper at the RX band came from the simpler "ideal screen"
                                      # model, which cannot judge copper edges or copper over the TX.)

ROTOR_AUTO_TX_CLEARANCE_MM  = 0.1   # ROTOR_AUTO_COVER_TX = False only: copper stays this far inside the TX ring
ROTOR_AUTO_EDGE_CLEARANCE_MM = 0.5  # rotor copper stays this far from the bore edge and from the outline
ROTOR_AUTO_COPPER_LAYERS    = ["F.Cu"]   # layer(s) carrying the metal sectors;
                                         # mount the copper side towards the stator

# ---- custom -----------------------------------------------------------------
ROTOR_CUSTOM_SECTORS            = 1
ROTOR_CUSTOM_DUTY               = 0.5
ROTOR_CUSTOM_START_ANGLE_DEG    = 0.0
ROTOR_CUSTOM_INNER_RADIUS_MM    = 37.1
ROTOR_CUSTOM_OUTER_RADIUS_MM    = 51.9
ROTOR_CUSTOM_COPPER_LAYERS      = ["F.Cu"]
ROTOR_CUSTOM_OUTLINE_RADIUS_MM  = 55.0   # outer board edge (None = no outline)
ROTOR_CUSTOM_BORE_RADIUS_MM     = 36.8   # centre hole (None = no hole)

# ---- both modes -------------------------------------------------------------
ROTOR_ARC_STEPS_PER_SECTOR = 48     # polygon points on every circular arc

# Solder mask expansion ("SolderMaskExpansion") over the rotor copper; the same for every copper
# layer of the rotor, in both modes:
#   0.05  the solder mask is removed over the copper: the opening is 0.05 mm wider than the copper
#         on every side (any value above 0 works the same way, with that margin)
#   0     the opening is exactly the copper outline
#   -1    no opening: the solder mask stays over the copper
# No other negative value is accepted.  The openings are drawn on F.Mask / B.Mask (a shape on a
# mask layer is an opening in KiCad), so they are part of the rotor file.
ROTOR_SOLDER_MASK_EXPANSION_MM = 0.05
