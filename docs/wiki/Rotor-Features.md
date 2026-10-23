# 12. Rotor Features

The rotor is a separate PCB with copper lobes on its face, mounted copper side towards the stator.
It is generated from the stator by default (`ROTOR_MODE = "according_to_stator"`), or drawn from
custom values.

## 12.1 Lobes

In the default mode (`according_to_stator`) the rotor has one copper lobe for every stator loop. In `custom` mode `ROTOR_CUSTOM_SECTORS` sets the number of lobes, and the checker warns when it differs from `LOOPS`.

![Rotor 1: Rotor Lobes](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rotor_1_lobes.png)

*Rotor 1. Rotors with 1, 2, 3, 4, 6, 8, 12 and 16 lobes.*

A 1-lobe rotor (a half disc at the default metal fraction of 0.5) is mechanically unbalanced; at high speed it needs a non-metal
counterweight.

## 12.2 Edges And Metal Fraction

| Parameter | Effect |
|---|---|
| `ROTOR_AUTO_COVER_TX` | The copper runs over the TX turns (5–8 % more signal in the model) |
| `ROTOR_AUTO_TX_OVERHANG_MM` | How far the copper reaches past the outermost TX turn |
| `ROTOR_AUTO_EXTENSION_INNER_MM` | Where the copper ends on the inside, relative to the RX band |
| `ROTOR_AUTO_DUTY` | The metal fraction of each period (0.5 = half copper, half gap) |
| `ROTOR_AUTO_COPPER_LAYERS` | Which layers carry the copper |
| `ROTOR_SOLDER_MASK_EXPANSION_MM` | Solder mask opening over the copper. The default, −1, keeps the mask over the copper (recommended) |
| `ROTOR_PCB_THICKNESS_MM` | Thickness of the rotor board written into the KiCad file (None = the stator's `PCB_THICKNESS_MM`); it changes nothing in the copper |

![Rotor 2: Rotor Edges And Metal Fraction](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rotor_2_edges.png)

*Rotor 2. A 4-lobe rotor over its stator: the default, a larger TX overhang, copper ending inside
the TX ring, a shorter inner edge, and metal fractions of 1/3 and 0.4. The stator is drawn faintly (Top red, Inner-1 green); series TX on Top + Inner-1, pitch 1.2 mm.*

The best metal fraction and outer edge depend on the coil. The optimizer (under construction on the [`analyser_and_optimizer` branch](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/tree/analyser_and_optimizer)) searches them together.

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [Stator Features](Stator-Features.md) | [Board Features](Board-Features.md) |
