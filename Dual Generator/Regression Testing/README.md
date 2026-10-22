# Regression Testing (Dual Generator)

Runs the Dual Generator the way a user does, in this process, with parameter values set in memory, and checks what
it prints and what it writes.  The parameter files, the Output folder and the Single Generator are never touched.

    python "Dual Generator/Regression Testing/run_regression.py"            everything (about 10 minutes)
    python "Dual Generator/Regression Testing/run_regression.py" -v         one line per test
    python "Dual Generator/Regression Testing/run_regression.py" -k checker only the checker cases (-k silkscreen, ...)
    python "Dual Generator/Regression Testing/run_regression.py" --update-references
                                                                            rewrite References/ from the generator as it is

Needs what the generator needs: Python 3.8 or newer and numpy.  Exit code 0 when every test passed.

| file | what it tests |
|---|---|
| `test_checker.py` | the four DUAL_MODE layouts and every way they can be set wrongly, the fixed file, the dual rules (nets, frequencies, layers, rings), the Single Generator's own checks on each set, strict mode; each case says the return code and the lines the run must print |
| `test_boards.py` | every board case written and compared with `References/` (stator, rotor, record), numbers within 1e-5 |
| `test_invariants.py` | what must hold for every written dual board: the file format, four layers, six nets, copper inside the edges on the layers each set asked for, the clearance between nets, set 1 inside set 2 by the recorded gap, closed RX coils, TX terminals at TERMINAL_1_DEG / TERMINAL_2_DEG, the two rotor rings, the record; the same values written twice are identical |
| `test_silkscreen.py` | the lead-cutting silkscreen of both sets: six suggestions, names with the set number, breaks near each set's terminal, via sites with room, lettering off the vias, sides and labels options |
| `test_units.py` | the set parameters handed to the Single Generator, the layout modes, folder names, the guard that the dual files supply every name the Single Generator knows |
| `harness.py` | loads the generator, applies overrides, runs it, keeps the written boards per case (`BOARD_CASES`) |
| `References/` | the frozen output of each board case (`.kicad_pcb.gz`, `Parameters.txt`) |

The shared parser and measuring code is `resources/RegressionTools.py` (used by both generators' suites).

When a test in `test_boards.py` fails, the generator writes something different from what it wrote when the
references were frozen.  Read the printed differences; if the change is intended, run `--update-references` and
commit the new `References/` with the change.  The other tests do not depend on the references.
