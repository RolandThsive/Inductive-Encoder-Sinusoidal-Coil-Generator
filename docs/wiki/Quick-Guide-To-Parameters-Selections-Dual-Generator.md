# 20. Quick Guide To Parameters Selections - Dual Generator

A dual board is two coil sets on one board, so before it is built you choose how the radii are given: which of the two
RX bands, the two board edges and the gap between the sets you set, and which the generator works out. That choice is
`DUAL_MODE`, in `Dual_Board_Parameters.py`. This page shows the four modes, the two settings that only some modes
use (`BAND_SPLIT` in mode 1, `TRACK_GAP_MM` in modes 1 and 3), and a starting point for the rest. Every picture is a run of the Dual Generator
with only the named settings changed, silkscreen off; colour shows the copper layer (Top red, Inner-1 green, Inner-2
dark yellow). Each parameter is described in full in the
[Parameter Reference Dual Generator](Parameter-Reference-Dual-Generator.md).

## 20.1 The Four Modes

From the centre out the stator is `bore | RX1 band | TX1 ring | TRACK_GAP_MM | RX2 band | TX2 ring | outline`. The TX
rings always follow from their RX bands (`TX_OFFSET_MM`, `TX_TURNS`, `TX_PITCH_MM`), so the choice is between the two
bands, the two edges and the gap:

| `DUAL_MODE` | You Give | Must Be `None` | The Generator |
|---|---|---|---|
| **1** | `TRACK_GAP_MM`, `INNER_EDGE_RADIUS_MM`, `OUTER_EDGE_RADIUS_MM`, `BAND_SPLIT` | Both RX bands (all four radii in `Dual_RX1` and `Dual_RX2`) | Fits both bands between the edges; `BAND_SPLIT` shares the free width between them |
| **2** (default) | Both RX bands | `TRACK_GAP_MM` and both edges | Computes the bore and the outline from the bands, and measures and reports the gap |
| **3** | One RX band (in `Dual_RX1` or `Dual_RX2`) and `TRACK_GAP_MM` | The other band and both edges | Places the other band across the gap with the same half width (`RX_A_MM`), then works as mode 2 |
| **4** | Both RX bands and both edges | `TRACK_GAP_MM` | Uses everything as given, checks that each edge leaves room, and measures and reports the gap |

![Dual Parameters 1: The Four DUAL_MODEs](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_params_1_modes.png)

*Dual Parameters 1. The same two sets (inner 1 loop, outer 16 loops, 4 + 4 series TX turns per set, pitch 0.35 mm) laid
out four ways, at the same scale. Next to each board: what was given and what the generator computed, read from the
run's `Parameters.txt` (radii in mm). Mode 1: bore 7.25, outline 30, gap 3, `BAND_SPLIT` 0.5 give RX1 8.45 to 14.95 and
RX2 20.525 to 27.025. Mode 2: the default bands give bore 7.25, outline 26.875 and a measured gap of 3.725. Mode 3: RX1
8.45 to 11.7 and a gap of 3 give RX2 17.275 to 20.525 (the same half width, 1.625) and outline 23.5. Mode 4: the default
bands with bore 6.5 and outline 28.*

Which mode to use:

- **Mode 1** when the board outline and the shaft hole are fixed (a housing, a bearing) and you want the largest bands
  that fit.
- **Mode 2** when both bands matter, for example to match a known design; the board grows to suit them.
- **Mode 3** when one track is fixed and the other may go wherever the gap puts it.
- **Mode 4** when everything is fixed and you only want it built and checked.

### 20.1.1 What The Checker Says

The checker holds what is set against the chosen mode. A value the mode needs that is `None`, or a value that must be
`None` and is set, is an error that names every such value. When what is set matches another mode, the error names
that mode too. For example, with `DUAL_MODE = 2` and `TRACK_GAP_MM = 3.0`:

```text
ERROR   DUAL_MODE conflicts with TRACK_GAP_MM
        DUAL_MODE = 2 (the edges from the bands) does not match what is set: TRACK_GAP_MM = 3.0 (Dual_Board_Parameters.py)
        but the mode measures the gap: set it to None. Change the values, or choose another DUAL_MODE.
```

The error then lists the four modes. Change the values, or change `DUAL_MODE`.

## 20.2 Giving A Band

Each set's band is the ring of radii its RX curves weave in, given in its own file (`Dual_RX1_Parameters.py`,
`Dual_RX2_Parameters.py`) in one of two ways, or not at all:

| Way | Parameters | The Band |
|---|---|---|
| Radii pair | `INSIDE_RADIUS_MM`, `OUTSIDE_RADIUS_MM` (with `RX_R_BASE_MM`, `RX_A_MM` = `None`) | From the inside radius to the outside radius |
| R base and A pair | `RX_R_BASE_MM`, `RX_A_MM` (with `INSIDE_RADIUS_MM`, `OUTSIDE_RADIUS_MM` = `None`) | `RX_R_BASE_MM - RX_A_MM` to `RX_R_BASE_MM + RX_A_MM` |
| Not given | All four `None` | Placed by the generator (mode 1, or mode 3 for the band you leave out); `Parameters.txt` prints the values it chose |

Each pair goes together: a pair with only one value set is an error, and so is a band given by both pairs at once.

## 20.3 Sharing The Width: `BAND_SPLIT` (Mode 1)

In mode 1 the free radial width between the edges, after both TX rings and the gap, is shared between the two bands.
`BAND_SPLIT` is set 1's share, strictly between 0 and 1: 0.5 gives both bands the same width. A 1x / 16x board is
usually near 0.5; the more loops the fine track has, the more width it should get (a smaller `BAND_SPLIT`).

![Dual Parameters 2: BAND_SPLIT](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_params_2_band_split.png)

*Dual Parameters 2. `BAND_SPLIT` = 0.35, 0.5 (the default) and 0.65 with the bore at 7.25 mm, the outline at 30 mm and
`TRACK_GAP_MM` at 3 mm. The two bands always share 13 mm: 4.55 + 8.45, 6.5 + 6.5 and 8.45 + 4.55 mm.*

## 20.4 The Gap Between The Sets: `TRACK_GAP_MM` (Modes 1 And 3)

`TRACK_GAP_MM` is the copper-free ring between the sets: from the outermost copper of set 1 (its TX1 ring) to the
innermost copper of set 2 (the RX2 band start minus half an RX trace or a via radius, whichever is larger). In modes 1
and 3 it is the gap to leave; in modes 2 and 4 it must be `None`, and the measured gap must be at least
`MIN_CLEARANCE_MM`.

![Dual Parameters 3: TRACK_GAP_MM](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_params_3_gap.png)

*Dual Parameters 3. Mode 3 with the RX1 band given (8.45 to 11.7 mm) and `TRACK_GAP_MM` = 0.5, 2 and 4 mm. RX2 is placed
across the gap with the same half width (1.625 mm), and the outline follows it: 21, 22.5 and 24.5 mm.*

The gap does not isolate the two sets electrically: a balanced RX band sees no net flux from a round TX ring, however
close, and what is left falls only slowly with distance. Keep the gap for the copper clearance and the solder mask. What
keeps the fine track clean is the distance from ring 1 of the rotor to the RX2 band, `ROTOR_1_TO_RX2_MM` (see
[Rotor Features - Dual Generator](Rotor-Features-Dual-Generator.md#173-distances-between-the-rings)). The rotor needs
room too: `ROTOR_TRACK_GAP_MM` (2 mm) must stay bare between the two rings, so a very small gap between the sets can
make the rotor the limit.

## 20.5 A Starting Point

The defaults are a complete 1x / 16x board on a 53.75 mm disc, built without warnings. Start from them and change one
thing at a time:

| Choice | Default | Why |
|---|---|---|
| Loops | Set 1: 1, set 2: 16 | The coarse track gives the absolute angle; its error must stay below 180 / `LOOPS` of set 2 degrees (±11.25° for 16 loops) |
| Layers | RX on Top + Inner-1, TX on Top + Inner-2, both sets | Leaves Bottom free for set 1's leads to cross set 2 |
| TX | Series, 4 turns per layer, pitch 0.35 mm, traces 0.15 mm | Enough inductance at 3 MHz for the inner tank; every turn of TX1 pushes set 2 out. A parallel ring needs a pitch of at least 0.43 mm with 0.6 mm vias |
| TX ends | `TERMINAL_1_DEG` 180, `TERMINAL_2_DEG` 0 | Opposite sides, so the two sets' breakouts stay apart |
| Frequencies | 3.0 MHz and 4.3 MHz | 43 % apart and on no small integer ratio |
| Rotor | Ring 1 inside TX1 (`ROTOR_AUTO_COVER_TX = False`), ring 2 over TX2 | Keeps the half-moon ring 1 well away from the fine band |
| Vias and clearance | 0.6 / 0.3 mm, 0.15 mm | Leave room in the inner set's tight TX ring |
| Board thickness | 3.2 mm | |

Check before generating, then generate, from the `Dual Generator` folder:

```bash
python Dual_Generator/Checks/Dual_CheckParameters.py
python Dual_Generator/Run/Dual_RunCoilGenerator.py
```

## 20.6 Related Pages

- [Quick Guide To Parameters Selections](Quick-Guide-To-Parameters-Selections.md): the band, TX and rotor choices of each
  set, which hold for the Dual Generator too (except the fingers and tails a dual board does not have).
- [Board Features - Dual Generator](Board-Features-Dual-Generator.md): the layout and the checks.
- [Choosing A Rotor And Stator](Choosing-A-Rotor-And-Stator.md): coarse and fine tracks.

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [Silkscreen - Dual Generator](Silkscreen-Dual-Generator.md) | [Parameter Reference Single Generator](Parameter-Reference-Single-Generator.md) |
