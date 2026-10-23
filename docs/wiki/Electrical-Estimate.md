# 17. Electrical Estimate

`TX_Electrics.py` (in `Generator/Stator/TX/`) turns the geometry into absolute electrical numbers. `RunCoilGenerator.py` prints them in step 4 of every
generation. The analyser and optimizer (under construction on the [`analyser_and_optimizer` branch](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/tree/analyser_and_optimizer)) print a similar estimate, from their own `CoilElectrics.py`, for every case of the tolerance window and every candidate. Nothing
here changes a board.

> [!WARNING]
> None of these numbers has been checked against a measured board. Keep a margin to every limit of the IC.

## 17.1 What It Gives

- The **TX inductance** with the rotor away and with the rotor at the air gap.
- The **TX resistance** (DC) and the **Q**.
- The **tank capacitors** for `EXCITATION_FREQ_HZ` and the **oscillator frequency** they give.
- The **parallel resistance of the tank**, which is what the oscillator has to drive, as a range.

The oscillator frequency and the tank resistance are checked against the receiver IC limits in `IC_Parameters.py` (see [17.4](#174-receiver-ic-limits)). The receiver voltage is not estimated: it needs a model of the whole sensor, which is not part of the generator.

## 17.2 How The Numbers Are Made

| Quantity | Method |
|---|---|
| TX inductance | Every TX turn is taken as a circular loop (radius from the generator, depth from the stack-up: `PCB_THICKNESS_MM`, and `STACKUP_PREPREG_MM` for the inner layers of a 4-layer board). L = the turn self-inductances (a ring of a w × t trace) plus the mutual inductances of every pair of turns (Maxwell's formula for coaxial circles). Radial steps, spiral pitch and terminal tails are left out; against the full TX polyline (Neumann integral) this is within 2 %. |
| Resistance | DC resistance of all the TX copper. At the TX frequency skin and proximity effects raise it; the checks allow for up to an AC factor times the DC value. |
| Rotor effect | The rotor copper is taken as an ideal screen of the TX field. That is an upper estimate of the drop in inductance (a real rotor with gaps lets the field through them), so the true frequency with the rotor lies between "rotor away" and the predicted one. |
| Tank resistance | The true value lies between the value with the estimated rotor and the value with the rotor's effect left out. It is a warning only if even the higher value is below the IC's minimum. If only the lower value is, it is an info line that gives the range. |
| Tank capacitors | With `IC_SPLIT_TANK_CAPS = True` (the default), two capacitors of 2 C, one from each TX pin to ground (2 C from TX1 and 2 C from TX2, which is C across the coil). With False, one capacitor C across the coil. The estimate suggests the standard C0G values of `TANK_CAP_SERIES` (E12 by default) just below and above the value needed. |

**Example (series TX on Top + Inner-1, 4 loops, board edges 30 / 50 mm, 3 turns per layer, 1.2 mm pitch, 0.4 mm traces, one finger per RX coil (`RX_TABS = "single"`) of 7.2 mm).** L = 8.51 µH with the rotor away and 6.32 µH with the rotor at the 1 mm air gap (−25.7 %, upper estimate). R = 2.11 Ω DC, Q = 33 to 66. The tank for 3.5 MHz is 2 × 654 pF (nearest standard E12 C0G: 2 × 560 pF or 2 × 680 pF), and the parallel tank resistance is 4.6 to 9.2 kΩ against the 250 Ω minimum of the default IC limits, so there is no finding.

## 17.3 Not Included

- Parasitic capacitance (IC pins, coil, wiring; typically some 10 pF), which lowers the frequency a little.
- Temperature, except through `COPPER_CONDUCTIVITY_S_M`. Copper resistance rises 0.39 % per kelvin, so a lower conductivity models a warmer board.

## 17.4 Receiver IC Limits

The limits are set in `IC_Parameters.py`. The defaults are an example, the IPS2550. Take the values
from the datasheet of your IC and check your revision.

| Setting | Default | Meaning |
|---|---|---|
| `IC_NAME` | `"IPS2550"` | The name shown in the estimate. Any text, or None ("receiver IC"). |
| `IC_OSC_MIN_MHZ`, `IC_OSC_MAX_MHZ` | 2.0, 5.6 | The IC's LC oscillator range. |
| `IC_MIN_RP_OHM` | 250 | The smallest parallel (loss) resistance of the tank that the oscillator can drive (R_Peq). |
| `IC_SPLIT_TANK_CAPS` | True | True: the tank capacitance in two halves, 2 C from TX1 and 2 C from TX2 to ground. False: one C across the coil. |

Set both frequency limits to None to skip the frequency check, and `IC_MIN_RP_OHM` to None to skip the resistance
check. With all three None there are no IC checks. A missing line, or a missing `IC_Parameters.py`, uses the default
and prints an info line. See the [Parameter Reference](Parameter-Reference.md#155-ic-ic_parameterspy).

| Previous | Next |
|:---|---:|
| [Checks, Errors And Warnings](Checks-Errors-And-Warnings.md) | [Suggestive Analysis And Optimization](Suggestive-Analysis-And-Optimization.md) |
