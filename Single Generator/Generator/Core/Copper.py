"""
Copper.py  -  the records every builder writes and every check reads: a track segment and a via.  A field that a
record does not use is None (an RX segment has no turn, a TX segment no net: the TX net is TX_NET).
Nothing to edit here.
"""

from typing import NamedTuple, Optional


class Segment(NamedTuple):
    """One straight piece of track from a to b on `layer`."""
    a: tuple                      # (x, y) mm
    b: tuple                      # (x, y) mm
    layer: str                    # "F.Cu", "In1.Cu", "In2.Cu", "B.Cu"
    net: Optional[str] = None     # RX: the coil's net name
    curve: Optional[int] = None   # RX: index of the receiver curve (phase / sub-coil) it belongs to
    turn: Optional[int] = None    # TX: the turn id (-1 for the tails, steps and terminal pieces)
    kind: Optional[str] = None    # TX: turn | arc | step | stub | bracket | tail | terminal


class Via(NamedTuple):
    """A via at `at`.  `layers` names the two copper layers it joins (the layers of the traces that meet there),
    top-most first; the writer uses the pair only for a blind via (VIA_TYPE), a through via always spans the board."""
    at: tuple                     # (x, y) mm
    net: Optional[str] = None     # RX: the coil's net name
    curve: Optional[int] = None   # RX: the receiver curve
    node: Optional[int] = None    # RX: the polyline node it sits on
    turn: Optional[int] = None    # TX: the turn it belongs to
    layers: Optional[tuple] = None  # ("F.Cu", "In1.Cu") ... the two layers joined; None = not recorded
