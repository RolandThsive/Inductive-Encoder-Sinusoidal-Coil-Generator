# 17. Rotor Features - Dual Generator

The dual rotor is **one disc with two rings of copper sectors**: ring 1 faces set 1 (the inner, coarse set) and ring 2
faces set 2 (the outer, fine set). Each ring is built by the Single Generator's own rotor code from its own file
(`Dual_Rotor1_Parameters.py`, `Dual_Rotor2_Parameters.py`), so the parameters on the [Rotor Features](Rotor-Features.md)
page hold for each ring. The disc itself (`ROTOR_MODE`, its bore and outline, its thickness, the arc resolution and the
solder mask) is set once, in `Dual_Board_Parameters.py`. Mount the copper side towards the stator.

## 17.1 Lobes

With `ROTOR_MODE = "according_to_stator"` (the default) each ring has one copper lobe for every loop of its own set,
and its radial extent comes from that set's RX band and TX ring. With `ROTOR_MODE = "custom"` each ring is drawn from
its own `ROTOR_CUSTOM_*` values (sectors, metal fraction, start angle, inner and outer radius, layers), and the disc's
edges from `ROTOR_CUSTOM_OUTLINE_RADIUS_MM` and `ROTOR_CUSTOM_BORE_RADIUS_MM`.

![Dual Rotor 1: Ring 2 Lobes](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_rotor_1_lobes.png)

*Dual Rotor 1. The default disc (bore radius 7.25 mm, outer radius 26.875 mm) with ring 1 fixed at 1 lobe and ring 2 at
1, 2, 3, 4, 6, 8, 12 and 16 lobes, metal fraction 0.5 in both rings.*

Ring 1 with 1 lobe is a half moon at the default metal fraction of 0.5, so the disc is mechanically unbalanced; at high
speed it needs a non-metal counterweight.

### 17.1.1 Both Rings Start At Their Own Set's Zero

Each stator set is turned on its own so that its TX ends sit at `TERMINAL_1_DEG` or `TERMINAL_2_DEG`, so the two RX
patterns have their zero at different angles. `ROTOR_START_ANGLE_ZERO` says where each ring's start angle
(`ROTOR_AUTO_START_ANGLE_DEG` or `ROTOR_CUSTOM_START_ANGLE_DEG`) is measured from:

| `ROTOR_START_ANGLE_ZERO` | Meaning |
|---|---|
| `"rx_zero"` (default) | From its own set's RX pattern zero: the generator adds the angle the set was turned by, so both rings start at their own set's zero and the coarse and the fine track read 0 at the same shaft angle. This is what the coarse-to-fine decision needs; the firmware calibrates the residual |
| `"board"` | From the board's +x axis, as the Single Generator measures it; the turn of each set is not added. `Parameters.txt` prints each set's zero, so you can add it by hand |

Keep both rings' start angles equal (0 by default): a shift between the coarse and the fine track uses up part of the
±180 / `LOOPS` of set 2 degrees that the coarse-to-fine decision tolerates.

## 17.2 Ring Edges And Metal Fraction

The two rings use the same edge settings as a single rotor, with different defaults, because they do different jobs:

| Setting | Ring 1 (Inner) | Ring 2 (Outer) |
|---|---|---|
| `ROTOR_AUTO_COVER_TX` | `False`: the ring stops inside the TX1 ring | `True`: the ring runs over the TX2 turns, ending `ROTOR_AUTO_TX_OVERHANG_MM` (0.5 mm) past the outermost one |
| `ROTOR_AUTO_EXTENSION_INNER_MM` | `None` = `ROTOR_AUTO_EXTENSION_MM` = `AIR_GAP_MM`, limited by the bore | `0.5`: kept short so ring 2 stays clear of ring 1 |
| `ROTOR_AUTO_EXTENSION_OUTER_MM` | `0.0`: the ring ends at the RX1 band end, never closer than `ROTOR_AUTO_TX_CLEARANCE_MM` (0.1 mm) inside TX1 | `None` (used only when `ROTOR_AUTO_COVER_TX = False`) |
| `ROTOR_AUTO_DUTY` | 0.5 | 0.5 |
| Default ring | r = 7.77 to 11.70 mm | r = 17.50 to 26.32 mm |

`ROTOR_AUTO_EDGE_CLEARANCE_MM` (0.5 mm) keeps both rings' copper away from the disc's bore and outline.

Ring 1 is the dangerous one. A 1-lobe target is a half moon, so any of its field that reaches the RX2 band modulates
the fine signal once per turn: a first-harmonic error that no fine-track calibration removes. That is why ring 1 does
not cover TX1 by default. Covering it would gain a few percent of coarse signal, which the IC's automatic gain control
does not need, and would put the half moon about half a millimetre from the fine band; the generator warns about it.

![Dual Rotor 2: Ring Edges And Metal Fraction](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_rotor_2_edges.png)

*Dual Rotor 2. The default board with 8 outer loops (inner set 1 loop), each picture changing one setting: the
default; ring 1 over its TX ring (`ROTOR_AUTO_COVER_TX = True` in `Dual_Rotor1`, a warning); ring 2 ending inside its TX
ring; ring 2's inner edge 1.5 mm past its band; ring 1 metal fraction 0.25; ring 2 metal fraction 0.4. The stator is
drawn faintly under the rotor copper.*

## 17.3 Distances Between The Rings

Three rules keep each ring's metal away from the other set. All three are set in `Dual_Board_Parameters.py`:

| Parameter | Default | Rule | When Broken |
|---|---|---|---|
| `ROTOR_TRACK_GAP_MM` | 2.0 | Bare ring between ring 1's outer radius and ring 2's inner radius | Error, naming the extension to change |
| `ROTOR_1_TO_RX2_MM` | 3.0 | Least distance from ring 1's outer radius to the innermost RX2 copper | Warning |
| `ROTOR_2_TO_RX1_MM` | 2.0 | Least distance from ring 2's inner radius to the outermost RX1 copper | Warning |

`ROTOR_TRACK_GAP_MM` is a proxy; what matters is how far each ring's metal stays from the other set's RX band. For
copper near a coil the usual layout rule is 3 mm, and 5 mm where the design allows it: copper 0.9 mm from a coil leaves
about 12 % of the RX voltage, copper 2.6 mm away about 45 %. Dual 1x / 16x boards in practice sit at about 3 mm, so use
`ROTOR_1_TO_RX2_MM = 5.0` when the radius allows it. Ring 2 near the coarse band only adds a ripple of `LOOPS` of set 2
per turn, which a 1-loop RX rejects by symmetry, so it may come closer than ring 1 may.

On the default board, measured on the written files: the rings are 5.80 mm apart, ring 1 ends 6.00 mm inside the RX2
copper, and ring 2 starts 5.50 mm outside the RX1 copper. The generator also warns when ring 1 reaches past the TX1 ring
into the gap or over set 2's copper, and when ring 2 reaches in over set 1. The
[Board Features - Dual Generator](Board-Features-Dual-Generator.md#183-the-layout-from-the-centre-out) page shows these
distances on a drawing.

| Previous | Next |
|:---|---:|
| [Stator Features - Dual Generator](Stator-Features-Dual-Generator.md) | [Board Features - Dual Generator](Board-Features-Dual-Generator.md) |
