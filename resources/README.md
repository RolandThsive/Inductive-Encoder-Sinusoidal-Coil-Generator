# resources

Files that more than one generator uses, outside the generator folders.

- `SilkscreenFont.py`: the stroke font of the silkscreen suggestions (lead names drawn as lines, no KiCad text).
  Capitals, digits and a few signs on a 4 x 6 grid, drawn for this repository; see the docstring for the two
  functions (`layout`, `width`).  Used by the Dual Generator's `Dual_LeadCutting_SilkscreenSuggestion.py`.
