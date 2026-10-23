# 13. Board Features

| Feature | Description |
|---|---|
| Copper Layers | 2 or 4. On 4 layers the RX and TX layers are chosen freely |
| Vias | Through vias, or (`VIA_TYPE = "blind"`, 4 layers) blind vias between the two layers each via joins |
| Board Edges | Fixed bore and outer radius, or derived from the RX band |
| Clearance | On the finished board the vias, the fingers and the TX copper near the vias and the terminal are measured against `MIN_CLEARANCE_MM`; the spacing of the RX traces and of the TX turns is checked from the parameters |
| TX Self-Clearance | Checked by the generator, since KiCad's DRC cannot see it |
| TX Terminal | Placed by the generator where it keeps the largest gap from the RX copper (with `RX_TABS = "single"`, as close to the two fingers as the clearance allows); the board is then turned so the terminal sits at 0° (to the right) |
| Title Block | Filled in `Keyword: Value` style: TX, SIN/COS nets and phases, RX layers, radii, RX band |
| Page Size | Chosen automatically so the title block never overlaps the board |
| Silkscreen | A lead-cutting suggestion, drawn on `F.SilkS` and `B.SilkS` as the last step of a run: where to break each RX coil and where the two TX ends get their vias, with the lead names. It is guidance only and changes no copper (see [Silkscreen](Silkscreen.md)) |
| Pads | None, on purpose: the coils are broken out by hand |

![Board 1: 2-Layer And 4-Layer Stators](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/board_1_layers.png)

*Board 1. A 2-layer stator (RX on Top and Bottom, TX on Bottom), and 4-layer stators with the TX on
Top and on Top + Inner-1 (4 loops, one finger per coil, board edges 30 / 50 mm, pitch 1.2 mm, trace width 0.4 mm). Colours show the copper layer: Top red, Inner-1 green, Bottom dark blue. Right: the area around the TX terminal, to scale.*

Keep layers that carry no coil free of copper pours under the coil area: a plane there acts like an
extra target and weakens the signal.

| Previous | Next |
|:---|---:|
| [Rotor Features](Rotor-Features.md) | [Silkscreen](Silkscreen.md) |
