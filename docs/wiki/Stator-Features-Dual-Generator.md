# 16. Stator Features - Dual Generator

The Dual Generator puts **two complete coil sets on one stator board**: set 1 inside, set 2 outside, each with its
own RX pair, its own TX ring and its own receiver IC. Set 1 is the coarse, absolute track (1 loop by default) and set
2 the fine track (16 loops by default): the coarse angle says which period of the fine track the rotor is in, and the
fine track gives the resolution.

Each set is built by the Single Generator's own code from its own parameter files (`Dual_RX1` / `Dual_TX1` for set 1,
`Dual_RX2` / `Dual_TX2` for set 2). Everything on the [Stator Features](Stator-Features.md) page therefore holds for
each set, with the rules below that every dual board adds. The Dual Generator places the two sets, turns them, merges
them into one file and checks the gap between them; the Single Generator itself is not changed.

Every picture is drawn from the `.kicad_pcb` files the Dual Generator wrote, with the silkscreen suggestion switched
off (`SILKSCREEN_SUGGESTION = False`). Colours show the copper layer only: Top red, Inner-1 green, Inner-2 dark yellow,
Bottom dark blue. Traces are drawn at their true width. Unless a caption says otherwise the board is the default one:
bore radius 7.25 mm, outer radius 26.875 mm, RX1 band 8.45 to 11.7 mm, RX2 band 18.0 to 23.9 mm, 4 TX turns per layer
in both sets, TX pitch 0.35 mm, traces 0.15 mm, vias 0.6 / 0.3 mm.

## 16.1 What A Dual Board Fixes

A dual board is always built one way. These Single Generator settings are fixed in `Dual_Fixed_Parameters.py`, and the
checker refuses any other value and says why:

| Setting | Fixed Value | Why |
|---|---|---|
| `PCB_LAYERS` | `4` | Each set needs two RX layers and two TX layers; two layers cannot hold two sets without fingers |
| `RX_TABS` | `"none"` | Set 1's bridging fingers would cross set 2's band; both RX rings are plain bands, broken out by hand |
| `TX_SHAPE` | `"stepped_diagonal"` | Stepped turns only: `"spiral"` is not used, and `"stepped_arc"`'s last arc would need a tail |
| `TX_TAIL_EXTRA_MM` | `0` | No tail: the TX ring ends one pitch outside its last turn, so nothing runs out through the other set |
| `RX_RISING_EDGE_LAYER` | `"F.Cu"` | A 2-layer setting, unused on 4 layers |

The finger settings (`RX_TAB_LAYER`, `RX_TAB_LENGTH_MM`, `RX_TAB_WIDTH_MM`, `TX_SERIES_UNDERPASS_LAYER`,
`TX_PARALLEL_BREAK_STYLE`) and `TX_STEPPED_ARC_RADIUS_MM` are listed there too, as unused. `TX_WIRING` is not fixed:
each set chooses `"series"` or `"parallel"`, and `"single"` is a conflict.

## 16.2 RX Coils

Each set has the Single Generator's four-phase RX: a SIN pair and a COS pair, every phase with its rising edges on
`RX_LAYER_A` and its falling edges on `RX_LAYER_B` (by default Top and Inner-1 in both sets). Both sets may use the
same two layers, because their copper never overlaps radially. The six nets must all have different names (the
defaults are `SIN_1`, `COS_1`, `TX_1`, `SIN_2`, `COS_2` and `TX_2`); a name used twice is an error, because KiCad
would join the two coils into one net.

### 16.2.1 Loops

`LOOPS` is set for each set, from 1 to 16. The inner set is the coarse one: with 1 loop it gives a true 0 to 360°
output that tells the outer set's periods apart. The outer set's loops set the resolution. The coarse angle error must
stay below half an outer period, which is 180 / `LOOPS` of set 2 mechanical degrees (±11.25° for 16 loops).

![Dual Stator 1: Outer Set Loops](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_stator_1_loops.png)

*Dual Stator 1. The default board with the inner set fixed at 1 loop and the outer set at 1, 2, 4, 8 and 16 loops
(RX only, the TX is not drawn).*

### 16.2.2 Sub-Coils

`RX_SUBCOILS` (1, 2 or 3) and `RX_SUBCOIL_SPLIT_ELEC_DEG` work for each set as on a single board. They are most useful
on the 1-loop inner set, where the harmonics matter most. Each sub-coil adds junction vias, so the band needs room
for them: on the default inner band (8.45 to 11.7 mm) two sub-coils pass the checker, but the run stops while it
builds set 1 ("RX_SUBCOILS conflicts with RX_SUBCOIL_SPLIT_ELEC_DEG, RX_VIA_ELECTRICAL_DEG and LOOPS", then "set 1: no
crossing of neighbouring sub-coils is clear enough for the via that joins them"). Widen the inner band, or use smaller
vias (0.45 mm builds, 0.5 mm does not).

![Dual Stator 2: RX Sub-Coils](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_stator_2_subcoils.png)

*Dual Stator 2. The inner set with 1 sub-coil and with 2 sub-coils split by 45°. The inner band is widened to 8.45 to
14.0 mm and the outer band moved to 20.0 to 25.9 mm so that the junction vias fit (RX only, the TX is not drawn).*

## 16.3 TX Rings

Each set has its own TX ring, with `TX_TURNS` complete turns on `TX_LAYER_A` and `TX_TURNS` turns on `TX_LAYER_B`
(by default Top and Inner-2, the [Recommended Combination](Quick-Guide-To-Parameters-Selections.md#1541-recommended-combination)).
The first turn sits `TX_OFFSET_MM` outside the set's RX band and each next turn `TX_PITCH_MM` further out. The inner
TX ring sits between the two sets, so every turn and every millimetre of pitch there pushes set 2 outwards.

### 16.3.1 Number Of Turns

More turns raise the inductance and the Q of each tank. With fixed board edges (`DUAL_MODE = 1`) both RX bands shrink
as the TX rings grow. The electrical estimate checks each set's tank against its own IC: with 2 turns per layer at
3 MHz the inner tank falls below the IPS2550's least parallel resistance, and the estimate says so.

![Dual Stator 3: TX Turns](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_stator_3_tx_turns.png)

*Dual Stator 3. 2 to 6 TX turns per layer in both sets (series TX on Top + Inner-2, pitch 0.35 mm, inner set 1 loop,
outer set 16 loops). `DUAL_MODE = 1` keeps the bore (7.25 mm), the outline (30 mm) and the gap between the sets (3 mm)
the same in every picture.*

### 16.3.2 Series Versus Parallel

`TX_WIRING` is chosen for each set:

| `TX_WIRING` | What It Builds |
|---|---|
| `"series"` (default) | The turns on the two TX layers in series, joined by one via at the inner end: 2 × `TX_TURNS` turns. The two ends sit on top of each other one pitch outside the last turn, one on each TX layer |
| `"parallel"` | The same turns on both layers in parallel, stitched through vias at the terminal: `TX_TURNS` turns, not 2 × `TX_TURNS`. In the estimate that is a quarter of the series ring's inductance and about the same Q (set 1 at pitch 0.45 mm: 2.81 µH and Q 10 to 21 in series, 0.70 µH and Q 9 to 19 in parallel). The inner end comes out on an inner tail that ends one pitch outside the last turn, no further |

A parallel ring needs room for its stitching vias between the turns: with the default 0.6 mm vias the checker asks for
a pitch of at least 0.43 mm, so the default pitch of 0.35 mm works only for a series ring.

![Dual Stator 4: TX Series vs Parallel](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_stator_4_tx_series_parallel.png)

*Dual Stator 4. The default board with series TX rings (top row) and parallel TX rings (bottom row), pitch 0.45 mm in
both rows. Left: the whole board. Middle and right: the TX ends of the inner set (at 180°) and of the outer set (at
0°), to scale, in mm from the board centre.*

### 16.3.3 Where Each Set's TX Ends Go

Each set looks for its TX terminal as a single board does, at the place with the largest gap from its own RX copper.
Then, instead of turning the terminal to 0°, each set is turned on its own so that its TX ends sit at its own angle,
`TERMINAL_1_DEG` for set 1 (default 180°, the left) and `TERMINAL_2_DEG` for set 2 (default 0°, the right). The run
prints both, for set 1 on the default board: "TX terminal: found at 135.00 deg of the RX pattern (0.639 mm from the
nearest RX copper); the board is turned by 45.00 deg so that it sits at 180 deg".
Angles run from the +x axis of the page towards +y, down the KiCad page: 0 = right, 90 = bottom, 180 = left, 270 =
top. Different angles keep the two sets' breakouts apart. Each set's RX pattern zero lands wherever its turn puts it;
`Parameters.txt` prints both.

![Dual Stator 5: Where Each Set's TX Ends Go](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_stator_5_terminals.png)

*Dual Stator 5. The default board with 4 outer loops and the TX ends at 180° / 0° (the default), 90° / 270° and
0° / 0°.*

### 16.3.4 Step Angle And Inside Via

The stepped turns are joined by straight steps at `TX_STEPPED_ANGLE_DEG` to the turns (45° by default), as on a single
board. The via that joins the two TX layers of a series ring sits `TX_INSIDE_VIA_DISTANCE_MM` (0.2 mm) inside the
first turn; it may be at most `TX_OFFSET_MM` minus the via radius, half an RX trace and `MIN_CLEARANCE_MM`.

![Dual Stator 6: TX Step Angle](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_stator_6_tx_step_angle.png)

*Dual Stator 6. The outer set's TX ends with step angles of 20°, 30°, 45° (the default) and 90°, to scale (4 turns per
layer, pitch 0.35 mm, trace 0.15 mm). The inner set follows the same rule.*

## 16.4 Related Pages

- [Board Features - Dual Generator](Board-Features-Dual-Generator.md): the layout from the centre out and the checks.
- [Quick Guide To Parameters Selections - Dual Generator](Quick-Guide-To-Parameters-Selections-Dual-Generator.md): the
  four `DUAL_MODE`s.
- [Parameter Reference Dual Generator](Parameter-Reference-Dual-Generator.md): every dual parameter and its default.

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [Quick Guide To Parameters Selections](Quick-Guide-To-Parameters-Selections.md) | [Rotor Features - Dual Generator](Rotor-Features-Dual-Generator.md) |
