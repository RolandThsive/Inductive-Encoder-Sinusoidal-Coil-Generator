# RX Profiles

Each RX coil is a pair of curves that weave around a centre radius `r_base` inside the RX band,
crossing it every half period. The two curves of a pair mirror each other (the `+` and the `−`
curve below), and the coil is the loop they form together. The shape of the weave is chosen by
`RX_PROFILE`.

## Profile `cosine_r` (Limaçon)

This is the law the Renesas IPS2200 reference design follows. The radius itself swings
as a sine:

$$
\Large r(\theta) = r_{base} \pm A\,\sin(n\,\theta)
$$

| Symbol | Meaning |
|---|---|
| `r(θ)` | Radius of the copper trace at the mechanical angle `θ`, in mm |
| `θ` | Mechanical angle around the board, 0° to 360° |
| `n` | Number of loops (`LOOPS`): electrical periods per mechanical turn |
| `n·θ` | Electrical angle. One full sine of the weave per `360°/n` of rotation |
| `r_base` | Centre line of the band, `(r_out + r_in) / 2`. The curves cross it every half period |
| `A` | Amplitude, the swing around `r_base`, `(r_out − r_in) / 2`. The curves touch `r_in` and `r_out` at their peaks |
| `±` | The two curves of one pair. `+` is the rising curve, `−` the mirrored one |
| `r_in`, `r_out` | Inside and outside radius of the RX band (`INSIDE_RADIUS_MM`, `OUTSIDE_RADIUS_MM`) |

![RX Profile 1: cosine_r](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_1_cosine_r.png)

*RX Profile 1. The `cosine_r` profile for n = 4 loops, with `r_in` = 38 mm and `r_out` = 51 mm, so
`r_base` = 44.5 mm and `A` = 6.5 mm. Left: top view. Right: the same curves unrolled.*

## Profile `equal_area` (Default)

Here the **square** of the radius swings as a sine, so that for a uniform field the flux picked
up by a single curve follows an exact sine of the rotor position:

$$
\Large r^{2}(\theta) = r_{base}^{2} \pm A\,\sin(n\,\theta)
$$

| Symbol | Meaning |
|---|---|
| `r(θ)` | Radius of the copper trace at the mechanical angle `θ`, in mm |
| `θ`, `n`, `n·θ` | Same as above |
| `r_base²` | The centre of the swing, `(r_out² + r_in²) / 2`. So `r_base` = √`r_base²` is the radius whose circle sits in the middle of the band **in area**, not in length |
| `A` | Amplitude of the swing in r², `(r_out² − r_in²) / 2`, in mm². It has the unit of an area, not of a length |
| `±` | The two mirrored curves of one pair |

For `r_in` = 38 mm and `r_out` = 51 mm, `r_base` = 44.97 mm (a little outside the middle of the
band, 44.5 mm) and `A` = 578.5 mm². The weave is therefore slightly lopsided in radius, 6.0 mm
outwards and 7.0 mm inwards.

![RX Profile 2: equal_area](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_2_equal_area.png)

*RX Profile 2. The `equal_area` profile for n = 4 loops on the same band as Profile 1. The dotted
grey line in the right panel is the middle of the band, 44.5 mm, for comparison.*

## Profile `field_compensated`

The first two profiles assume that the TX field is the same everywhere in the RX band. In a real
board it is not: the field of the TX ring changes with the radius and with the height above the
board. The `field_compensated` profile starts from `equal_area` and bends the curves so that the
signal stays an exact sine in that non-uniform field. It uses `AIR_GAP_MM`, `PCB_THICKNESS_MM` and
the TX settings, so it changes when any of them changes.

## Comparing The Three Profiles

![RX Profile 3: The three profiles](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_3_comparison.png)

*RX Profile 3. The same 4-loop board built with each profile, and the radius of one curve pair
over one electrical period (90°). `equal_area` and `cosine_r` lie almost on top of each other;
`field_compensated` departs from them by up to about 1.5 mm in radius at some angles.*

| Profile | Rule | Compensates for | Use it when |
|---|---|---|---|
| `equal_area` (default) | r² swings equally around r_base² | A uniform field | You want the default, well-behaved choice |
| `cosine_r` | r swings equally around the mean radius | A uniform field | You want to match the Renesas reference design, which follows this law |
| `field_compensated` | `equal_area`, bent by the modelled TX field | The non-uniform TX field | You know the air gap and board stack and want the model to correct for the field |

All three are selected with `RX_PROFILE` in `RX_Parameters.py`. As with the rest of the analysis,
the differences shown here come from the generator and its models. They have not yet been checked
on hardware.
