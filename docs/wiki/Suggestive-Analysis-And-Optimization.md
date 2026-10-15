# 18. Suggestive Analysis And Optimization

The analyser and optimizer are optional. They never change a board or a parameter file.

- **AnalyzeCoil** builds the stator and rotor in memory and simulates both receiver coils while the
  rotor turns. It reports the signal, offset, SIN/COS match, harmonics and angle error, for the
  nominal design and for a tolerance window of air gap, rotor eccentricity, tilt and etching.
- **True-3D Copper Model.** Each coil is modelled from its real copper, layer by layer, using
  Biot–Savart. It agrees with exact Biot–Savart within 2–3.5 % rms.
- **Rotor Eddy-Current Model.** Each copper lobe is treated as a thin conductor carrying its own
  eddy current, so copper edges and copper over the TX are judged physically.
- **OptimizeCoil** searches the RX profile, sub-coils, split, rotor metal fraction and rotor outer
  edge, and ranks the results by the worst angle error over the tolerance window. It prints the
  parameter lines to change.

**Example.** The optimizer was run on a 1-loop stator (bore radius 18 mm, outer radius 32 mm) with
`OptimizeCoil.py` with `ECCENTRICITY_MM` and `TILT_DEG` set to 0 (air gap and metal fraction tolerances only, a much faster run). It suggested two sub-coils split by 50° and rotor copper that ends just
over the outermost TX turn:

| Design | Worst-Case Angle Error (Air Gap 1 ± 0.2 mm) | Relative Signal | RX Voltage (IPS2550, 6–11 Vpp TX) |
|---|---|---|---|
| Start: 1 sub-coil, `equal_area` profile | 0.66° electrical | 1.00 | 106–194 mVpp |
| Suggested: 2 sub-coils at 50°, copper overhang −0.25 mm | 0.18° electrical | 1.79 | 189–346 mVpp |

> [!NOTE]
> The numbers in this example were made with the earlier, coarser chord defaults. The predicted angle error depends on the chord count (for example 0.777° at 160 chords per loop against 0.456° at 1024 in one test), so older optimizer rankings are superseded. Re-run the optimizer with the current defaults before trusting old numbers.

![Analysis 1: Optimizer Comparison](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/analysis_1_optimizer.png)

*Analysis 1. The starting design, the optimizer's suggestion, and their angle error over one turn at
the nominal air gap. Model results only.*

| Previous | Next |
|:---|---:|
| [Electrical Estimate](Electrical-Estimate.md) | [Project Output Organization](Project-Output-Organization.md) |
