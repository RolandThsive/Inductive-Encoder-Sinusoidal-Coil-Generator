"""The dual generator package (Run, Checks, Stator, Rotor, Core).  Importing it puts two folders on the import
path: the Parameters folder next to it (Dual_Parameters.py and the seven Dual_..._Parameters.py files) and the
"Single Generator" folder next to "Dual Generator", so that the Single Generator's own package (`Generator`) can be
imported and used as it is.  Nothing in the Single Generator is changed, and Python is told not to write
__pycache__ folders, so running the dual generator leaves no files there either.

Every dual file name starts with Dual_, so no dual module can clash with the Single Generator's Parameters.py,
Board_Parameters.py, ... which its package also puts on the path."""
import os
import sys

sys.dont_write_bytecode = True

_DUAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # "Dual Generator"
_PARAMETERS = os.path.join(_DUAL, "Parameters")
SINGLE_GENERATOR = os.path.join(os.path.dirname(_DUAL), "Single Generator")
DUAL_GENERATOR = _DUAL

for _p in (_PARAMETERS, SINGLE_GENERATOR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if not os.path.isdir(os.path.join(SINGLE_GENERATOR, "Generator")):
    raise ImportError(f'the Single Generator was not found at "{SINGLE_GENERATOR}": the "Dual Generator" and '
                      f'"Single Generator" folders must sit next to each other (the dual generator builds every '
                      f'coil with the Single Generator\'s own code)')

import Generator  # noqa: E402,F401   (the Single Generator's package: it puts its own Parameters folder on the path)
