# Glossary

| Term | Meaning |
|---|---|
| **Stator** | The fixed board: the TX coil plus the SIN and COS receiver (RX) coils. |
| **Rotor** | The moving metal target: copper sectors on a second board, mounted copper side towards the stator. |
| **TX coil** | The transmit coil: concentric turns outside the RX band, driven by the IC's oscillator. |
| **RX coil** | A receiver coil. There are two: SIN and COS. Each is one closed series loop. |
| **Phase** | One of the four RX curves. Phases 0 and 2 (antiphase) make the SIN coil, phases 1 and 3 make the COS coil. |
| **Loop** | One electrical period: one full sine wave of the RX coils around the board. `LOOPS` periods per mechanical turn. |
| **Lobe** | One half of a loop's curve (positive or negative); a loop has two lobes. Not to be confused with a rotor sector. |
| **Sector** | One copper sector on the rotor. The rotor has as many sectors as the stator has loops. |
| **Electrical period / degrees** | One loop is 360 electrical degrees, which is 360 / `LOOPS` mechanical degrees. |
| **Unique range** | The angle over which the output is unambiguous: 360° / `LOOPS`. |
| **RX band** | The ring the RX coils swing across, between `INSIDE_RADIUS_MM` and `OUTSIDE_RADIUS_MM`. |
| **`r_base` and `A`** | The centre of the RX band and how far the coils swing in and out from it. |
| **Profile** | The shape rule of the RX curves: `equal_area`, `cosine_r` (limaçon) or `field_compensated`. |
| **Sub-coil** | One antiphase pair of curves. A coil can be built from 1 to 3 sub-coils spread apart by a split angle and wired in series. |
| **Split** | The electrical angle between sub-coils. |
| **Finger (bridging finger)** | A short radial run at the outer tip of an RX lobe that crosses over the TX turns so the coil can be broken out outside the TX ring. Setting: `RX_TABS`. |
| **Break style** | How TX turns make way for a finger: *staggered* (go-around) or *stitched* (windows). |
| **Go-around (staggered)** | Each TX turn stops before the finger and a bracket on another layer carries the current around it. |
| **Stitched windows** | Parallel TX only: the turns stop at vias on each side of the finger and the other layer carries the current past it. |
| **Chord** | One straight segment of the polyline that approximates a curve. Every RX curve, TX turn and rotor arc is a polyline of chords. |
| **Chord tolerance** | The largest gap, in mm, allowed between the true curve and its chord. RX, TX and rotor each have their own setting (`RX_`, `TX_`, `ROTOR_CHORD_TOLERANCE_MM`, default and minimum 0.001 mm). |
| **Auto steps** | The "auto" setting of `STEPS_PER_LOOP`, `TX_STEPS` and `ROTOR_ARC_STEPS_PER_SECTOR`: the generator picks the number of chords or points from the chord tolerance. A whole number is used exactly. |
| **Stepped / spiral** | TX turn shapes: concentric circles joined by short steps, or one smooth Archimedean spiral. |
| **Step angle** | The angle of the radial steps of a stepped TX turn, measured from the turn. |
| **Terminal via** | The via at the TX terminal that joins the inner tail to the first turn (or the two spirals of a series TX). |
| **Series / parallel TX** | Two TX layers wired end to end, or the same turns on both layers stitched together. |
| **Underpass** | The layer carrying the TX inner tail or the go-around brackets. |
| **Metal fraction (duty)** | The fraction of each rotor period that is copper. 0.5 = 180 electrical degrees. |
| **Air gap** | The distance from the stator top copper to the rotor copper. |
| **Tolerance window** | The range of air gap, rotor eccentricity, tilt and etching over which the analyser judges a design. |
| **Eddy-current model** | The default rotor model: each copper sector is a thin perfect conductor carrying its own eddy current. |
| **Ideal-screen model** | The older, faster rotor model: TX flux is simply removed wherever there is copper. |
| **Tank** | The TX coil plus its capacitors; the oscillator runs at the tank's resonant frequency. |
| **Receiver IC** | The chip that drives the TX and reads the RX coils, for example the Renesas IPS2550 or IPS2200. |
| **KiCad net** | A named electrical connection in the board. The coils use nets `TX`, SIN (`2`) and COS (`1`). |
| **DRC** | KiCad's design-rule check. It cannot see TX-to-TX shorts because all TX turns are one net. |
