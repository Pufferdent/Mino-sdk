"""The seam a solving algorithm plugs into.

The rest of this package describes *what* is being asked: boards, the lines
between them, what each line must satisfy, what a queue with a hold slot can
reorder. None of that says how to find the answer. The shipped answer is
:class:`~tetris_sdk.opener.tiles.TileSolver`, used by default; anything
implementing this protocol can be passed in its place.

A solver is one object with one method. Everything upstream — :class:`Diagram`,
:class:`Bridge`, the constraints — is already correct and stays put, so a new
algorithm is a new class here rather than a rewrite.

Two facts an earlier, removed attempt established, kept load-bearing in the
shipped solver:

* Solve first, then test queues against the solves. A single solve admits many
  placement orders and hold lets many queues produce one of them. Searching per
  queue re-derives the same solves thousands of times.
* Know the region before ordering. Letting placements roam anywhere inside the
  target and filtering afterwards cost 350x — 952 s against 2.7 s on the same
  line, for the same answer.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Solver(Protocol):
    """Finds the ways across a line."""

    def solve(self, bridge, cap: int | None = None) -> list:
        """Return :class:`Route` objects for ``bridge``, at most ``cap`` of them.

        A route is one complete, playable way from the line's start board to its
        end board: an ordering of placements, each reachable in the real frame,
        with rows clearing as they fill. Routes that any of ``bridge.constraints``
        rejects must not be returned.
        """
        ...


class Unsolved(RuntimeError):
    """Raised when a line is asked for a number and no solver was supplied."""

    def __init__(self) -> None:
        super().__init__(
            "no solver: pass one to Bridge.routes(solver=...) or "
            "Diagram.chances(solver=...). See tetris_sdk.opener.solver.Solver."
        )
