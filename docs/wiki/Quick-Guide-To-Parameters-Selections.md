# 14. Quick Guide To Parameters Selections

This page shows, with pictures made by the generator itself, the choices you make before a board is
built: how the RX band is defined, how many TX turns and how long a TX tail, how the TX is wired and
how it makes way for the RX fingers, and how much of the rotor is metal. Every picture is one run of
the generator with only the named setting changed. Each parameter is described in full in the
[Parameter Reference](Parameter-Reference.md).

## 14.1 Defining The RX Band

The RX band is the ring of radii in which the RX curves weave. Three things can set it:

| | Parameters | Meaning |
|---|---|---|
| **Board edges** | `INNER_EDGE_RADIUS_MM` (bore), `OUTER_EDGE_RADIUS_MM` (outline) | The two circles that bound the board |
| **Radii pair** | `INSIDE_RADIUS_MM`, `OUTSIDE_RADIUS_MM` | The band's inner and outer radius |
| **R base and A pair** | `RX_R_BASE_MM`, `RX_A_MM` | The band's centre line and half width: the band is `r_base ± A` |

Each row and column below is one of them. A cell shows whether the two can be used together (the
diagonal is each one on its own):

| | Board edges | Radii pair | R base and A pair |
|---|---|---|---|
| **Board edges** | ✅ Alone: the band is fitted between the edges | ✅ Edges set the board, the pair sets the band | ✅ Edges set the board, the pair sets the band |
| **Radii pair** | ✅ Edges set the board, the pair sets the band | ✅ Alone: the edges are computed from the band | ❌ Not allowed: the band would be given twice |
| **R base and A pair** | ✅ Edges set the board, the pair sets the band | ❌ Not allowed: the band would be given twice | ✅ Alone: the edges are computed from the band |

The five allowed setups are pictured below: 1 = edges only, 2 = edges + radii pair, 3 = edges +
R base and A, 4 = radii pair only, 5 = R base and A only.

Rules behind the table:

- **A pair is always set together** (both radii, or both of R base and A). Set only one of the two
  pairs; leave the other pair at `None`.
- **Edges only** (every pair `None`): the band is fitted between the edges, leaving room for the TX, the
  tail and the fingers. Both edges must then be set.
- **With a pair**, each edge may be set or left `None`. An edge set to `None` is computed from the band:
  the bore sits `INNER_EDGE_INSET_MM` inside the band and the outline a little beyond the TX, tail and
  fingers.
- A fixed edge that leaves too little room for the band is an error, and the checker tells you the
  radius it needs.

![Parameters 1: Defining The RX Band](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/params_1_rx_band.png)

*Parameters 1. The same 1-loop stator defined five ways. 1: board edges only (band fitted, 16.2 to
22.4 mm). 2: edges plus the pair INSIDE 17 / OUTSIDE 22. 3: edges plus the pair R_BASE 19.5 / A 2.5
(the same band as 2). 4 and 5: the same two pairs without board edges, so the edges are computed
(15.8 and 26.6 mm).*

Use edges only when the board outline is fixed and you want the largest band that fits. Use a pair when
the band radii matter (for example to match a reference design); add the edges when the outline is also
fixed. Use a pair alone when only the band matters and the board may grow to suit it.

## 14.2 TX Turns

`TX_TURNS` is the number of complete TX turns **per layer**. The first turn sits `TX_OFFSET_MM` outside
the RX band and each next turn `TX_PITCH_MM` further out. More turns raise the inductance and the
signal, and need a wider board edge.

![Parameters 2: TX Turns](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/params_2_tx_turns.png)

*Parameters 2. TX_TURNS = 1, 2, 3 and 5 on one layer (pitch 0.6 mm), close-up beside the TX terminal.
Everything else is unchanged; only the outer edge moves out.*

## 14.3 TX Tail

The tail is the short radial piece that carries the TX terminal out past the outermost turn.
`TX_TAIL_EXTRA_MM` sets how far it reaches beyond the outermost turn; the default is 1 mm.

![Parameters 3: TX Tail](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/params_3_tx_tail.png)

*Parameters 3. TX_TAIL_EXTRA_MM = 0, 2 and 4 mm. A longer tail makes it easier to solder or connect, and
moves the outer board edge out with it.*

## 14.4 TX Styles

With two TX layers (`TX_LAYERS = 2`) the turns are wired in **series** (`TX_SERIES = True`, two spirals
joined by a via, twice the turns) or in **parallel** (`TX_SERIES = False`, the same turns on both layers,
stitched together by vias). Wherever an RX finger crosses the TX, the turns on the finger's layer must
make way for it:

- **Staggered (go-around).** Each turn ends before the finger, runs out to a via, and a bracket on the
  other layer carries it around the end of the finger. Both layers stay complete. The finger sticks out
  past the brackets, so the board grows by about 2 mm.
- **Stitched.** The turns on the finger's layer stop at a via on each side of the finger and the turns of
  the other layer carry the current past it. There is no copper outside the TX ring. **Parallel TX only.**

The two wirings and the two styles combine like this:

| | Staggered (go-around) | Stitched |
|---|---|---|
| **Series** (`TX_SERIES = True`) | ✅ The only style a series TX can use. Two spirals joined by a via, 2 × `TX_TURNS` turns, both terminals leave at `TX_START_ANGLE_DEG` | ❌ Not available |
| **Parallel** (`TX_SERIES = False`) | ✅ `TX_PARALLEL_BREAK_STYLE = "staggered"` (the default). The same turns on both layers; the finger's layer goes around the finger, brackets on the other layer. Both layers stay complete; the board grows by about 2 mm | ✅ `TX_PARALLEL_BREAK_STYLE = "stitched"`. The same turns on both layers; the finger's layer stops at a via on each side of the finger and the other layer carries the current past it. No copper outside the TX ring |

`TX_PARALLEL_BREAK_STYLE` applies only to a parallel TX; a series TX always goes around the fingers.

### 14.4.1 Recommended Combination

The best combination is a **4-layer board** with the RX fingers (if you choose to have them) on
**Inner 1** and a **series TX with stepped turns on Top and Inner 2**:

| Setting | Value |
|---|---|
| `PCB_LAYERS` | `4` |
| `RX_TAB_LAYER` | `2` (Inner 1) |
| `TX_LAYERS` | `2` |
| `TX_LAYER_A`, `TX_LAYER_B` | `1` (Top) and `3` (Inner 2) |
| `TX_SERIES` | `True` |
| `TX_TURN_SHAPE` | `"stepped"` |

The fingers then sit on a layer that carries no TX turns, so no turn has to go around them. The
generator builds this setup without errors.

![Parameters 6: Recommended Combination](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/params_6_recommended.png)

*Parameters 6. The recommended combination, generated with exactly the settings in the table above (3 turns per TX layer, RX band 17 to 22 mm, 1 loop). The TX turns on Inner 2 run directly below the Top turns at the same radii, so they are hidden by them in this view. The fingers are on Inner 1.*

![Parameters 4: TX Styles](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/params_4_tx_styles.png)

*Parameters 4. Series staggered, parallel staggered and parallel stitched on the same 1-loop stator (TX
on Top and Bottom, 3 turns per layer, fingers on Top). Top row: the whole board. Bottom row: one finger
close up.*

## 14.5 Rotor Metal Fraction

`ROTOR_AUTO_DUTY` is the share of each period that is metal: 0.5 is half metal and half gap (180°
electrical). With a 1-loop stator there is one metal sector, so the duty is simply the angle it covers.
The rotor's metal also covers the TX ring by `ROTOR_AUTO_TX_OVERHANG_MM`.

![Parameters 5: Rotor Metal Fraction](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/params_5_rotor_duty.png)

*Parameters 5. ROTOR_AUTO_DUTY = 0.5, 0.25 and 0.75 over the same 1-loop stator. The rotor is drawn
semi-transparent over the stator, so the RX and TX stay visible.*

0.5 is the default. A smaller or larger duty changes the signal shape and amplitude, and a single metal sector is mechanically unbalanced, so add a counterweight
if the shaft turns fast. The [Suggestive Analysis And Optimization](Suggestive-Analysis-And-Optimization.md)
page shows how to search for the best duty for your board.

## 14.6 Related Pages

- [RX Profiles](RX-Profiles.md): the curve that the RX band is filled with.
- [Stator Features](Stator-Features.md) and [Rotor Features](Rotor-Features.md): every option in detail.
- [Parameter Reference](Parameter-Reference.md): all parameters, defaults and ranges.

| Previous | Next |
|:---|---:|
| [Board Features](Board-Features.md) | [Parameter Reference](Parameter-Reference.md) |
