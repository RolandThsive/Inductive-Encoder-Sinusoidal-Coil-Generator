"""
Conflict.py  -  what a check finds and how it is reported: ParameterConflict (two or more settings that cannot both
hold, with the explanation), the Report that collects every finding (error / warning / info) and prints it, and the
console colours.  A conflict is printed as

    ERROR   INNER_EDGE_RADIUS_MM conflicts with OUTER_EDGE_RADIUS_MM
            the board's inner radius (15 mm) cannot be larger than its outer radius (12 mm)

Raised by the checks (ParameterRules.py, ConflictRules.py, DesignChecks.py) and by the builders when something
cannot be fitted while building.  Nothing to edit here.
"""

import os
import sys


class ParameterConflict(ValueError):
    """`names`: the parameters that conflict (2 or more); `message`: one sentence that says why and what to change."""

    def __init__(self, names, message):
        self.names = tuple(names)
        self.message = message
        super().__init__(f"{conflict_title(self.names)}: {message}")


def conflict_title(names):
    """'A conflicts with B' / 'A conflicts with B and C' / 'A, B and C conflict with each other'."""
    names = list(names)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} conflicts with {names[1]}"
    return f"{names[0]} conflicts with {', '.join(names[1:-1])} and {names[-1]}"


class Colour:
    enabled = False

    @classmethod
    def setup(cls, force=None):
        if force is None:
            force = None if "FORCE_COLOR" not in os.environ else True
        if "NO_COLOR" in os.environ and force is None:
            cls.enabled = False
        elif force is not None:
            cls.enabled = bool(force)
        else:
            cls.enabled = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
        if cls.enabled and os.name == "nt":
            os.system("")                      # switches the Windows console to ANSI mode

    @classmethod
    def _wrap(cls, code, s):
        return f"\033[{code}m{s}\033[0m" if cls.enabled else s

    red = classmethod(lambda c, s: c._wrap("1;31", s))
    yellow = classmethod(lambda c, s: c._wrap("1;33", s))
    green = classmethod(lambda c, s: c._wrap("1;32", s))
    dim = classmethod(lambda c, s: c._wrap("2", s))
    bold = classmethod(lambda c, s: c._wrap("1", s))


class Report:
    """Findings of a check: items (level, message, names).  `names` are the parameters a finding is about; a finding
    with two or more names is a conflict between them and is printed as

        ERROR   NAME_A conflicts with NAME_B
                why, and what to change
    """

    def __init__(self):
        self.items = []                         # (level, message, names)

    def add(self, level, msg, names=()):
        self.items.append((level, msg, tuple(names)))

    def error(self, msg, names=()):
        self.add("error", msg, names)

    def warn(self, msg, names=()):
        self.add("warning", msg, names)

    def info(self, msg, names=()):
        self.add("info", msg, names)

    def conflict(self, names, msg, level="error"):
        """`names` (2 or more parameters) cannot hold together; `msg` says why and what to change."""
        self.add(level, msg, names)

    def extend(self, other):
        self.items.extend(other.items)

    @property
    def errors(self):
        return [self.text(i) for i in self.items if i[0] == "error"]

    @property
    def warnings(self):
        return [self.text(i) for i in self.items if i[0] == "warning"]

    @staticmethod
    def text(item):
        """One line of plain text for an item (the record file)."""
        level, msg, names = item
        return f"{conflict_title(names)}: {msg}" if len(names) >= 2 else msg

    def print(self, indent="  "):
        for level, msg, names in self.items:
            paint = {"error": Colour.red, "warning": Colour.yellow}.get(level, Colour.dim if level == "info" else None)
            tag = {"error": "ERROR  ", "warning": "WARNING", "info": "info   "}[level]
            lines = msg.split("\n")
            if len(names) >= 2:                 # a conflict: the names in colour, the explanation below them
                head = conflict_title(names)
                print(f"{indent}{paint(tag + ' ' + head)}")
                for ln in lines:
                    print(indent + " " * 8 + ln)
                continue
            if level == "info":
                print(f"{indent}{Colour.dim(tag)} {lines[0]}")
                for ln in lines[1:]:
                    print(indent + " " * 8 + ln)
            else:
                print(f"{indent}{paint(tag + ' ' + lines[0])}")
                for ln in lines[1:]:
                    print(indent + " " * 8 + paint(ln))

    def add_exception(self, e, level="error"):
        """A ValueError from the geometry modules: a ParameterConflict keeps its names, anything else is plain text."""
        if isinstance(e, ParameterConflict):
            self.add(level, e.message, e.names)
        else:
            self.add(level, str(e))
