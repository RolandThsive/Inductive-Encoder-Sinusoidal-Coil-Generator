# Theory And References

> [!WARNING]
> Every model in this project is unvalidated against hardware. Hardware testing and model validation are the
> project's immediate next steps (see [Immediate Next Steps](Immediate-Next-Steps.md)).

## Method

| Topic | Where | What is used |
|---|---|---|
| Field of a current loop | `CoilElectrics.py` | Axial field of a circular loop with complete elliptic integrals K and E. |
| TX inductance | `CoilElectrics.py` | Ring self-inductance (geometric mean distance of a w × t trace) plus Maxwell's mutual inductance of coaxial circles; checked against the Neumann integral within 2 %. |
| Real copper in 3-D | `RealCopper.py` | Each RX coil is split into one closed loop per layer plus exact chord remainders (Biot–Savart of straight pieces); the TX is taken from its real copper with the DC current split of the copper network; direct TX-to-RX coupling by the Neumann double line integral. Agrees with exact Biot–Savart within 2 to 3.5 % rms. |
| Rotor eddy currents | `RotorEddyModel.py` | Each copper sector is a thin, perfect conductor (at 2 to 5 MHz the skin depth of copper, 30 to 45 µm, is about one copper thickness). A stream function describes the current; the copper is cut into cells, finest at the edges; the normal field of every cell loop is computed exactly and solved so the total normal field is zero in every cell. A coil's flux follows by reciprocity. |
| Checks of the eddy model | `RotorEddyModel.py` | A thin disc in a uniform field (exact; dipole moment within 0.3 to 0.8 %), long narrow sectors against the exact 2-D strip result (within 1 to 2 %), the off-centre path against the centred one, and grid convergence (signal within about 3 %, angle errors within about 10 %). |
| Sub-coil harmonics | `RX_Parameters.py` | Two sub-coils split by *d*: signal × 2·cos(*d*/2), harmonic *h* × 2·cos(*h*·*d*/2). |
| Crowding at copper edges | `CoilElectrics.py` | For long radial sectors the exact 2-D result: fundamental 1 − cos(π*d*) instead of (2/π) sin(π*d*). |

The [RX profiles](RX-Profiles.md) explain the three curve laws, and [Working Principle](Working-Principle.md) the
sensor as a whole.

## Sources Named In The Code

These are the sources the parameter files and docstrings refer to. **None of them has been opened for this wiki**, so
what is said about them below comes only from how the code cites them.

| Source | Cited for |
|---|---|
| Renesas IPS2200 reference design | The `cosine_r` (limaçon) RX law, measured from its layout; distributed windings with two sub-coils split by 45°; TX on layers 1 and 3 of a 4-layer board with RX on 1 and 2; the 100 pF receiver input filter; rotor copper running over the TX turns. |
| Renesas IPS2550 and IPS2200 datasheets | The receiver IC limits in [Electrical Estimate](Electrical-Estimate.md) (oscillator range, minimum tank resistance, TX and RX voltages). The limits should be checked against your datasheet revision. |
| Hoxha et al., *Sensors*, 2022, Fig. 2 | The 2-layer series TX layout and the go-around ("staggered") way of making TX turns give way to RX fingers. |

If you can supply any of these, or papers on inductive position-sensor coil shaping, error compensation or rotor
eddy-current design, please open an issue or contact the author.
