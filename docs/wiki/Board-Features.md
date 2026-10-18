# 13. Board Features

| Feature | Description |
|---|---|
| Copper Layers | 2 or 4. On 4 layers the RX and TX layers are chosen freely |
| Vias | Through vias only, no blind or buried vias |
| Board Edges | Fixed bore and outer radius, or derived from the RX band |
| Clearance | Every via and trace is checked against `MIN_CLEARANCE_MM` |
| TX Self-Clearance | Checked by the generator, since KiCad's DRC cannot see it |
| TX Terminal | Placed by the generator where it keeps the largest gap from the RX copper; the board is then turned so the terminal sits at 0° (to the right) |
| Title Block | Filled in `Keyword: Value` style: TX, SIN/COS nets and phases, RX layers, radii, RX band |
| Page Size | Chosen automatically so the title block never overlaps the board |
| Silkscreen And Pads | None, on purpose: the coils are broken out by hand |

![Board 1: 2-Layer And 4-Layer Stators](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/board_1_layers.png)

*Board 1. A 2-layer stator (RX on Top and Bottom, TX on Bottom), and 4-layer stators with the TX on
Top and on Top + Inner-1 (4 loops, one finger per coil, board edges 30 / 50 mm, pitch 1.2 mm, trace width 0.4 mm). Colours show the copper layer: Top red, Inner-1 green, Bottom dark blue. Right: the area around the TX terminal, to scale.*

Keep layers that carry no coil free of copper pours under the coil area: a plane there acts like an
extra target and weakens the signal.

| Previous | Next |
|:---|---:|
| [Rotor Features](Rotor-Features.md) | [Quick Guide To Parameters Selections](Quick-Guide-To-Parameters-Selections.md) |
