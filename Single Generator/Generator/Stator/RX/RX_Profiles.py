"""
RX_Profiles.py  -  the radius law of the RX curves (RX_PROFILE): how the radius of every receiver curve swings
between the inside and the outside of the RX band with the electrical angle.
    equal_area   r^2 swings as a sine: the flux weight is a pure sine of the angle (equal-area radius law)
    cosine_r     r itself swings as a sine (a limacon)
The function takes the RX builder (`rx`, RX_Builder.py) and sets rx.radius(s), s = sin(electrical angle).
Nothing to edit here.
"""

import numpy as np


def radius_law(rx):
    P = rx.P
    ri2, ro2 = rx.ri ** 2, rx.ro ** 2
    rx._a, rx._b = 0.5 * (ro2 - ri2), 0.5 * (ro2 + ri2)
    if P.RX_PROFILE == "equal_area":
        rx.radius = lambda s: np.sqrt(rx._b + rx._a * np.asarray(s, dtype=float))
        return
    if P.RX_PROFILE == "cosine_r":
        rm, ra = 0.5 * (rx.ro + rx.ri), 0.5 * (rx.ro - rx.ri)
        rx.radius = lambda s: rm + ra * np.asarray(s, dtype=float)
        return
    raise ValueError('RX_PROFILE must be "equal_area" or "cosine_r"')
