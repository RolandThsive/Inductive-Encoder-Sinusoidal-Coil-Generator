# 3. Getting Started

The generator is pure Python 3 with numpy (matplotlib is optional, for plots). There is also a
[Web Tool](Web-Tool.md) that needs no installation.

## 3.1 Install

```bash
pip install numpy matplotlib
```

## 3.2 First Run

1. Open `Parameters/` and look at the four files you can edit: `Board_Parameters.py`, `RX_Parameters.py`,
   `TX_Parameters.py` and `Rotor_Parameters.py`. The [Parameter Reference](Parameter-Reference.md) explains every
   setting. The defaults already build a board.
2. Check the parameters without writing anything:

   ```bash
   python Generator/RunCoilGenerator.py --check
   ```

3. Generate the boards:

   ```bash
   python Generator/RunCoilGenerator.py
   ```

4. Open `Stator.kicad_pcb` and `Rotor.kicad_pcb` from the new folder in `Output/` with KiCad 7, 8, 9 or 10. See
   [KiCad Compatibility](KiCad-Compatibility.md).

## 3.3 All Commands

```bash
python Generator/RunCoilGenerator.py              # Check, then write Stator + Rotor
python Generator/RunCoilGenerator.py --check      # Check only, write nothing
python Generator/RunCoilGenerator.py --strict     # Treat warnings as errors
python Analyser_And_Optimizer/AnalyzeCoil.py      # Analyse the current parameters
python Analyser_And_Optimizer/OptimizeCoil.py     # Search better settings (set in OptimizerParameters.py)
```

Every program runs from any folder; it finds the other folders itself. A run never overwrites anything: if the output
folder name already exists, `__1`, `__2` and so on are added. See
[Project Output Organization](Project-Output-Organization.md).

## 3.4 What Happens In A Run

1. The parameters are checked ([Checks, Errors And Warnings](Checks-Errors-And-Warnings.md)).
2. The stator is built and checked.
3. The rotor is built and checked.
4. The [electrical estimate](Electrical-Estimate.md) is printed and checked against the receiver IC.
5. With `--strict` or `--check`, the run stops or continues as requested.
6. The boards and `Parameters.txt` (the summaries, every value used, and copies of the parameter files) are written.

Every board carries a filled-in KiCad title block. There is no silkscreen and there are no terminals or pads: you
break the coils out where you like.

> [!NOTE]
> Every model and estimate in this project is unvalidated against hardware. Test boards are ordered and have not
> been measured yet.

## 3.5 Next

- Pick the loop count for your use: [Choosing A Rotor And Stator](Choosing-A-Rotor-And-Stator.md).
- Understand the features: [Stator Features](Stator-Features.md), [Rotor Features](Rotor-Features.md),
  [Board Features](Board-Features.md).
- Check and improve a design: [Suggestive Analysis And Optimization](Suggestive-Analysis-And-Optimization.md).

| Previous | Next |
|:---|---:|
| [Contents](Contents.md) | [Web Tool](Web-Tool.md) |
