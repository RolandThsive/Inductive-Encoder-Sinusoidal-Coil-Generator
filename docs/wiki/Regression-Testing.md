# 29. Regression Testing

Both generators have a regression test suite that runs the generator the way a user does, with parameter values set in
memory, and checks what it prints and what it writes. The parameter files, the `Output` folders and the generators are
never touched by a test run. The suites need what the generators need: Python 3.9 or newer and NumPy (see requirements.txt).

## 29.1 Running The Tests

From the root of the repository:

```bash
python "Single Generator/Regression Testing/run_regression.py"      # everything, about 3 minutes
python "Dual Generator/Regression Testing/run_regression.py"        # everything, about 10 minutes
```

| Option | Effect |
|---|---|
| `-v` | One line per test |
| `-k <word>` | Only the tests whose name contains the word, for example `-k checker` or `-k silkscreen` |
| `--update-references` | Rewrite `References/` from the generator as it is now |
| `--keep` | Keep the temporary output folder the boards are written to |

The exit code is 0 when every test passed.

## 29.2 What Is Tested

Each suite has the same files:

| File | Single Generator | Dual Generator |
|---|---|---|
| `test_checker.py` | One value of every kind set wrongly, missing and unknown names, inactive values left alone, the conflicts between values (vias, layers, nets, edges, fingers, rotor), the geometry that stops a run, strict mode. Each case states the return code and the lines the run must print | The four `DUAL_MODE` layouts and every way they can be set wrongly, the fixed file, the dual rules (nets, frequencies, layers, rings), the Single Generator's own checks on each set, strict mode |
| `test_boards.py` | Every board case written and compared with `References/` (stator, rotor, record), numbers within 1e-5; its folder must hold exactly these three files and the two [output pictures](Output-Pictures.md) | The same, for the dual board cases |
| `test_invariants.py` | What every written board must obey: the file format, the layer table, the nets, copper inside the edges with the right widths, the clearance between nets, closed RX coils, the TX in one piece with its terminal at 0°, the rotor sectors, the record; the same values written twice are identical | The same for a dual board: four layers, six nets, set 1 inside set 2 by the recorded gap, the TX ends at `TERMINAL_1_DEG` / `TERMINAL_2_DEG`, the two rotor rings |
| `test_silkscreen.py` | The lead-cutting silkscreen: three suggestions on both sides, via sites with room, lettering off the vias and mirrored on the bottom, the settings with their fallbacks, the font, the name placer | Six suggestions, names with the set number, breaks near each set's terminal, sides and labels options |
| `test_cli.py` | The generator started as a script in a fresh Python process, from its folder and from elsewhere, with `--check`, `--help` and a bad option | The same, plus the checker on its own and the promise that a dual run leaves no `__pycache__` in the Single Generator |
| `test_units.py` | The folder names, the KiCad writer, the report and colour classes, the parameter and geometry helpers | The set parameters handed to the Single Generator, the layout modes, the folder names, and a guard that the dual files supply every name the Single Generator knows |

`harness.py` loads the generator, applies the overrides, runs it and keeps the written boards of each case
(`BOARD_CASES`). `References/` holds the frozen output of each board case (`.kicad_pcb.gz` and `Parameters.txt`).

The parsing and measuring code both suites share is `resources/RegressionTools.py`. It reads the written `.kicad_pcb`
back and measures it independently of the generator: the smallest clearance between nets on a cell grid, the
connectivity of each net, the copper extent of each layer, and a token-by-token comparison with the references.

## 29.3 On Every Pull Request

The workflow `.github/workflows/regression.yml` runs both suites on every pull request (opened, updated or reopened), on
Ubuntu and on Windows, with Python 3.9 and 3.13, so the boards come out the same on every machine the generators are used
on. The checks read, for example, "Single Generator (ubuntu-latest, Python 3.13)". A push to a branch without a pull
request runs nothing, and a new push to a pull request cancels the run still going for it.

## 29.4 When A Test Fails

When a test in `test_boards.py` fails, the generator writes something different from what it wrote when the references
were frozen. Read the printed differences; if the change is intended, run `--update-references` and commit the new
`References/` with the change. The other tests do not depend on the references.

A change that adds a feature brings its tests with it, in the same commit:

1. A case in `test_checker.py` for every new rule and every new error or warning text (one case that triggers it, one
   that does not). A new parameter gets a case with it set and one with it missing.
2. A case in `harness.BOARD_CASES` when the feature changes the copper, the rotor or the record, so its output is frozen
   in `References/` from then on.
3. An invariant in `test_invariants.py` when there is a rule the written files must always obey.
4. A unit test in `test_units.py` for a new helper.
5. `--update-references` last, after every printed difference has been read and found intended.

The suite cannot notice a feature that arrived without a test; that part is the review's job.

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [KiCad Compatibility](KiCad-Compatibility.md) | [Glossary](Glossary.md) |
