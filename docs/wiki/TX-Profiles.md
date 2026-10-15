# 1. TX Profiles

The transmitter (TX) coil is a set of concentric turns around the RX band. This page shows the ways
the generator can lay it out: on one layer or two, wired in series or in parallel, and with the two
styles it uses to make way for the RX fingers. In every picture below only the TX is drawn; the RX
coils are not shown. Each picture is one run of the generator with only the named settings changed.
For the settings themselves see the [Parameter Reference](Parameter-Reference.md); for a short
decision guide see the [Quick Guide To Parameters Selections](Quick-Guide-To-Parameters-Selections.md).

## 1.1 Series And Parallel

| | Series (`TX_SERIES = True`) | Parallel (`TX_SERIES = False`) |
|---|---|---|
| Layers | Two TX layers (`TX_LAYERS = 2`) | Two TX layers (`TX_LAYERS = 2`) |
| Wiring | Two spirals joined by a via at the inner end; the turns of both add, so 2 × `TX_TURNS` turns | The same `TX_TURNS` turns on both layers, stitched together by vias |
| Both terminals | Leave radially at `TX_START_ANGLE_DEG` | One terminal, with the vias around it |
| Making way for RX fingers | Staggered (go-around) only | Staggered (go-around) or stitched, set by `TX_PARALLEL_BREAK_STYLE` |

With one TX layer (`TX_LAYERS = 1`) there is nothing to wire in series or in parallel: all
`TX_TURNS` turns sit on `TX_LAYER_A`, and the inner tail that carries the terminal runs on another layer.

## 1.2 2-Layer Board: One TX Layer

On a 2-layer board the two layers are Top (1) and Bottom (4). A single TX can sit on either one:

- **TX on Bottom only**: `TX_LAYERS = 1`, `TX_LAYER_A = 4`. This is the original layout and the default.
- **TX on Top only**: `TX_LAYERS = 1`, `TX_LAYER_A = 1`. The TX sits next to the rotor.

![TX Profiles 1: 2-layer board, one TX layer](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/tx_profiles_1_two_layer_single.png)

*TX Profiles 1. A 2-layer board with the TX on Bottom only and on Top only, whole board and a close-up of the TX terminal and tail. The inner tail runs on the other layer and joins the first turn at the via.*

## 1.3 2-Layer Board: TX On Top And Bottom

With `TX_LAYERS = 2`, `TX_LAYER_A = 1` and `TX_LAYER_B = 4` the TX uses both layers. Wherever an RX finger runs
on a layer that carries TX turns, the turns make way for it. The three possible combinations:

| | Staggered (go-around) | Stitched |
|---|---|---|
| **Series** | Available (the only style for series) | Not available |
| **Parallel** | `TX_PARALLEL_BREAK_STYLE = "staggered"` (default) | `TX_PARALLEL_BREAK_STYLE = "stitched"` |

![TX Profiles 2: 2-layer board, TX on Top and Bottom](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/tx_profiles_2_two_layer_pair.png)

*TX Profiles 2. A 2-layer board with the TX on Top and Bottom: series staggered, parallel staggered and parallel stitched. Top row: the whole board. Bottom row: close-up where an RX finger crosses the TX (the finger itself is not drawn).*

## 1.4 4-Layer Board: Combinations

A 4-layer board has Top (1), Inner 1 (2), Inner 2 (3) and Bottom (4). The TX can use any one layer or any
two different layers (`TX_LAYER_A`, `TX_LAYER_B`). The TX only has to make way for a finger when the
finger's layer (`RX_TAB_LAYER`) carries TX turns, so in the picture below the fingers are set on Top.
A TX that does not use the finger's layer is never interrupted.

| Combination | Settings |
|---|---|
| TX on Top only | `TX_LAYERS = 1`, `TX_LAYER_A = 1` |
| TX on Bottom only | `TX_LAYERS = 1`, `TX_LAYER_A = 4` |
| Series, Top + Inner 2 | `TX_LAYERS = 2`, `TX_LAYER_A = 1`, `TX_LAYER_B = 3`, `TX_SERIES = True` |
| Series, Top + Bottom | `TX_LAYERS = 2`, `TX_LAYER_A = 1`, `TX_LAYER_B = 4`, `TX_SERIES = True` |
| Parallel, Top + Inner 2, staggered | As above with `TX_SERIES = False`, `TX_PARALLEL_BREAK_STYLE = "staggered"` |
| Parallel, Top + Inner 2, stitched | As above with `TX_SERIES = False`, `TX_PARALLEL_BREAK_STYLE = "stitched"` |

![TX Profiles 3: 4-layer board combinations](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/tx_profiles_3_four_layer.png)

*TX Profiles 3. Six TX combinations on a 4-layer board (RX on Top and Inner 1, fingers on Top), close-up where an RX finger crosses. TX on Bottom only has no turns on the finger's layer, so it runs unbroken.*

The recommended combination (series, stepped turns, Top + Inner 2, fingers on Inner 1) is described in the
[Quick Guide To Parameters Selections](Quick-Guide-To-Parameters-Selections.md#141-recommended-combination).

| Previous | Next |
|:---|---:|
| [RX Profiles](RX-Profiles.md) | [Choosing A Rotor And Stator](Choosing-A-Rotor-And-Stator.md) |
