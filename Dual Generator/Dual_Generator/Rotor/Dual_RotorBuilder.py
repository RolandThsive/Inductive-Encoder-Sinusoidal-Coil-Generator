"""
Dual_RotorBuilder.py  -  the rotor disc of a dual board: two rings of metal sectors, each a Single Generator rotor
(RotorBuilder.RotorDesign) built from its own set, on one disc with one bore and one outline.

    rotor1 = build_ring(P1, stator1, zero)   the Single Generator's rotor for set 1 (ring 1)
    rotor2 = build_ring(P2, stator2, zero)   zero = ROTOR_START_ANGLE_ZERO (Dual_Board_Parameters.py)
    disc = assemble(P, dual_stator, rotor1, rotor2)
    disc.write(path)                         one KiCad file: both rings, their mask openings, bore and outline

Each ring's start angle (ROTOR_AUTO_START_ANGLE_DEG / ROTOR_CUSTOM_START_ANGLE_DEG) is measured from where
ROTOR_START_ANGLE_ZERO says: "rx_zero" = its own set's RX pattern zero (build_ring adds the angle the set was turned
by, so that at disc angle 0 both sets read the same electrical phase), "board" = the board's +x axis, as the Single
Generator measures it.  The record file prints both zeros.

The Single Generator's RotorDesign.write makes a file of its own, so the disc writes the copper itself from the
rings' public geometry (sector_polygon, mask_polygon, layers, mask_layers), with the same lines
RotorDesign.write uses.  Nothing to edit here.
"""

from Generator.Core.KiCadWriter import KiCadBoard, page_size
from Generator.Rotor import RotorBuilder as RB


ZERO_CHOICES = ("rx_zero", "board")


def build_ring(Pk, stator, zero="rx_zero"):
    """The Single Generator's rotor for one set, its start angle measured from the set's RX pattern zero
    (zero = "rx_zero") or from the board's +x axis (zero = "board")."""
    zero = str(zero).strip().lower()
    if zero not in ZERO_CHOICES:
        raise ValueError(f"ROTOR_START_ANGLE_ZERO = {zero!r}: must be one of {', '.join(repr(z) for z in ZERO_CHOICES)}")
    turn = float(stator.rotation_deg) if zero == "rx_zero" else 0.0
    Pk.ROTOR_AUTO_START_ANGLE_DEG = float(Pk.ROTOR_AUTO_START_ANGLE_DEG) + turn
    Pk.ROTOR_CUSTOM_START_ANGLE_DEG = float(Pk.ROTOR_CUSTOM_START_ANGLE_DEG) + turn
    ring = RB.RotorDesign(Pk, stator=stator)
    ring.zero_deg = turn                                   # what was added to the start angle
    ring.set_zero_deg = float(stator.rotation_deg)         # where the set's RX pattern zero is on the board
    ring.zero_from = zero
    return ring


def assemble(P, dual_stator, rotor1, rotor2):
    return DualRotor(P, dual_stator, rotor1, rotor2)


class DualRotor:
    """The finished rotor disc: the two rings and the one bore and outline."""

    def __init__(self, P, dual_stator, rotor1, rotor2):
        self.P = P
        self.rings = (rotor1, rotor2)
        self.cx, self.cy = rotor1.cx, rotor1.cy
        B = P.BOARD
        self.mode = str(B.ROTOR_MODE).lower()
        if self.mode == "custom":
            self.bore, self.outline = B.ROTOR_CUSTOM_BORE_RADIUS_MM, B.ROTOR_CUSTOM_OUTLINE_RADIUS_MM
        else:
            self.bore, self.outline = dual_stator.bore, dual_stator.outline
        self.gap = rotor2.r_in - rotor1.r_out

    def page_size(self):
        B = self.P.BOARD
        r = max(x for x in [self.outline] + [rg.r_out + max(0.0, rg.mask_expansion or 0.0) for rg in self.rings]
                if x is not None)
        return page_size(B, self.cx, self.cy, r)

    def write(self, path):
        """Write the disc to `path` (Dual_RunCoilGenerator.py chooses it: Dual_OutputFolders.py)."""
        B = self.P.BOARD
        if not path:
            raise ValueError("DualRotor.write needs the file path; boards are written by Dual_RunCoilGenerator.py")
        f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
        words = {"F.Cu": "Top", "B.Cu": "Bottom"}
        r1, r2 = self.rings
        comments = ["Generator: Dual_RotorBuilder.py (each ring built by the Single Generator's RotorBuilder.py)"]
        for k, rg in ((1, r1), (2, r2)):
            comments.append(f"Ring {k}: Sectors: {rg.sectors}, Metal Fraction: {rg.duty:.4g}, Radius: {f(rg.r_in)} ... "
                            f"{f(rg.r_out)} mm, Layer: {' + '.join(words.get(l, l) for l in rg.layers)}")
        comments.append(", ".join(x for x in (
            f"Radius-Outer: {f(self.outline)} mm" if self.outline is not None else "",
            f"Radius-Inner: {f(self.bore)} mm" if self.bore is not None else "",
            f"Gap between the rings: {f(self.gap)} mm") if x))
        thickness = getattr(B, "ROTOR_PCB_THICKNESS_MM", None)
        if thickness is None:
            thickness = B.PCB_THICKNESS_MM
        board = KiCadBoard(title=f"Dual rotor {r1.sectors} + {r2.sectors} sectors", comments=comments,
                           page=self.page_size(), thickness=thickness)
        for rg in self.rings:                      # (the same lines as the Single Generator's RotorDesign.write)
            for layer in rg.layers:
                for k in range(rg.sectors):
                    board.polygon(rg.sector_polygon(k), layer)
            if rg.mask_expansion is not None:
                for layer in rg.layers:
                    for k in range(rg.sectors):
                        board.polygon(rg.mask_polygon(k), RB.MASK_LAYER[layer])
        if self.bore is not None:
            board.circle((self.cx, self.cy), self.bore, "Edge.Cuts", B.EDGE_LINE_WIDTH_MM)
        if self.outline is not None:
            board.circle((self.cx, self.cy), self.outline, "Edge.Cuts", B.EDGE_LINE_WIDTH_MM)
        board.save(path)
        return path

    def summary(self):
        lines = [f"Dual rotor ({self.mode}): ring 1 {self.rings[0].sectors} sector(s), ring 2 {self.rings[1].sectors} "
                 f"sector(s); bore r = {self.bore}, outline r = {self.outline}; {self.gap:.2f} mm bare between the rings"]
        if all(getattr(rg, "zero_from", "rx_zero") == "rx_zero" for rg in self.rings):
            lines.append("  both rings start at their own set's RX pattern zero (ROTOR_START_ANGLE_ZERO = \"rx_zero\"), so "
                         "the coarse and the fine track read 0 at the same shaft angle and turn the same way (no "
                         "nominal zero shift: the coarse-to-fine decision tolerates at most +-180/LOOPS of set 2 "
                         "degrees of it); the firmware still has to calibrate the residual at the nominal air gap")
        else:
            z1, z2 = (float(getattr(rg, "set_zero_deg", 0.0)) for rg in self.rings)
            lines.append(f"  both rings start at the board's +x axis (ROTOR_START_ANGLE_ZERO = \"board\"): set 1's RX zero "
                         f"is at {z1:.2f} deg and set 2's at {z2:.2f} deg, so the coarse and the fine track read 0 at "
                         f"different shaft angles unless the start angles in Dual_Rotor1 / Rotor2 allow for it (the "
                         f"coarse-to-fine decision tolerates at most +-180/LOOPS of set 2 degrees of shift)")
        for k, rg in ((1, self.rings[0]), (2, self.rings[1])):
            if getattr(rg, "zero_from", "rx_zero") == "rx_zero":
                lines.append(f"Ring {k}, sector start measured from set {k}'s RX pattern zero ({rg.zero_deg:.2f} deg, "
                             f"ROTOR_START_ANGLE_ZERO = \"rx_zero\"):")
            else:
                lines.append(f"Ring {k}, sector start measured from the board's +x axis (ROTOR_START_ANGLE_ZERO = "
                             f"\"board\"; set {k}'s RX pattern zero is at {float(getattr(rg, 'set_zero_deg', 0.0)):.2f} deg):")
            lines += ["  " + ln for ln in rg.summary().split("\n")]
        return "\n".join(lines)
