"""
IC_Parameters.py  -  the receiver IC the TX coil is checked against.

The electrical estimate (TX_Electrics.py, printed by RunCoilGenerator.py and written into Parameters.txt) checks
the TX tank against these limits.  They never change a board.  Take them from the datasheet of your IC (check
your revision) and keep a margin: the estimate is a model, not a measurement.

Units: as the names say.  Nothing in this file is computed - edit values only.
"""

# =============================================================================
# RECEIVER IC  (defaults: IPS2550, datasheet of June 20, 2022)
# =============================================================================
IC_NAME         = "IPS2550"   # shown in the electrical estimate; any text, or None ("the receiver IC")
IC_OSC_MIN_MHZ  = 2.0         # lowest LC oscillator frequency (MHz)                  IPS2550: f_LC min 2.0
IC_OSC_MAX_MHZ  = 5.6         # highest LC oscillator frequency (MHz)                 IPS2550: f_LC max 5.6
IC_MIN_RP_OHM   = 250         # smallest parallel (loss) resistance of the TX tank    IPS2550: R_Peq 250
                              # that the oscillator can drive (ohm): R_Peq = L / (C x R_series)
# Set IC_OSC_MIN_MHZ and IC_OSC_MAX_MHZ to None to skip the frequency check, IC_MIN_RP_OHM to None to skip the
# resistance check; with all three None there are no IC checks.
#
# The tank capacitance goes in two halves, as these ICs take it: 2 C from TX1 and 2 C from TX2 to ground
# (the estimate prints 2 x C).
