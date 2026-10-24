# 3. Getting Started

The generator is pure Python 3 and needs only numpy. There is also a
[Web Tool](Web-Tool.md) that needs no installation.

## 3.1 Install

```bash
python -m pip install -r requirements.txt
```

## 3.2 First Run

1. Open `Single Generator/Parameters/` and look at the files you can edit: `Board_Parameters.py`, `RX_Parameters.py`,
   `TX_Parameters.py`, `Rotor_Parameters.py`, `IC_Parameters.py` and `SilkScreenSuggestion_Parameters.py`. The
   [Parameter Reference Single Generator](Parameter-Reference-Single-Generator.md) explains every setting. The defaults
   already build a board.
2. Go to the `Single Generator` folder and check the parameters without writing anything:

   ```bash
   cd "Single Generator"
   python Generator/Run/RunCoilGenerator.py --check
   ```

3. Generate the boards:

   ```bash
   python Generator/Run/RunCoilGenerator.py
   ```

4. Open `Stator.kicad_pcb` and `Rotor.kicad_pcb` from the new folder in `Single Generator/Output/` with KiCad 7, 8, 9 or 10. See
   [KiCad Compatibility](KiCad-Compatibility.md).

## 3.3 All Commands

```bash
python Generator/Run/RunCoilGenerator.py              # Check, then write Stator + Rotor
python Generator/Run/RunCoilGenerator.py --check      # Check only, write nothing
python Generator/Run/RunCoilGenerator.py --stator     # Only the stator
python Generator/Run/RunCoilGenerator.py --rotor      # Only the rotor (the stator geometry is built but not written)
python Generator/Run/RunCoilGenerator.py --no-color   # Plain text, no colours
```

Whether a warning about the finished boards (a clearance, the board edge, the page, the rotor) stops the run is not a command-line option any more: set
`GENERATOR_MODE` to `"strict"` in `Board_Parameters.py` (the default `"normal"` writes the boards anyway).
Colours: red = error (nothing is written), yellow = warning, green = success.

The analyser and optimizer are not on main. They are under construction on the [`analyser_and_optimizer` branch](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/tree/analyser_and_optimizer).

The generator runs from any folder; it finds the other folders itself. A run never overwrites anything: if the output
folder name already exists, `__1`, `__2` and so on are added. See
[Project Output Organization](Project-Output-Organization.md).

## 3.4 What Happens In A Run

1. The parameters are checked ([Checks, Errors And Warnings](Checks-Errors-And-Warnings.md)).
2. The RX coils and their fingers are built, then the TX coil with its terminal where it keeps the largest gap from the RX copper (with `RX_TABS = "single"`, as close to the two fingers as the clearance allows). The board is turned so that the terminal sits at 0° (to the right), and the finished copper is checked.
3. The rotor is built and checked.
4. The [electrical estimate](Electrical-Estimate.md) is printed and checked against the receiver IC limits in `IC_Parameters.py`.
5. The run decides: any error stops it (nothing is written); with `GENERATOR_MODE = "strict"` every warning about the finished boards counts as an error, and `--check` stops here on purpose.
6. The boards and `Parameters.txt` (the summaries, every value used, and copies of the parameter files) are written.
7. Then a lead-cutting suggestion is drawn on the silkscreen of the stator: where to break each RX coil and where the
   TX ends get their vias. It changes no copper and never stops a run; the coordinates are printed and added to
   `Parameters.txt`. See [Silkscreen](Silkscreen.md).
8. Last, two SVG pictures of the boards are drawn into the same folder: `<folder name>_Representative.svg` to look
   at, and `<folder name>_Actual.svg` with the copper 1:1 in mm. A picture that cannot be made is only a warning; the
   boards are not affected. See [Output Pictures](Output-Pictures.md).

Every board carries a filled-in KiCad title block. There are no terminals or pads: you break the coils out yourself,
where the silkscreen suggests or wherever you like.

> [!NOTE]
> Every model and estimate in this project is unvalidated against hardware. Test boards are ordered and have not
> been measured yet.

## 3.5 The Dual Generator

The Dual Generator builds two coil sets on one stator (a coarse inner set and a fine outer set, each with its own IC)
and one rotor disc with two rings. It uses the Single Generator's own code, so both folders must stay next to each
other. Its settings are the files in `Dual Generator/Parameters/` (`Dual_Board_Parameters.py`, `Dual_RX1` / `Dual_RX2`,
`Dual_TX1` / `Dual_TX2`, `Dual_Rotor1` / `Dual_Rotor2`, `Dual_IC1` / `Dual_IC2` and
`Dual_SilkScreenSuggestion_Parameters.py`; `Dual_Fixed_Parameters.py` is not to be changed). The defaults build a
1x / 16x board.

```bash
cd "Dual Generator"
python Dual_Generator/Checks/Dual_CheckParameters.py       # Check the parameters only
python Dual_Generator/Run/Dual_RunCoilGenerator.py         # Check, then write Stator + Rotor
python Dual_Generator/Run/Dual_RunCoilGenerator.py --check # Check only, write nothing
```

The options `--stator`, `--rotor` and `--no-color` work as for the Single Generator. Each run writes a new
`DualCoil_...` folder in `Dual Generator/Output/`, with the boards, `Parameters.txt` and the two
[output pictures](Output-Pictures.md). Start with the
[Quick Guide To Parameters Selections - Dual Generator](Quick-Guide-To-Parameters-Selections-Dual-Generator.md).

## 3.6 Next

- Pick the loop count for your use: [Choosing A Rotor And Stator](Choosing-A-Rotor-And-Stator.md).
- Understand the features: [Stator Features](Stator-Features.md), [Rotor Features](Rotor-Features.md),
  [Board Features](Board-Features.md), [Silkscreen](Silkscreen.md), and the same for the
  [Dual Generator](Stator-Features-Dual-Generator.md).
- Check and improve a design (analysis and optimization are under construction): [Suggestive Analysis And Optimization](Suggestive-Analysis-And-Optimization.md).

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [Contents](Contents.md) | [Web Tool](Web-Tool.md) |
