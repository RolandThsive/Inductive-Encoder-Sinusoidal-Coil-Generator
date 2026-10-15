# 8. RX Profiles

Each RX coil is a pair of curves that weave around a centre radius `r_base` inside the RX band,
crossing it every half period. The two curves of a pair mirror each other (the `+` and the `−`
curve below), and the coil is the loop they form together. The shape of the weave is chosen by
`RX_PROFILE`.

The three profiles at a glance:

| Profile | Rule | Compensates for | Use it when |
|---|---|---|---|
| `equal_area` (default) | r² swings equally around r_base² | A uniform field | You want the default, well-behaved choice |
| `cosine_r` | r swings equally around the mean radius | A uniform field | You want to match the Renesas reference design, which follows this law |
| `field_compensated` | `equal_area`, bent by the modelled TX field | The non-uniform TX field | You know the air gap and board stack and want the model to correct for the field |

All three are selected with `RX_PROFILE` in `RX_Parameters.py`. As with the rest of the analysis,
the differences shown here come from the generator and its models. They have not yet been checked
on hardware.

## 8.1 Profile `cosine_r` (Limaçon)

This is the law the Renesas IPS2200 reference design follows. The radius itself swings
as a sine:

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

![RX Profile 1: cosine_r](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_1_cosine_r.png)

*RX Profile 1. The `cosine_r` profile for n = 4 loops, with `r_in` = 38 mm and `r_out` = 51 mm, so
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

![RX Profile 2: equal_area](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_2_equal_area.png)

*RX Profile 2. The `equal_area` profile for n = 4 loops on the same band as Profile 1. The dotted
grey line in the right panel is the middle of the band, 44.5 mm, for comparison.*

## 8.3 Profile `field_compensated`

The first two profiles assume that the TX field is the same everywhere in the RX band. In a real
board it is not: the field of the TX ring changes with the radius and with the height above the
board. The `field_compensated` profile starts from `equal_area` and bends the curves so that the
signal stays an exact sine in that non-uniform field. It uses `AIR_GAP_MM`, `PCB_THICKNESS_MM` and
the TX settings, so it changes when any of them changes.

### 8.3.1 The Bend Calculation

`equal_area` is the special case of a constant field: the cumulative weight up to the radius `r` is then
proportional to `r²`, and making `r²` swing as a sine makes that weight swing as a sine. `field_compensated`
keeps the same idea but uses the real field. Let `B(r)` be the axial field of the TX ring at the height of the
rotor and `G(r)` the cumulative weight of the band up to `r`:

$$
\Large G(r) = \int_{r_{in}}^{r} B(r') r' dr'
$$

The radius is then chosen so that `G` swings as a sine, which is the equal-area rule with `B` in place of a
constant:

$$
\Large G\big(r(\theta)\big) = \frac{G(r_{out})}{2} \big(1 + \sin(n \theta)\big)
\qquad\Longleftrightarrow\qquad
r(\theta) = G^{-1}\left(\frac{G(r_{out})}{2} \big(1 + \sin(n \theta)\big)\right)
$$

The field `B(r)` is the sum over the TX turns of the axial field of a circular current loop (the standard
closed form with the complete elliptic integrals `K` and `E`):

$$
\Large B(r) = \sum_{l}\sum_{j} w_l \frac{K(m) + \dfrac{R_j^{2} - r^{2} - z_l^{2}}{(R_j - r)^{2} + z_l^{2}} E(m)}{\sqrt{(R_j + r)^{2} + z_l^{2}}}
\qquad m = \frac{4 R_j r}{(R_j + r)^{2} + z_l^{2}}
$$

| Symbol | Meaning |
|---|---|
| `G(r)` | Cumulative weight of the band from `r_in` to `r`. Only the ratio `G(r) / G(r_out)` is used, so its absolute size does not matter. `G(r_in)` = 0 |
| `B(r)` | Axial field of the TX ring at radius `r`, (only its shape across the band matters, not its absolute size, so constant factors such as the current cancel out) |
| `r_in`, `r_out` | Inside and outside radius of the RX band |
| `R_j` | Radius of TX turn `j` |
| `l` | A TX layer that carries turns; `w_l` is its share of the TX current (1 for one layer, 1 for each of the two layers of a series TX, 0.5 for each of the two layers of a parallel TX) |
| `z_l` | Height of the rotor above TX layer `l`: `AIR_GAP_MM` plus the depth of that layer below the top copper (Top 0, Inner 1 0.2 mm, Inner 2 `PCB_THICKNESS_MM` − 0.2 mm, Bottom `PCB_THICKNESS_MM`; a board thinner than 0.4 mm puts the inner layers at thirds) |
| `K(m)`, `E(m)` | Complete elliptic integrals of the first and second kind with parameter `m` |
| `n·θ` | Electrical angle, as above |

![RX Profile 4: Equal area vs field compensated](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/Wiki_Modifications/docs/images/rx_profile_4_equal_area_vs_field_compensated.png)

*RX Profile 4. Computed by the generator for the default band (16.2 to 22.4 mm) with a 3-turn TX coil. A: the TX
field `B(r)` is not constant over the band, which `equal_area` assumes. B: for `sin(nθ) = 0.5` the target weight is
`G = 0.75`; reading it off each curve gives a different radius (here 0.12 mm apart). C: repeating this for every angle
gives the two boundaries; they differ by up to 0.28 mm, and that difference is the compensation.*

The generator evaluates `B(r)` on 4001 points between `r_in` and `r_out`, integrates it step by step (trapezoid
rule) to get `G`, and finds `r(θ)` by interpolating the inverse of `G`. The curves therefore depend on
`AIR_GAP_MM`, `PCB_THICKNESS_MM`, the TX turn radii, the TX layers and the TX wiring. This is a model of
the field, not a measurement, and it has not yet been checked on hardware.

## 8.4 Comparing The Three Profiles

![RX Profile 3: The three profiles](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/rx_profile_3_comparison.png)

*RX Profile 3. The same 4-loop board built with each profile, and the radius of one curve pair
over one electrical period (90°). `equal_area` and `cosine_r` lie almost on top of each other;
`field_compensated` departs from them by up to about 1.5 mm in radius at some angles.*

| Previous | Next |
|:---|---:|
| [Induction Encoding - Rotary Working Principle](Working-Principle.md) | [TX Profiles](TX-Profiles.md) |
