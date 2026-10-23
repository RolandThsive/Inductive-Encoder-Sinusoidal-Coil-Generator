# 18. Board Features - Dual Generator

The Dual Generator writes one stator board with two coil sets and one rotor disc with two rings. Each set is built,
turned and checked by the Single Generator's own code; the Dual Generator then puts the two sets on one board, checks
what only a dual board can get wrong (the gap between the sets, the distance between the rotor rings, the two
oscillators) and writes the files.

## 18.1 Features

| Feature | Description |
|---|---|
| Coil Sets | Two: set 1 inside (coarse, 1 loop by default) and set 2 outside (fine, 16 loops by default). Each has its own RX pair, its own TX ring and its own receiver IC |
| Copper Layers | Always 4. Each set's RX and TX layers are chosen freely (`RX_LAYER_A` / `B`, `TX_LAYER_A` / `B`); both sets may use the same layers, since their copper never overlaps radially |
| Nets | Six, one per coil: `SIN_1`, `COS_1`, `TX_1`, `SIN_2`, `COS_2`, `TX_2` by default. A name used twice is an error, because KiCad would join the two coils |
| Board Edges | One bore and one outline for both sets, given or computed as `DUAL_MODE` says (see [Quick Guide - Dual Generator](Quick-Guide-To-Parameters-Selections-Dual-Generator.md)) |
| Gap Between The Sets | Measured on the built copper, from the outermost copper of set 1 to the innermost copper of set 2 |
| Vias | Through vias (0.6 / 0.3 mm by default), or (`VIA_TYPE = "blind"`) blind vias between the two layers each via joins. A through via of one set is checked against the other set's copper on every layer |
| Clearance | Each set gets the Single Generator's own clearance checks. `GENERATOR_MODE`: `"normal"` prints a clearance warning and writes the boards, `"strict"` makes it an error. A short (copper touching copper of another net) is always an error, and so is copper of one set inside the other set's ring |
| TX Ends | Each set is turned so that its TX ends sit at its own angle: `TERMINAL_1_DEG` (180°, the left) and `TERMINAL_2_DEG` (0°, the right) |
| RX Fingers, TX Tails | None. Both RX rings are plain bands and each TX ring ends one pitch outside its last turn (fixed in `Dual_Fixed_Parameters.py`) |
| Title Block | Title `Dual stator <loops 1>x<loops 2> loops`. One comment line per set (loops, RX band, SIN / COS nets, rising and falling layers, TX net, wiring, turns per layer and the angle its ends sit at), then the radii and the measured gap, the trace widths and the layer count. The rotor's title block names the sectors, metal fraction and radii of each ring |
| Page Size | Chosen automatically, as on a single board, so the title block never overlaps the board |
| Silkscreen | A lead-cutting suggestion for both sets, drawn on `F.SilkS` and `B.SilkS` as the last step (see [Silkscreen - Dual Generator](Silkscreen-Dual-Generator.md)). No pads are created |
| Stack-Up | One air gap (`AIR_GAP_MM`, 1.0 mm) and one board thickness (`PCB_THICKNESS_MM`, 3.2 mm by default) for both sets |

## 18.2 Layers

The recommended layers, which are the defaults, put each set's RX on Top + Inner-1 and its TX on Top + Inner-2. That
leaves **Bottom free of both sets' copper**. Set 1's six leads must cross set 2 on their way to set 1's IC; on the free
Bottom layer, the one farthest from the rotor, they can do that radially, as tight pairs, at one angle. The checker
warns when set 2 uses all four layers, because then no layer is free for those leads.

![Dual Board 2: The Four Layers](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_board_2_layers.png)

*Dual Board 2. The four layers of the default board, each drawn on its own: Top carries the RX rising edges and TX turns
of both sets, Inner-1 the RX falling edges, Inner-2 the other half of both TX rings, and Bottom no copper (only the
through vias pass it). Silkscreen off.*

## 18.3 The Layout From The Centre Out

From the centre out, the stator is:

```text
bore | RX1 band | TX1 ring | TRACK_GAP_MM | RX2 band | TX2 ring | outline
```

- The bore sits `INNER_EDGE_INSET_MM` (1.2 mm) inside the RX1 band, so the RX1 inner-tip vias sit on the band start.
- Each TX ring starts `TX_OFFSET_MM` outside its RX band and ends one pitch outside its last turn, where the two TX ends
  sit. Its room comes from the Single Generator's own TX ring formula and is verified on the built copper.
- The gap is the copper-free ring from the outermost copper of set 1 (its TX1 ring ends, half a trace past one pitch
  outside the last turn) to the innermost copper of set 2 (the RX2 band start minus half an RX trace or a via radius,
  whichever is larger).
- The outline leaves at least `OUTER_EDGE_OFFSET_MM` (2.0 mm) past the RX2 band and `OUTER_EDGE_TAIL_MARGIN_MM` (0.7 mm)
  past the TX2 ring. In modes 1 to 3, when ring 2 of the rotor covers the TX2 turns (the default), the outline must also
  hold ring 2: the outermost TX2 copper plus `ROTOR_AUTO_TX_OVERHANG_MM` (0.5 mm), `ROTOR_AUTO_EDGE_CLEARANCE_MM`
  (0.5 mm) and `LAYOUT_TOLERANCE_MM` (0.05 mm, or half the edge line plus the sag of the ring's polygon when that is
  more). On the default board this rule sets the outline: 25.825 + 0.5 + 0.5 + 0.05 = 26.875 mm, where the first two
  rules ask for 25.9 and 26.8 mm.

![Dual Board 1: From The Centre Out](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/dual_board_1_layout.png)

*Dual Board 1. The default board measured on the written files. Each stator bar is the copper of one coil (traces with
their width, vias with their diameter), grey because each coil spans two layers; the rotor bars are the two rings,
red because the rotor copper is on Top. The arrows are the gap between the sets
(3.725 mm) and the three rotor distances of [Rotor Features - Dual Generator](Rotor-Features-Dual-Generator.md#173-distances-between-the-rings).*

The gap is **not** what isolates the two sets. A balanced RX band sees no net flux from a round TX ring, however close.
The residual coupling from TX1 into RX2 comes from asymmetry (the TX ends, the vias, layer misregistration) and falls
only slowly with distance; dual boards in practice leave 1.1 to 1.4 mm between the two RX bands, all of it TX turns. The
gap is there for the copper clearance and the solder mask. What keeps the fine track clean is the distance from ring 1
of the rotor to the RX2 band (`ROTOR_1_TO_RX2_MM`).

## 18.4 Two Oscillators

Each set has its own TX oscillator at its own `EXCITATION_FREQ_HZ` (3.0 MHz for set 1 and 4.3 MHz for set 2 by
default). The generator draws two TX rings; whether both ICs drive their own ring, or one IC drives both tanks and the
other has its TX current set to 0, is decided on the schematic. If the two tanks are driven separately, each IC's
switching demodulator mixes the other carrier down and its automatic gain control sees both carriers. So the checker
warns:

| Rule | Parameter | Default |
|---|---|---|
| The two frequencies must differ by at least this share of the lower one (closer is a warning) | `TX_FREQ_SEPARATION_MIN` | 0.2 (20 %) |
| They must not sit within this tolerance of a small integer ratio p:q (3.0 / 4.5 MHz = 2:3 is a warning; 3.0 / 4.3 MHz is not) | `TX_FREQ_RATIO_TOLERANCE` | 0.02 (2 %) |
| The largest p and q checked (4 covers 2:1, 3:1, 4:1, 3:2 and 4:3; 1 turns the ratio warning off) | `TX_FREQ_RATIO_MAX_ORDER` | 4 |

When the frequencies pass, the checker still notes that two free-running tanks have not been shown to work: two-IC dual
boards usually drive one tank only. Prove it on the first board by reading each IC's gain with the other TX on and off.
Pulling the two tanks onto each other is not the risk: the lock range is about f0 × k / (2 Q), a few tens of kHz for a
coupling k below 0.3.

## 18.5 Checks On The Finished Boards

On top of the Single Generator's checks for each set, the Dual Generator checks:

- **The gap between the sets**, on the built copper. Less than `TRACK_GAP_MM` (modes 1 and 3) or `MIN_CLEARANCE_MM`
  (modes 2 and 4) is an error that says how far to move the RX2 band out.
- **The layout formulas**. When the built copper differs from the formulas by more than `LAYOUT_TOLERANCE_MM`
  (0.05 mm), the run warns; the boards are as built.
- **The rotor rings**: the bare ring between them (an error below `ROTOR_TRACK_GAP_MM`), each ring's distance from the
  other set's RX copper (warnings), and either ring reaching over the other set (warnings).
- **The electrical estimate**, for each set against its own IC (`Dual_IC1_Parameters.py`, `Dual_IC2_Parameters.py`). See
  [Electrical Estimate](Electrical-Estimate.md).

Every message is listed in [Checks, Errors And Warnings](Checks-Errors-And-Warnings.md#236-dual-generator).

| Previous | Next |
|:---|---:|
| [Rotor Features - Dual Generator](Rotor-Features-Dual-Generator.md) | [Silkscreen - Dual Generator](Silkscreen-Dual-Generator.md) |
