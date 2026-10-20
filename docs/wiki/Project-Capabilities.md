# 5. Project Capabilities

| Area | Capability |
|---|---|
| Human Language | English |
| Programming Language | Pure Python 3 with numpy |
| Output | Stator and rotor as `.kicad_pcb` files, plus a full record of every value used |
| RX Loops | 1 to 16 electrical periods per mechanical turn |
| RX Phases | Four phases only: SIN and COS pairs, each with a positive and a negative half |
| RX Profiles | `equal_area`, `cosine_r` (limaçon); a field-compensated profile is research underway |
| RX Sub-Coils | 1 to 3 per coil, mainly for miniature 1-loop coils |
| RX Fingers | Bridging fingers to break the coils out across the TX ring: all, single or none |
| TX Layers | Any one layer, or any two layers (Top and Bottom on a 2-layer board) |
| TX Wiring | Single (one layer), series or parallel (`TX_WIRING`) |
| TX Shape | Stepped diagonal turns (adjustable step angle), stepped arc turns (adjustable arc radius) or spiral turns |
| TX Break Style | Go-around (staggered) or stitched windows where a finger crosses the TX ring |
| TX Terminal | Placed automatically where it keeps the largest gap from the RX copper (with `RX_TABS = "single"`, as close to the two fingers as the clearance allows); the board is turned so it sits at 0° |
| Rotor | Generated from the stator, or fully custom |
| Board | 2 or 4 copper layers, through vias only, fixed or automatic board edges |
| Checks | Parameter rules, finished-geometry rules and the generator's own TX self-clearance check, with named conflicts; `GENERATOR_MODE` `normal` or `strict` |
| Electrical Estimate | TX inductance, resistance, Q, tank capacitors, oscillator frequency and tank resistance against the IC limits in `IC_Parameters.py` (no receiver voltage) |
| Analysis | Under construction on the `analyser_and_optimizer` branch: angle error, signal, harmonics and a tolerance window (air gap, eccentricity, tilt, etching) |
| Optimization | Under construction on the `analyser_and_optimizer` branch: searches profile, sub-coils, split, rotor metal fraction and rotor outer edge |

Most of these are shown with pictures on the [Stator Features](Stator-Features.md), [Rotor Features](Rotor-Features.md) and [Board Features](Board-Features.md) pages.

## 5.1 Board Size Range

The table below gives the board sizes that build without any error or warning for 1, 4 and 16
loops. It was found by running the generator's own checks (parameters, finished boards, rotor and
electrical estimate) over a grid of board radii in 1 mm steps, up to an outer radius of 40 mm, with
these settings: 4 layers, series TX on Top + Inner-1 with 3 turns per layer, 0.6 mm pitch, 0.2 mm
traces, 0.8 / 0.4 mm vias, 0.2 mm clearance, the default IC limits, fixed board edges (the RX band is
fitted between them) and `RX_TAB_LENGTH_MM = 5` (this TX needs fingers of at least 4.94 mm).

| Loops | Smallest Outer Radius, One Finger Per Coil (`RX_TABS = "single"`) | Bore Radius On That Board | Bore Radius Range On Larger Boards | Smallest Outer Radius, Fingers On Every Tip (`RX_TABS = "all"`, the default) | What Limits It |
|---|---|---|---|---|---|
| 1 | 12 mm | 1–2 mm | 1 mm up to (outer radius − 10 mm) | 12 mm | RX band width |
| 4 | 13 mm | 2 mm | 2 mm up to (outer radius − 10 mm) | 30 mm | RX band width and tip vias; with fingers on every tip, a TX window under a finger would reach the TX terminal on smaller boards |
| 16 | 26 mm | 12 mm | 12 mm up to 14 mm on a 27 mm board, up to (outer radius − 11 mm) on boards of 28 to 33 mm, and up to (outer radius − 10 mm) from 34 mm | none up to 40 mm | Tip vias crowd at small bore radii: a quarter loop needs at least 1.2 mm of arc at the RX inner edge |

All radii are board edges (`INNER_EDGE_RADIUS_MM`, `OUTER_EDGE_RADIUS_MM`). Most boards in the
pictures of this wiki have board edges of 30 and 50 mm. Smaller vias, fewer TX turns or
a finer pitch make smaller boards possible.

There is no upper limit in the generator itself. A larger board gives a wider RX band and a
stronger signal.

| Previous | Next |
|:---|---:|
| [Web Tool](Web-Tool.md) | [Examples](Examples.md) |
