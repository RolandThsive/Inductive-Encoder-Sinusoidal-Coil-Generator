"""
Dual_TX2_Parameters.py  -  the transmitter (TX) ring of set 2, the outer set, and the IC that drives it and reads
the set.  Dual_TX1_Parameters.py has the same names for set 1.

The names are the Single Generator's own (TX_Parameters.py; RECEIVER_IC and EXCITATION_FREQ_HZ from its
Board_Parameters.py, since a dual board has one IC per set).  Left out on purpose, because a dual board fixes
them (Dual_Fixed_Parameters.py): the TX tail (TX_TAIL_EXTRA_MM = 0: nothing runs out past one pitch outside the
last turn), the shape (TX_SHAPE = "stepped_diagonal": stepped turns only) and the finger settings
(TX_SERIES_UNDERPASS_LAYER, TX_PARALLEL_BREAK_STYLE).  The wiring is chosen here: series or parallel.

Units: millimetres, degrees, hertz.  Nothing in this file is computed - edit values only.
Layers are numbered 1 = Top, 2 = Inner 1, 3 = Inner 2, 4 = Bottom.
"""

# =============================================================================
# THE IC OF THIS SET  (the electrical estimate)
# =============================================================================
RECEIVER_IC         = "IPS2550"     # the IC this set's coils are checked against: "IPS2550", "IPS2200", or None
EXCITATION_FREQ_HZ  = 4.3e6         # TX oscillator frequency aimed for, with the rotor in place (hertz).  Give
                                    # the two sets different frequencies (TX_FREQ_SEPARATION_MIN,
                                    # Dual_Board_Parameters.py).  The generator draws two TX rings; whether both
                                    # ICs drive their own, or one IC drives both tanks in parallel and the other
                                    # has its TX current set to 0 (the Renesas CN317 way, one carrier), is decided
                                    # on the schematic, not here

# =============================================================================
# THE TX RING  (TX_TURNS turns on TX_LAYER_A and TX_TURNS turns on TX_LAYER_B, series or parallel)
# =============================================================================
TX_NET             = "TX_2"

# TX_WIRING = how the turns on the two TX layers are joined (a dual board allows these two, not "single"):
#   "series"   : the turns on TX_LAYER_A and on TX_LAYER_B in series, joined by one via at the inner end
#                (2 x TX_TURNS turns; both terminals leave at the terminal angle, one on each layer)
#   "parallel" : the same turns on both layers in parallel, stitched through vias at the terminal: about
#                6 % more receiver signal and twice the Q in the model, half the inductance; its inner end
#                comes out on an inner tail that ends one pitch outside the last turn (no further)
TX_WIRING          = "series"

TX_TURNS           = 3              # complete turns PER TX LAYER.  The outer ring sits at the board edge
TX_OFFSET_MM       = 1.1            # first turn radius = RX outside radius + this
TX_PITCH_MM        = 0.6            # radial pitch between turns
TX_TRACE_WIDTH_MM  = 0.2
TX_STEPS           = "auto"
TX_CHORD_TOLERANCE_MM = 0.001

# The shape is fixed: "stepped_diagonal" (concentric turns joined by straight steps; Dual_Fixed_Parameters.py).
TX_STEPPED_ANGLE_DEG = 45           # angle of the steps to the turns
TX_INSIDE_VIA_DISTANCE_MM = 0.3    # the via that joins the two TX layers, moved this far inside the first turn
                                    # (at most TX_OFFSET_MM - via radius - half an RX trace - MIN_CLEARANCE_MM)

# The two TX layers (they must differ).  The wiki's Recommended Combination: TX on Top + Inner 2, RX on
# Top + Inner 1.  Both sets may use the same layers.
TX_LAYER_A = 1
TX_LAYER_B = 3
