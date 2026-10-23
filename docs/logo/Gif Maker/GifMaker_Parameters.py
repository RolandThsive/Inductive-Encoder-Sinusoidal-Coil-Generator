"""
GifMaker_Parameters.py  -  the settings of GifMaker.py.  Edit the values here, then run:  python GifMaker.py
"""

# ------------------------------------------------------------ what to turn
SVG_FILE = "../Logo_1_V2.svg"        # the logo; the element with id="rotor" is the part that turns
OUTPUT_FILE = None                  # None: "<SVG_FILE name>_rotor_spin_<GIF_WIDTH_PX>px.gif" next to the SVG

# ------------------------------------------------------------ size and speed
GIF_WIDTH_PX = 400                  # width (and height) of the GIF in pixels
ROTATION_DEG_PER_SEC = 30.0         # speed of the rotor in degrees per second; negative turns the other way

# ------------------------------------------------------------ quality
FRAMES_PER_SECOND = 10              # frame rate of the GIF (GIF viewers play 50 fps at most)
GIF_COLORS = 255                    # 2 to 255 colours per frame; fewer colours make a smaller file
EDGE_COLOR = "#1d2733"              # the soft edge of the outline is blended onto this colour (no white halo)
ROTOR_PIVOT = (250, 250)            # the point the rotor turns about, in SVG units (the centre of the badge)

# ------------------------------------------------------------ rendering
BROWSER = "auto"                    # path of a Chromium / Chrome / Edge program, or "auto" to look for one
WORKERS = 6                         # frames rendered at the same time
