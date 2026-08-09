"""Opener research: boards, the lines between them, and their chances.

Draw the boards, join them with lines, say what each line must satisfy — that
much is here and complete. A node is a canonical fumen plus the pieces still to
come; a line is a bag of play between two of them; constraints say what the
play must achieve.

Finding the ways across a line is a solver's job. The shipped one is
:class:`~tetris_sdk.opener.tiles.TileSolver` — lifted exact cover proposes,
real-frame replay disposes — and it is what :meth:`Bridge.routes` and
:meth:`Diagram.chances` use when no solver is passed. The seam stays open:
anything implementing :class:`~tetris_sdk.opener.solver.Solver` can be passed
instead, and everything that describes the problem stays put.
"""

from tetris_sdk.opener.bridge import (
    Bridge,
    LineClear,
    Route,
    Step,
    any_chance,
    any_odds,
)
from tetris_sdk.opener.constraints import (
    Clears,
    Constraint,
    KeepB2B,
    NoGravityWait,
    Saves,
    Spin,
)
from tetris_sdk.opener.diagram import Choice, Diagram, Line, Odds
from tetris_sdk.opener.node import Node
from tetris_sdk.opener.solver import Solver, Unsolved
from tetris_sdk.opener.tiles import TileSolver

__all__ = [
    "Node",
    "Bridge", "Route", "Step", "LineClear", "any_odds", "any_chance",
    "Diagram", "Line", "Odds", "Choice",
    "Solver", "Unsolved", "TileSolver",
    "Constraint", "KeepB2B", "Spin", "Saves", "NoGravityWait", "Clears",
]
