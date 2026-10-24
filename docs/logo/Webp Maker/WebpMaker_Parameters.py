"""
WebpMaker_Parameters.py  -  the settings of WebpMaker.py.  Edit the values here, then run:  python WebpMaker.py
"""

# ------------------------------------------------------------ what to turn
SVG_FILE = "../Logo_1_V2.svg"       # the logo; the element with id="rotor" is the part that turns
OUTPUT_FILE = None                  # None: "<SVG_FILE name>_rotor_spin_<WIDTH_PX>px.webp" (or .png) next to the SVG

# ------------------------------------------------------------ format
OUTPUT_FORMAT = "webp"              # "webp" (animated WebP, smallest file) or "apng" (animated PNG, widest support)
WEBP_LOSSLESS = True                # webp only: True keeps every pixel exact; False makes a smaller file
WEBP_QUALITY = 90                   # webp only, used when WEBP_LOSSLESS is False: 1 to 100

# ------------------------------------------------------------ size and speed
WIDTH_PX = 400                      # width (and height) of the image in pixels
ROTATION_DEG_PER_SEC = 30.0         # speed of the rotor in degrees per second; negative turns the other way
FRAMES_PER_SECOND = 10              # frame rate of the animation

# ------------------------------------------------------------ drawing
ROTOR_PIVOT = (250, 250)            # the point the rotor turns about, in SVG units (the centre of the badge)

# ------------------------------------------------------------ rendering
BROWSER = "auto"                    # path of a Chromium / Chrome / Edge program, or "auto" to look for one
WORKERS = 8                         # frames rendered at the same time
