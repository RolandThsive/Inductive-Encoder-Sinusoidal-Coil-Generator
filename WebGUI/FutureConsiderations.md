# Future Considerations

Ideas kept for later versions of the Web GUI. Nothing here is active now.

## Output Settings In Advanced

The Board tab of Advanced had an **Output** block, titled "Output (Fixed In The Web Version)". It showed six
parameters from `Board_Parameters.py`, read only:

| Parameter | What It Sets |
| --- | --- |
| `OUTPUT_DIR` | The output folder of a desktop run |
| `STATOR_FILE` | The stator file name |
| `ROTOR_FILE` | The rotor file name |
| `CENTER_X_MM`, `CENTER_Y_MM` | Where the board centre sits on the KiCad page |
| `PAGE_SIZE_MM` | The KiCad page size |

It is hidden for now because none of these can be changed on the web: the zip and file names come from the run
name, and the boards keep the default centre and page.

The code is still in place:

- `WebGUI.js`: `SHOW_OUTPUT_GROUP = false` hides the block. Set it to `true` to show it again.
- `WebGenerator.py`: `READ_ONLY` keeps these six read only: imports ignore them and exported files keep their starting values.
- `WebGUI.js`: `GROUP_TITLES["Output"]` is the block's title.

To make them editable later: remove the names from `READ_ONLY`, give the centre and page size steppers, and
decide how a custom `STATOR_FILE` / `ROTOR_FILE` should name the files inside the zip and the Download Stator /
Download Rotor buttons.
