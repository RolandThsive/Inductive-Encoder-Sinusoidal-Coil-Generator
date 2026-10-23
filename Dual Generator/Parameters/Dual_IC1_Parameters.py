"""
Dual_IC1_Parameters.py  -  the IC of set 1, the inner (coarse) set: the receiver IC that drives this set's TX ring
and reads its RX coils.  Dual_IC2_Parameters.py has the same names for set 2.

The names are the Single Generator's own (IC_Parameters.py), one file per set because a dual board has one IC per
set (the two may be the same type or different ones).  The electrical estimate (TX_Electrics.py, printed by
Dual_RunCoilGenerator.py for each set and written into Parameters.txt) checks this set's TX tank against these
limits.  They never change a board.  Take them from the datasheet of your IC (check your revision) and keep a
margin: the estimate is a model, not a measurement.

Units: as the names say.  Nothing in this file is computed - edit values only.
"""

# =============================================================================
# RECEIVER IC OF SET 1  (defaults: the IPS2550, from its datasheet)
# =============================================================================
IC_NAME            = "IPS2550"  # shown in the electrical estimate; any text, or None ("the receiver IC")
IC_OSC_MIN_MHZ     = 2.0        # lowest LC oscillator frequency (MHz)                 IPS2550: f_LC min 2.0
IC_OSC_MAX_MHZ     = 5.6        # highest LC oscillator frequency (MHz)                IPS2550: f_LC max 5.6
IC_MIN_RP_OHM      = 250        # smallest parallel (loss) resistance of the TX tank   IPS2550: R_Peq 250
                                # that the oscillator can drive (ohm): R_Peq = L / (C x R_series)
IC_SPLIT_TANK_CAPS = True       # True: the tank capacitance C goes in two halves, 2 C from TX1 and 2 C from
                                # TX2 to ground (IPS2550: recommended for EMC); False: one C across the coil
# Set IC_OSC_MIN_MHZ and IC_OSC_MAX_MHZ to None to skip the frequency check, IC_MIN_RP_OHM to None to skip the
# resistance check; with all three None there are no IC checks.
