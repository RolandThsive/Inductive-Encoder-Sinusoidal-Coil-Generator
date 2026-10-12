"""
OptimizerParameters.py  -  settings of the optional OptimizeCoil.py search.

They change only what the optimizer tries; they never change a board, and RunCoilGenerator.py does
not read this file.  Edit values only.
"""

# =============================================================================
# FINGERS  (RX bridging fingers, RX_TABS in RX_Parameters.py)
# =============================================================================
# False : the optimizer keeps RX_TABS as it is in RX_Parameters.py (every candidate has fingers,
#         or none has).
# True  : every coil layout is tried three times: fingers at every tip (RX_TABS = "all"), one
#         finger per coil next to the TX tail ("single") and no fingers ("none"); the best of each
#         is checked over the full tolerance window and they are compared at the end.  The search
#         takes about three times as long.
COMPARE_FINGERS = False
