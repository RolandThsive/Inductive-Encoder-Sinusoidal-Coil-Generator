"""
SilkScreenSuggestion_Parameters.py  -  the silkscreen suggestion for cutting the leads: where to break each RX
coil and where the two ends of the TX coil get their vias.

The generator's coils have no terminals: every RX coil (SIN and COS) is one closed loop, and the two ends of the
TX coil lie on top of each other at the end of its tail (one on each of its two layers).  The user breaks each
RX loop at one place and sets a via at each side of the cut, and extends each TX end to a via of its own, then
routes from those vias to the IC.  This last step of the generation (LeadCutting_SilkscreenSuggestion.py, run
after the stator file is written) looks for a spot on each coil
where the vias have room on every layer and draws the suggestion on the silkscreen of the finished stator file:

    RX coil   a dashed box around the break, a dot at each of the two via sites, the name of each lead
              (SIN_1, SIN_2, COS_1, COS_2)
    TX coil   a dot at each of the two via sites beside the stacked end, a dashed line from the end to each site,
              the name of each lead with its layer (TX_1 TOP, TX_2 BOT, ...)

It changes no copper: the marks are drawings on F.SilkS and B.SilkS (the bottom text mirrored), and the
coordinates are printed in the run and appended to Parameters.txt.  Nothing in this file changes a coil.

Units: mm unless the name says otherwise.  Nothing in this file is computed - edit values only.
"""

# =============================================================================
# THE SUGGESTION
# =============================================================================
SILKSCREEN_SUGGESTION = True        # False: the stator file is left as the assembler wrote it (no silkscreen)
SILKSCREEN_SIDES      = "both"      # "both": F.SilkS and B.SilkS;  "top": F.SilkS only;  "bottom": B.SilkS only

# Colour of every mark (lines, boxes, dots and the lettering), as a hex RGB string ("#RRGGBB").  KiCad keeps a
# colour per graphic item (it is written into each item's stroke); the fab prints the silkscreen in its own ink
# regardless.
SILKSCREEN_COLOR      = "#FFFFFF"

SILKSCREEN_LABELS     = True        # True: write the lead names (SIN_1, SIN_2, TX_1, TX_2, ...) next to the via sites
SILKSCREEN_DOT_ON_ALL_VIAS = False  # True: also a dot on every via the generator placed (both sides);  False: only
                                    # the via sites of the suggestion

# =============================================================================
# GEOMETRY OF THE MARKS
# =============================================================================
SILKSCREEN_LINE_WIDTH_MM  = 0.12    # line width of the boxes, lines and dot outlines
# The lead names are drawn with the repository's own stroke font (resources/SilkscreenFont.py at the root of the
# repository: capitals, digits, a few signs; no KiCad font), as lines on the silkscreen, each name placed where it
# covers no other mark, name or via.
SILKSCREEN_TEXT_SIZE_MM   = 0.5     # height of a capital (mm); a glyph is 2/3 as wide, the letter pitch 5/6 of the height
SILKSCREEN_TEXT_STROKE_MM = 0.1     # line width of the lettering.  Most fabs print silkscreen lines down to about
                                    # 0.1 ... 0.15 mm and text down to about 0.8 mm height; smaller may come out unreadable
SILKSCREEN_DOT_RADIUS_MM  = 0.16    # radius of the filled dot at a via site
SILKSCREEN_BOX_MARGIN_MM  = 0.5     # the dashed box around an RX break reaches this far past the two via sites

# =============================================================================
# WHERE THE BREAK GOES  (the search; the result is printed in the run and in Parameters.txt)
# =============================================================================
# The two vias of an RX break sit on the coil this far apart (centre to centre, along the trace); the trace between
# them is what the user cuts.  At least VIA_DIAMETER_MM + MIN_CLEARANCE_MM.
SILKSCREEN_BREAK_VIA_GAP_MM   = 1.2
# The break is looked for on the coil's traces within this many degrees of the TX terminal (the board is turned
# so that it sits at 0 deg, the right), where the TX ends are, so that all leads come together.  Larger = more candidates, further from the TX ends.
SILKSCREEN_SEARCH_SPAN_DEG    = 30.0
# The two breaks and the TX end stay at least this far apart (centre to centre), so that the marks and
# the lead names do not land on each other.
SILKSCREEN_BREAK_SEPARATION_MM = 4.0
# The coil layers tried for the break, in this order; the first layer with a spot that has room is used.
SILKSCREEN_BREAK_LAYERS       = ["F.Cu", "B.Cu"]
# A via of the suggestion keeps MIN_CLEARANCE_MM (Board_Parameters.py) from every copper on every layer, and
# this much from the bore and the outline.
SILKSCREEN_VIA_EDGE_CLEARANCE_MM = 0.25
# The two via sites of a TX end are looked for up to this far from the stacked end (mm).
SILKSCREEN_TX_SITE_REACH_MM   = 2.0
