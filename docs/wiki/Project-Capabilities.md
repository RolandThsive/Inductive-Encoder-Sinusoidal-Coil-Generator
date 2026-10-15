# 1. Project Capabilities

| Area | Capability |
|---|---|
| Human Language | English |
| Programming Language | Pure Python 3 with numpy (matplotlib optional, for plots) |
| Output | Stator and rotor as `.kicad_pcb` files, plus a full record of every value used |
| RX Loops | 1 to 16 electrical periods per mechanical turn |
| RX Phases | Four phases only: SIN and COS pairs, each with a positive and a negative half |
| RX Profiles | `equal_area`, `cosine_r` (limaçon, as in the Renesas reference design), `field_compensated` |
| RX Sub-Coils | 1 to 3 per coil, mainly for miniature 1-loop coils |
| RX Fingers | Bridging fingers to break the coils out across the TX ring: all, single or none |
| TX Layers | Any one layer, or any two layers of a 4-layer board |
| TX Wiring | Series or parallel |
| TX Shape | Stepped or spiral turns, with an adjustable step angle |
| TX Break Style | Go-around (staggered) or stitched windows where a finger crosses the TX ring |
| Rotor | Generated from the stator, or fully custom |
| Board | 2 or 4 copper layers, through vias only, fixed or automatic board edges |
| Checks | Parameter rules, finished-geometry rules and the generator's own TX self-clearance check |
| Electrical Estimate | TX inductance, resistance, Q, tank capacitors, oscillator frequency and RX voltage against the IC limits |
| Analysis | Angle error, signal, harmonics and a tolerance window (air gap, eccentricity, tilt, etching) |
| Optimization | Searches profile, sub-coils, split, rotor metal fraction and rotor outer edge |

Each of these is shown with pictures in the sections below.

## 1.1 Board Size Range

The table below gives the board sizes that build without any error or warning for 1, 4 and 16
loops. It was found by running the generator's own checks over a grid of board radii (1 mm steps)
with the default settings: 4 layers, series TX on Top + Inner-1 with 3 turns per layer, 0.6 mm
pitch, 0.6 / 0.3 mm vias, 0.2 mm clearance and IPS2550 limits.

| Loops | Smallest Outer Radius | Bore Radius On That Board | Bore Radius Range On Larger Boards | What Limits It |
|---|---|---|---|---|
| 1 | 12 mm | 1–3 mm | 1 mm up to (outer radius − 9 mm) | RX band width; on the smallest boards, the IPS2550 tank resistance |
| 4 | 13 mm | 2–3 mm | 2 mm up to (outer radius − 10 mm) | RX band width and tip vias |
| 16 | 26 mm | 12–14 mm | 12 mm up to (outer radius − 10 mm) | Tip vias crowd at small bore radii: a quarter loop needs about 1.3 mm of arc at the RX inner edge |

All radii are board edges (`INNER_EDGE_RADIUS_MM`, `OUTER_EDGE_RADIUS_MM`). The 1- and 4-loop rows
were checked in 1 mm steps and the 16-loop row in 2 mm steps, up to an outer radius of 30 mm; the
largest board built in this README has an outer radius of 56.5 mm. Smaller vias, fewer TX turns or
a finer pitch make smaller boards possible.

There is no upper limit in the generator itself. A larger board gives a wider RX band and a
stronger signal.

| Previous | Next |
|:---|---:|
| [Web Tool](Web-Tool.md) | [Examples](Examples.md) |
