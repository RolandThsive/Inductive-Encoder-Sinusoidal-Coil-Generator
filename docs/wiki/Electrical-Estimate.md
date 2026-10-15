# 1. Electrical Estimate

`CoilElectrics.py` turns the geometry into absolute electrical numbers. `RunCoilGenerator.py` prints them for every
generation, `AnalyzeCoil.py` for every case of its tolerance window and `OptimizeCoil.py` for every candidate. Nothing
here changes a board.

> [!WARNING]
> None of these numbers has been checked against a measured board. Keep a margin to every limit of the IC.

## 1.1 What It Gives

- The **TX inductance** with the rotor away and with the rotor at the air gap.
- The **TX resistance** (DC) and the **Q**.
- The **tank capacitors** for `EXCITATION_FREQ_HZ` and the **oscillator frequency** they give.
- The **parallel resistance of the tank**, which is what the oscillator has to drive.
- The **receiver voltage**, peak to peak, at the TX voltage of the IC.

These are checked against the datasheet limits of `RECEIVER_IC`.

## 1.2 How The Numbers Are Made

| Quantity | Method |
|---|---|
| TX inductance | Every TX turn is taken as a circular loop (radius from the generator, depth from the stack-up). L = the turn self-inductances (a ring of a w × t trace) plus the mutual inductances of every pair of turns (Maxwell's formula for coaxial circles). Radial steps, spiral pitch and terminal tails are left out; against the full TX polyline (Neumann integral) this is within 2 %. |
| Resistance | DC resistance of all the TX copper. At the TX frequency skin and proximity effects raise it; the checks allow for up to an AC factor times the DC value. |
| Rotor effect | The default eddy-current model solves the eddy currents in the rotor copper, and the change of TX inductance follows from them exactly (thin, perfectly conducting copper, centred rotor). With the older ideal-screen model the drop is an upper estimate, so the true frequency lies between "rotor away" and the predicted one. |
| Receiver voltage | The analyser's receiver signal (the same model as its angle error) in volts. The IC sets the TX voltage, so the ratio counts: V_RX / V_TX = M / L, with M the TX-to-receiver mutual inductance at the rotor angle where it is largest and L the TX inductance with the rotor. |
| Tank capacitors | Two capacitors C from each TX pin to ground (2 C from TX1 and 2 C from TX2), E12 C0G values just below and above the value needed. |

With the ideal-screen model the receiver voltage misses the crowding of the field at the copper edges. For long radial
sectors that is an exact 2-D problem: the fundamental of the field in the rotor plane is 1 − cos(π d) instead of
(2/π) sin(π d), where d is the metal fraction. The correction factor is 0.51, 0.65, 0.91, 1.14 and 1.57 at d = 0.2,
0.25, 1/3, 0.4 and 0.5. The eddy model computes it directly.

## 1.3 Not Included

- Parasitic capacitance (IC pins, coil, wiring; typically some 10 pF), which lowers the frequency a little.
- The IC's receiver input filter (100 pF per line in the Renesas reference designs), which raises the receiver voltage
  by a few per cent.
- Temperature (copper resistance rises 0.39 % per kelvin).

## 1.4 Receiver IC Limits

The limits are taken from the Renesas datasheets. Check your revision.

| Limit | IPS2550 | IPS2200 |
|---|---|---|
| Oscillator frequency | 2.0 to 5.6 MHz | 1.7 to 5.8 MHz |
| Minimum tank resistance (R_Peq) | 250 Ω | 100 Ω |
| TX voltage (peak to peak) | 6 to 11 V | 11 V |
| Receiver voltage (peak to peak) | 15 mV to 0.92 V (default AGC target 1.8 Vpp, gain boost off) | 5 mV to 5.2 V (input range; the usable part depends on the front-end gain) |

For the IPS2550 the receiver range is 8 mV to 0.47 V with the gain boost on, and 25 mV to 1.5 V with the AGC target at
3.0 Vpp. A receiver voltage closer than a factor of 2 to a limit is pointed out.

Set `RECEIVER_IC = None` in `Board_Parameters.py` to switch the checks off, and `TX_AMPLITUDE_VPP` if you know the
real TX voltage. See the [Parameter Reference](Parameter-Reference.md).

| Previous | Next |
|:---|---:|
| [Checks, Errors And Warnings](Checks-Errors-And-Warnings.md) | [Suggestive Analysis And Optimization](Suggestive-Analysis-And-Optimization.md) |
