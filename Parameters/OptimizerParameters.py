"""
OptimizerParameters.py  -  every setting of the optional OptimizeCoil.py search.

OptimizeCoil.py has no command-line options: it does exactly what this file says.  The settings change
only what the optimizer tries; they never change a board, and RunCoilGenerator.py does not read this
file.  Edit values only.  (A line that is missing here means the value written next to it.)
"""

# =============================================================================
# WHAT IS SEARCHED
# =============================================================================
# RX coil shapes tried: any of "equal_area", "cosine_r", "field_compensated".
PROFILES = ("equal_area", "cosine_r", "field_compensated")

# Sub-coil counts tried (1, 2 or 3; 3 is crowded) and, for 2 or more, the splits tried (electrical degrees).
SUBCOIL_COUNTS = (1, 2)
SUBCOIL_SPLITS_DEG = (36.0, 40.0, 45.0, 50.0, 55.0, 60.0)

# Rotor metal fraction searched: (lowest, highest), both between 0 and 1.
DUTY_RANGE = (0.25, 0.50)

# True : the rotor's outer edge is searched too (from the RX band, over the TX turns, to the board outline).
# False: it stays as in Rotor_Parameters.py.   (Not searched when ROTOR_MODE is "custom".)
SEARCH_ROTOR_OUTER_EDGE = True

# ROTOR_MODEL = "screen" only: where the rotor copper may end, mm past the outer radius of the RX band.
OUTER_RANGE_MM = (-0.2, 0.5)

# True: every coil layout is tried three times: fingers at every tip (RX_TABS = "all"), one finger per coil
#       next to the TX tail ("single") and no fingers ("none"); the best of each is checked over the full
#       tolerance window and they are compared at the end.  The search takes about three times as long.
# False: RX_TABS stays as in RX_Parameters.py.
COMPARE_FINGERS = False

# =============================================================================
# HOW CANDIDATES ARE JUDGED
# =============================================================================
# Tolerances every candidate must stay good within (0 = skip that one).
GAP_TOLERANCE_MM = 0.2        # air gap  +/-
DUTY_TOLERANCE = 0.005        # rotor metal fraction  +/-  (etching)
OUTER_TOLERANCE_MM = 0.05     # rotor outer edge  +/-  (registration; ROTOR_MODEL = "screen" only)

# Rotor off-centre and tilted (checked for the finalists, together, in the worst direction).
# Both 0 = air gap and metal fraction tolerances only (a much faster run).
ECCENTRICITY_MM = 0.2         # rotor axis offset from the stator axis
TILT_DEG = 0.3                # rotor plane tilt
ECC_DIRECTIONS = 3            # eccentricity directions tried (over one loop pitch)

# Smallest allowed signal, as a fraction of your current design's signal (less signal = more noise).
MIN_SIGNAL = 0.8

# Candidates that the generator warns about (a via too close to copper ...) are shown but not recommended.
# True: they may be recommended.
ALLOW_WARNINGS = False

# How many candidates of the first stage are re-checked over the full tolerance window.
FINALISTS = 6

# =============================================================================
# THE MODEL
# =============================================================================
# "eddy"  : eddy currents in the rotor copper (RotorEddyModel.py); slower, sees copper over the TX turns.
# "screen": the older ideal-screen model; much faster.
ROTOR_MODEL = "eddy"

# True: every receiver trace at the depth of its real layer, the TX from its real copper (RealCopper.py).
# False: the older model (TX as rings, receiver copper half on each RX layer).
TRUE_3D_GEOMETRY = True

# ROTOR_MODEL = "screen" only: True = perfectly sharp rotor edges (no smoothing across the air gap).
SCREEN_SHARP_EDGES = False

# Worker processes: 0 = automatic (at most 4).
JOBS = 0

# =============================================================================
# RX BASE AND AMPLITUDE FINDER  (RX_R_BASE_MM and RX_A_MM)
# =============================================================================
# Works only when you give the board edges and nothing else for the RX band: INSIDE_RADIUS_MM,
# OUTSIDE_RADIUS_MM, RX_R_BASE_MM and RX_A_MM all None (RX_Parameters.py).  Everything above is optimized
# first, with the widest band the board and your TX coil leave.  Then, for the best BAND_BOARDS boards found
# AND for your current layout, the finder looks for the best RX_R_BASE_MM and RX_A_MM (the band's centre and
# half-width), keeping the TX coil you chose.
RX_BASE_AND_AMPLITUDE_FINDER = True

# The narrowest band tried, as a percentage of the widest band (more than 0, at most 100).
# 70 = bands from 100 % down to 70 % of the widest band.  100 = only the widest band.
BAND_WIDTH_LIMIT_PERCENT = 70.0

# The step of the search, in percent (1 ... 100): bands are tried in steps of this many percent of the width,
# and a narrower band is moved across the free space in steps of this many percent.  1 = finest.
# Fine steps take longer: the search starts coarse and refines around the best band.
BAND_STEP_PERCENT = 10.0

# How many of the best boards (besides your current layout) get the finder.
BAND_BOARDS = 3
