# 9. TX Profiles

The transmitter (TX) coil is a set of concentric turns around the RX band. This page shows the ways
the generator can lay it out: on one layer or two, wired in series or in parallel, and with the two
styles it uses to make way for the RX fingers. In every picture below only the TX is drawn; the RX
coils are not shown. Each picture is one run of the generator with only the named settings changed (TX pitch 1.0 mm, trace width 0.4 mm, three turns). Colour shows the copper layer, not the net: Top red, Inner-1 green, Inner-2 dark yellow, Bottom dark blue.
For the settings themselves see the [Parameter Reference Single Generator](Parameter-Reference-Single-Generator.md); for a short
decision guide see the [Quick Guide To Parameters Selections](Quick-Guide-To-Parameters-Selections.md).

## 9.1 Series And Parallel

| | Series (`TX_WIRING = "series"`) | Parallel (`TX_WIRING = "parallel"`) |
|---|---|---|
| Layers | Two TX layers (`TX_LAYER_A`, `TX_LAYER_B`) | Two TX layers (`TX_LAYER_A`, `TX_LAYER_B`) |
| Wiring | Two spirals joined by a via at the inner end; the turns of both add, so 2 × `TX_TURNS` turns | The same `TX_TURNS` turns on both layers, stitched together by vias |
| Both terminals | Leave radially at the TX terminal | Leave radially at the TX terminal, with the stitching vias around it |
| Making way for RX fingers | Staggered (go-around) only | Stitched (default) or staggered (go-around), set by `TX_PARALLEL_BREAK_STYLE` |

With one TX layer (`TX_WIRING = "single"`) there is nothing to wire in series or in parallel: all
`TX_TURNS` turns sit on `TX_LAYER_A`, and the inner tail that carries the terminal runs on another layer.

The TX terminal has no setting. The generator puts it where it keeps the largest gap from the RX copper. With `RX_TABS = "single"` it takes instead the place nearest the two fingers that keeps `MIN_CLEARANCE_MM`. It then turns
the whole board so that the terminal ends up at 0° (to the right), as in every picture on this page.

## 9.2 2-Layer Board: One TX Layer

On a 2-layer board the two layers are Top (1) and Bottom (4). A single TX can sit on either one:

- **TX on Bottom only**: `TX_WIRING = "single"`, `TX_LAYER_A = 4`. This is the default.
- **TX on Top only**: `TX_WIRING = "single"`, `TX_LAYER_A = 1`. The TX sits next to the rotor.

![TX Profiles 1: 2-layer board, one TX layer](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/tx_profiles_1_two_layer_single.png)

*TX Profiles 1. A 2-layer board with the TX on Bottom only (top row) and on Top only (bottom row): the whole board on the left and a to-scale close-up of the TX terminal and tail on the right. The inner tail runs on the other layer and joins the first turn at the via.*

## 9.3 2-Layer Board: TX On Top And Bottom

With `TX_WIRING = "series"` or `"parallel"`, `TX_LAYER_A = 1` and `TX_LAYER_B = 4` the TX uses both layers. Wherever an RX finger runs
on a layer that carries TX turns, the turns make way for it. The three possible combinations:

| | Staggered (go-around) | Stitched |
|---|---|---|
| **Series** | Available (the only style for series) | Not available |
| **Parallel** | `TX_PARALLEL_BREAK_STYLE = "staggered"` | `TX_PARALLEL_BREAK_STYLE = "stitched"` (default) |

![TX Profiles 2: 2-layer board, TX on Top and Bottom](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/tx_profiles_2_two_layer_pair.png)

*TX Profiles 2. A 2-layer board with the TX on Top and Bottom and an RX finger on Top at every tip (`RX_TABS = "all"`): series, parallel stitched and parallel staggered. Left: the whole board. Right: a to-scale close-up at the top of the ring. The RX fingers are not drawn, but the TX makes way for them where they would cross: the series and the staggered TX go around each finger on Bottom, the stitched TX carries on along its Bottom turns between two vias.*

With `RX_TABS = "single"` both fingers sit next to the TX terminal. A parallel TX is always stitched around its terminal,
so there both fingers fall inside the stitched part and `TX_PARALLEL_BREAK_STYLE` changes nothing.

## 9.4 4-Layer Board: Combinations

A 4-layer board has Top (1), Inner 1 (2), Inner 2 (3) and Bottom (4). The TX can use any one layer or any
two different layers (`TX_LAYER_A`, `TX_LAYER_B`). The TX only has to make way for a finger when the
finger's layer (`RX_TAB_LAYER`) carries TX turns, so in the picture below the fingers are set on Top (`RX_TAB_LAYER = 1`), one at every tip.
A TX that does not use the finger's layer is never interrupted.

| Combination | Settings |
|---|---|
| TX on Top only | `TX_WIRING = "single"`, `TX_LAYER_A = 1` |
| TX on Bottom only | `TX_WIRING = "single"`, `TX_LAYER_A = 4` |
| Series, Top + Inner 2 | `TX_WIRING = "series"`, `TX_LAYER_A = 1`, `TX_LAYER_B = 3` |
| Series, Top + Bottom | `TX_WIRING = "series"`, `TX_LAYER_A = 1`, `TX_LAYER_B = 4` |
| Parallel, Top + Inner 2, stitched | `TX_WIRING = "parallel"`, `TX_LAYER_A = 1`, `TX_LAYER_B = 3`, `TX_PARALLEL_BREAK_STYLE = "stitched"` |
| Parallel, Top + Inner 2, staggered | As above with `TX_PARALLEL_BREAK_STYLE = "staggered"` |

![TX Profiles 3: 4-layer board combinations](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/tx_profiles_3_four_layer.png)

*TX Profiles 3. Six TX combinations on a 4-layer board (RX on Top and Inner-1, a finger on Top at every tip), a to-scale close-up at one finger at the top of the ring. The TX on Bottom only has no turns on the finger layer, so it runs unbroken. The TX on Top only goes around the finger on Inner-1, its underpass layer.*

The recommended combination is described in the
[Quick Guide To Parameters Selections](Quick-Guide-To-Parameters-Selections.md#1541-recommended-combination).

## 9.5 Turn Shapes

Every combination above can use any of the three `TX_SHAPE` values: `stepped_diagonal` (the default), `stepped_arc` (arcs centred on the terminal via) and `spiral`. The stepped shapes change only the copper around the terminal. With `spiral` every turn is one smooth spiral that grows by one pitch per turn, so the TX ring ends one pitch farther out. The RX fingers must then reach one pitch farther too. With the shipped values `RX_TAB_LENGTH_MM` must be at least 3.5 mm instead of 3.0 mm. When it is too short, the generator stops and says the length it needs. No shape changes the layers or the wiring. `stepped_arc` takes one extra setting, `TX_STEPPED_ARC_RADIUS_MM`, described in [Stator Features](Stator-Features.md#1127-stepped-arc-radius).

![TX Profiles 4: TX turn shapes](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/tx_profiles_4_turn_shapes.png)

*TX Profiles 4. The three TX shapes around the terminal via on a 2-layer board with the TX on Bottom (TX only, terminal pointing right, to scale): `stepped_diagonal`, `stepped_arc` and `spiral`.*

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [RX Profiles](RX-Profiles.md) | [Choosing A Rotor And Stator](Choosing-A-Rotor-And-Stator.md) |
