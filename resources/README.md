# resources

Files that more than one generator uses, outside the generator folders.

- `SilkscreenFont.py`: the stroke font of the silkscreen suggestions (lead names drawn as lines, no KiCad text).
  Capitals, digits and a few signs on a 4 x 6 grid, drawn for this repository; see the docstring for the two
  functions (`layout`, `width`).  Used by the Dual Generator's `Dual_LeadCutting_SilkscreenSuggestion.py`.
- `RepresentativeSVGMaker.py`: a picture of a generated board for people: the stator on the left, the rotor on the
  right, layer colours, a title and a legend.  Copper under another layer is made visible (wider stator traces,
  dashed rotor outlines).  Writes `<folder name>_Representative.svg`.
- `ActualSVGMaker.py`: the copper of a generated board as it is, 1:1 in mm, with no text and nothing widened; one
  group per layer (`F_Cu`, `Inner_1`, `Inner_2`, `B_Cu`, plus `Edge_Cuts`) for the stator and for the rotor.  Writes
  `<folder name>_Actual.svg`.

  Both read only `Stator.kicad_pcb` and `Rotor.kicad_pcb`, need nothing but Python 3, and run on a folder:
  `python resources/ActualSVGMaker.py "Single Generator/Output/<folder>"`.  The Single and Dual generators call both
  at the end of every run that writes the two boards; when one is missing or fails, the run prints a warning and the
  boards are not affected.
