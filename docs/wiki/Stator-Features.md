# 11. Stator Features

Every picture below is drawn directly from the `.kicad_pcb` files the generator wrote. Colours show
the copper layer only, for the RX and the TX alike: Top red, Inner-1 green, Inner-2 dark yellow and
Bottom dark blue. Traces are drawn at their true width (0.4 mm), the TX pitch is 1.2 mm, the board edges
are 30 and 50 mm unless a caption says otherwise, and close-ups are to scale with axes in millimetres
from the board centre.

## 11.1 RX Coils

The RX coils are the measuring part of the sensor. The generator always builds **four phases: a SIN
pair and a COS pair, each with a positive and a negative half**. Every phase carries its rising
edges on one layer and its falling edges on the other, so the SIN and COS coils see the same air
gap at every angle.

### 11.1.1 Loops

`LOOPS` sets the number of electrical periods per mechanical turn, from 1 to 16. One loop gives a
true absolute 0–360° sensor. More loops divide the turn into finer periods for higher resolution.

![Stator 1: RX Loops](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/stator_1_loops.png)

*Stator 1. The same board with 1, 2, 4, 8 and 16 loops (RX only, the TX is not drawn).*

### 11.1.2 Sub-Coils

Each RX coil can be split into 2 or 3 sub-coils, spread `RX_SUBCOIL_SPLIT_ELEC_DEG` electrical degrees apart (45° by default) and wired in
series. The split cancels chosen harmonics of the
signal (45° lowers the 3rd and 5th harmonics by about 59 %) and nearly doubles the signal. Sub-coils
are mainly useful on **miniature 1-loop coils**, where the RX band is small and harmonics matter
most.

![Stator 2: RX Sub-Coils](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/stator_2_subcoils.png)

*Stator 2. A miniature 1-loop stator (bore radius 16.8 mm, outer radius 34 mm) with 1 sub-coil and with 2 sub-coils split by 45° (RX only, the TX is not drawn).*

### 11.1.3 Finger Styles

The RX coils lie inside the TX ring. Bridging fingers carry each coil out across the TX ring so it
can be broken out to the receiver IC. No terminals or pads are created; the coils are broken out by
hand where the user wants them. `RX_TAB_LENGTH_MM` is the exact finger length: when it is too short to clear
the outermost TX turn (a longer TX pitch needs longer fingers) the generator stops and says which length it needs. A `spiral` TX needs fingers one pitch longer, because its last turn ends one pitch farther out. With the default values that is at least 3.5 mm.

| `RX_TABS` | Description |
|---|---|
| `all` | A finger at every outer tip of every phase (the original layout) |
| `single` | One finger per RX coil (two in all), on neighbouring outer tips; the TX terminal is placed next to them |
| `none` | A plain RX band without fingers |

![Stator 3: RX Bridging Fingers](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/stator_3_fingers.png)

*Stator 3. A 4-loop stator with fingers set to All, Single and None. In the models, Single is as
accurate as None. RX only, the TX is not drawn.*

## 11.2 TX Coils

The TX coil excites the sensor. All pictures in this part use the same 4-loop RX coils so that only
the TX changes.

### 11.2.1 Number Of Turns

`TX_TURNS` sets the number of complete turns per TX layer. More turns raise the inductance and the
Q of the oscillator tank; fewer turns leave more room for the RX band.

![Stator 4: TX Turns](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/stator_4_tx_turns.png)

*Stator 4. 1 to 5 TX turns per layer (series TX on Top + Inner-1, same board edges in every panel). The RX band shrinks as the TX ring grows.*

### 11.2.2 Series Versus Parallel

With two TX layers the turns can be wired in **series** (two spirals joined by a via at the inner
end, carrying current in the same direction) or in **parallel** (the same turns on both layers,
joined through vias). A parallel TX gives about 6 % more signal than a TX on Top alone (Analyser figure, to be verified). In the
electrical estimate its Q is only about 1.3 to 1.8 times higher: the resistance drops to about 0.6 times, but the inductance drops too. It is about 1.3 times with the default `stitched` break style (11.2.5) on a 1.6 mm 2-layer board, and more with the go-around (`staggered`) style, on a thinner board or on a 4-layer board.

![Stator 5: TX Series vs Parallel](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/stator_5_tx_series_parallel.png)

*Stator 5. Series and parallel TX on Top + Inner-1, with the detail around one RX finger.*

### 11.2.3 Series: Turn Shapes

`TX_SHAPE` takes three values:

| Value | Turns |
|---|---|
| `stepped_diagonal` (default) | Concentric circles joined by straight steps near the terminal. |
| `stepped_arc` | Concentric circles joined by arcs centred on the terminal via. See [11.2.7](#1127-stepped-arc-radius) and the picture in [TX Profiles](TX-Profiles.md#95-turn-shapes). |
| `spiral` | One smooth Archimedean spiral with a constant gap, useful when the pitch is tight. |

The pictures below show all three.

![Stator 6: Series TX Stepped vs Spiral](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/stator_6_tx_series_shape.png)

*Stator 6. Series TX with `stepped_diagonal`, `stepped_arc` and `spiral` turns, with the detail at the TX terminal.*

In a series spiral the two layers are mirror images. They coincide at the terminal and at 180°, and
are up to half a pitch apart at 90° and 270°. This is inherent: identical spirals would cancel each
other.

### 11.2.4 Parallel: Turn Shapes

![Stator 7: Parallel TX Stepped vs Spiral](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/stator_7_tx_parallel_shape.png)

*Stator 7. Parallel TX with `stepped_diagonal`, `stepped_arc` and `spiral` turns. The two layers lie on top of each other, so
the Inner-1 turns are mostly hidden under the Top turns.*

### 11.2.5 Break Styles At The Fingers

Where an RX finger runs on a layer that also carries TX turns, the TX must make way for it:

| Style | Description |
|---|---|
| **Go-Around** (`staggered`) | Each turn stops before the finger in a staircase, runs out to a via, and a nested bracket on the other layer carries it around the finger. Used by every series TX. |
| **Stitched** (parallel only) | The turns on the finger's layer stop at a via on each side of the finger, and the other layer carries the current past it. |

A series TX always uses the go-around. For a parallel TX, `TX_PARALLEL_BREAK_STYLE` defaults to `stitched`; set it to `staggered` for the go-around.

![Stator 8: TX Break Styles](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/stator_8_tx_break_styles.png)

*Stator 8. Close-up of one finger: series go-around, parallel stitched and parallel go-around.*

### 11.2.6 Terminal Via Placement And Step Angle (`stepped_diagonal`)

All TX turns are one net, so KiCad's DRC cannot see a TX turn touching another TX turn. The
generator measures these gaps itself and warns.

`TX_INSIDE_VIA_DISTANCE_MM` (used by `stepped_diagonal` and `spiral`, not by `stepped_arc`) moves the terminal via towards the centre, away from the next turn. With the
default 0.6 mm pitch and 0.8 mm via, at 0 mm (the original layout) the via comes too close to the neighbouring turn, and the generator
warns. With the 1.2 mm pitch of these pictures it does not.

![Stator 9: TX Terminal Via Placement](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/stator_9_tx_terminal_via.png)

*Stator 9. Terminal via at 0 mm and at 0.3 mm (the default), with 20° steps.*

`TX_STEPPED_ANGLE_DEG` (`stepped_diagonal` only, 5° to 90°) sets the angle of the steps, measured from the turn: 90° steps straight out. Steep steps are staggered automatically to keep
the clearance.

![Stator 10: TX Stepped Angle](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/stator_10_tx_step_angle.png)

*Stator 10. Step angles of 20°, 30°, 45° and 90°.*

### 11.2.7 Stepped Arc Radius

With `stepped_arc` the terminal via sits on the first turn and is the centre of all the arcs. Arc `n` has the
radius `TX_STEPPED_ARC_RADIUS_MM + n × TX_PITCH_MM` (n = 0 innermost). It leaves turn `n` on one side of the via,
runs round the via and lands on turn `n + 1` on the other side. The arcs are one pitch apart, so the copper gap
between neighbouring arcs equals the gap between the turns. The last arc stops at its outermost point and the outer
tail leaves radially from there.

| Setting | Meaning |
|---|---|
| `"auto"` (default) | The larger of `TX_PITCH_MM` and via radius + half a TX trace + `MIN_CLEARANCE_MM`, plus 0.02 mm and the chord sag of the turns. 0.72 mm with the default trace, via and clearance (arcs 0.72, 1.32 and 1.92 mm at a 0.6 mm pitch). |
| a number | That radius, in mm. It must be larger than `TX_PITCH_MM` and smaller than `TX_PITCH_MM + TX_TAIL_EXTRA_MM` (both are errors otherwise). Below the via clearance radius the generator warns. |

`stepped_arc` works with every TX layout: one layer, two layers in series (the arcs of the second layer are the
mirror image and one via is the centre of both sets), two layers in parallel, the windows around the fingers and
4-layer boards. All TX turns are one net, so KiCad's DRC cannot see TX copper touching TX copper; the generator
measures the smallest gap between the pieces of TX copper around the via itself and warns below `MIN_CLEARANCE_MM`.
The arcs bulge outwards, so the outer tail starts a little farther out than the outer step of `stepped_diagonal`.

![TX Profiles 4: TX turn shapes](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/tx_profiles_4_turn_shapes.png)

*TX Profiles 4. The three TX shapes around the terminal via on a 2-layer board with the TX on Bottom (TX only, terminal pointing right, to scale, pitch 1.0 mm): `stepped_diagonal`, `stepped_arc` and `spiral`.*

### 11.2.8 TX Terminal Placement

The TX terminal (tail, via, steps or arcs, windows) has no angle setting. The generator builds a probe TX at 0°,
sweeps the terminal round the ring against the real RX copper (vias, curves, fingers, junction vias) and keeps the
place with the largest gap; with `RX_TABS = "single"` it takes the place nearest the two fingers that keeps
`MIN_CLEARANCE_MM`. The whole board is then rotated so that the terminal sits at 0° (to the right), which is why
every picture on this wiki shows it there. The rotation angle is printed in the run and written to `Parameters.txt`.

| Previous | Next |
|:---|---:|
| [Choosing A Rotor And Stator](Choosing-A-Rotor-And-Stator.md) | [Rotor Features](Rotor-Features.md) |
