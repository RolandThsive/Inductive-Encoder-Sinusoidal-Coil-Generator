# 8. RX Profiles

Each RX coil is a pair of curves (with `RX_SUBCOILS` > 1, several pairs in series) that weave around a centre radius `r_base` inside the RX band,
crossing it every half period. The two curves of a pair mirror each other (the `+` and the `−`
curve below), and the coil is the loop they form together. The shape of the weave is chosen by
`RX_PROFILE`.

Two profiles can be selected now; a third is research in progress:

| Profile | Rule | Compensates for | Use it when |
|---|---|---|---|
| `equal_area` (default) | r² swings equally around r_base² | A uniform field | You want the default, well-behaved choice |
| `cosine_r` | r swings equally around the mean radius | A uniform field | You want the radius itself to follow a sine |
| `field_compensated` | `equal_area`, bent by the modelled TX field | The non-uniform TX field | Research underway (not selectable in V18) |

`RX_PROFILE` in `RX_Parameters.py` accepts `equal_area` and `cosine_r`. As with the rest of the analysis,
the differences shown here come from the generator and its models. They have not yet been checked
on hardware.

## 8.1 Profile `cosine_r` (Limaçon)

With one loop (n = 1) the formula below draws a limaçon, also called the limaçon of Pascal or Pascal's snail: the
curve traced by a point fixed to a circle while that circle rolls around the outside of another circle of the same
radius (RX Profile 1). With more loops the same formula puts n waves around the turn instead of one, and the curve is
no longer a limaçon.

![RX Profile 1: Limaçon](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_limacon.gif)

*RX Profile 1. The orange circle rolls around the grey circle; both have radius 1. The blue point, fixed to the
orange circle 0.5 from its centre, traces a limaçon (blue). Measured from the red +, which sits 0.5 to the right of
the grey centre, the curve is r(θ) = 2 − cos θ. That is the `+` curve of the formula below for one loop, with
`r_base` = 2 and `A` = 1, turned a quarter turn anticlockwise.*

The radius itself swings as a sine:

$$
\Large r(\theta) = r_{base} \pm A \sin(n \theta)
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

![RX Profile 2: cosine_r](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_1_cosine_r.png)

*RX Profile 2. The `cosine_r` profile for n = 4 loops, with `r_in` = 38 mm and `r_out` = 51 mm, so
`r_base` = 44.5 mm and `A` = 6.5 mm. Left: top view. Right: the same curves unrolled.*

## 8.2 Profile `equal_area` (Default)

Here the **square** of the radius swings as a sine, so that for a uniform field the flux picked
up by a single curve follows an exact sine of the rotor position:

$$
\Large r^{2}(\theta) = r_{base}^{2} \pm A \sin(n \theta)
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

![RX Profile 3: equal_area](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_2_equal_area.png)

*RX Profile 3. The `equal_area` profile for n = 4 loops on the same band as Profile 2. The dotted
grey line in the right panel is the middle of the band, 44.5 mm, for comparison.*

The name refers to area. Picture a line from the board centre to the curve, turning once around the board. Each
degree it turns sweeps a thin slice whose area is proportional to r². So with this profile, the area added outside
the `r_base` circle and the area missing inside it are equal over every electrical period (RX Profile 4).

![RX Profile 4: equal_area sweep](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_equal_area.gif)

*RX Profile 4. The rising (`+`) curve of RX Profile 3, drawn by a line from the centre turning once around the
board. Left: top view; the red dashed circle is `r_base`, the grey circles `r_in` and `r_out`. The areas outside
`r_base` (purple) and inside it (orange) are equal over each electrical period of 90°: the counter at the bottom shows
purple minus orange and returns to 0 every 90°. Right: r² over the turn, an exact sine around `r_base²`.*

## 8.3 Profile `field_compensated`

**Research underway.** It was removed from the generator in V18 and returns when the field model does.

## 8.4 Comparing The Profiles

![RX Profile 5: The two profiles](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_3_comparison.png)

*RX Profile 5. The same 4-loop board (board edges 30 / 50 mm, RX only, the TX is not drawn) built with each of the two profiles, and the radius of the SIN curves over one electrical period (90°). The two profiles lie almost on top of each other.*

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [Induction Encoding - Rotary Working Principle](Working-Principle.md) | [TX Profiles](TX-Profiles.md) |
