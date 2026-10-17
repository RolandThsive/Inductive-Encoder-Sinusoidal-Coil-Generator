"""The generator package (Run, Checks, Stator, Rotor, Core).  Importing it puts the Parameters folder, which
sits next to the Generator folder, on the import path, so every module can `import Parameters`."""
import os
import sys

_PARAMETERS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Parameters")
if _PARAMETERS not in sys.path:
    sys.path.insert(0, _PARAMETERS)
