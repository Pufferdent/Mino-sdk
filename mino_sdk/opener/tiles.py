"""The shipped solver: lifted exact cover proposing, real-frame replay disposing.

A line that clears rows partway through looks like it has no fixed region to
fill — once a row goes, everything above drops. It does, in the right frame:
put the cleared rows back and every route's pieces partition the **lifted**
board minus the start stack (:mod:`mino_sdk.opener.lifted`). One wrinkle
makes that exact rather than approximate: a piece placed *after* a clear that
straddles the vanished row appears in the lifted frame with a gap — so the
region is tiled with stretched footprints as well as connected ones
(:mod:`mino_sdk.opener.tiling`).

Ordering is then decided where it belongs, in the real frame: each tiling is
replayed with rows clearing the moment they fill, and a placement counts only
if the bitboard BFS (:mod:`mino_sdk.opener.fastreach`) can reach it — kicks,
tucks and spins included, since those are the norm and cost nothing with an
instant soft drop. The only expense flagged is a gravity wait. A stretched
footprint needs its straddled rows already gone to map onto a real tetromino,
so ordering legality falls out of the reach check rather than bookkeeping.

Why this is fast where the removed solver was not: candidates come from the
tiling, so each replay step chooses among the handful of placements the route
actually uses instead of every resting position on the stack (the 350x that
buried the old search), and dead replay states are shared across tilings —
the state is fully determined by which tiling entries remain.
"""

from __future__ import annotations

from mino_sdk.board import COLS
from mino_sdk.opener import constraints as _c
from mino_sdk.opener.bridge import (
    LineClear,
    Route,
    Step,
    _instant_set,
    _orients,
    _reach_map,
    _rows_of,
)
from mino_sdk.opener.lifted import frames, to_real
from mino_sdk.opener.tiling import tile

_FULL_ROW = (1 << COLS) - 1


def _placement_of(piece, rcells: frozenset, system) -> tuple[int, int, int]:
    """``(rotation, row, col)`` of the orientation whose cells these are."""
    base_r = min(r for r, _ in rcells)
    base_c = min(c for _, c in rcells)
    offsets = tuple(sorted((r - base_r, c - base_c) for r, c in rcells))
    for rot, shape, _, _ in _orients(piece, system):
        if shape == offsets:
            return rot, base_r, base_c
    raise ValueError(f"{piece.name} cells are not one of its orientations")


def _lifted_index(real_row: int, cleared: tuple) -> int:
    """The lifted row a real row currently sits at, given the rows already gone."""
    row = real_row
    for gone in sorted(cleared):
        if gone <= row:
            row += 1
    return row


class TileSolver:
    """Finds the ways across a line. See the module docstring for the shape."""

    def solve(self, bridge, cap: int | None = None) -> list:
        budget = bridge.cleared_lines
        if budget is None:
            return []
        start = _rows_of(bridge.start)
        end = _rows_of(bridge.end)
        start_colors = {
            (r, c): None for r, mask in enumerate(start)
            for c in range(COLS) if mask >> c & 1
        }

        found: list = []
        dead: set = set()

        for lifted, region, cleared_rows in frames(end, budget, start,
                                                   4 * bridge.pieces):
            designated = frozenset(cleared_rows)
            for pool in bridge.pools():
                for tiling in tile(region, pool, cleared=designated,
                                   system=bridge.system):
                    self._replay(bridge, tuple(tiling), designated, start,
                                 end, start_colors, found, dead, cap)
                    if cap is not None and len(found) >= cap:
                        return found
        return found

    def _replay(self, bridge, entries, designated, start, end,
                start_colors, found, dead, cap) -> None:
        budget = bridge.cleared_lines
        steps: list = []

        def walk(rows, colors, remaining, cleared):
            if cap is not None and len(found) >= cap:
                return
            if not remaining:
                if rows == end and len(cleared) == budget:
                    route = Route(tuple(steps),
                                  LineClear(tuple(sorted(designated)), budget),
                                  bridge._saved(steps))
                    if _c.allows(bridge.constraints, route):
                        found.append(route)
                return

            key = (designated, frozenset(remaining))
            if key in dead:
                return
            before = len(found)

            for entry in remaining:
                piece, lcells = entry
                real = to_real(lcells, cleared)
                if real is None:
                    continue
                rcells = frozenset(real)
                spin = _reach_map(rows, piece, bridge.system).get(rcells)
                if spin is None:
                    continue

                stack = list(rows) + [0] * max(
                    0, max(r for r, _ in real) + 1 - len(rows))
                for r, c in real:
                    stack[r] |= 1 << c
                full = sorted({r for r, _ in real if stack[r] == _FULL_ROW})

                gone = [_lifted_index(r, cleared) for r in full]
                if any(g not in designated for g in gone):
                    continue  # a row filled that this frame says survives

                nxt = dict(colors)
                for cell in real:
                    nxt[cell] = piece
                if full:
                    for r in reversed(full):
                        stack.pop(r)
                    nxt = {
                        (r - sum(1 for f in full if f < r), c): p
                        for (r, c), p in nxt.items() if r not in full
                    }
                while stack and stack[-1] == 0:
                    stack.pop()

                rot, prow, pcol = _placement_of(piece, rcells, bridge.system)
                step = Step(piece=piece, rotation=rot, row=prow, col=pcol,
                            spin=spin, cells=tuple(sorted(rcells)),
                            colors=tuple(sorted(nxt.items())),
                            cleared=len(full),
                            gravity_wait=rcells not in _instant_set(
                                rows, piece, bridge.system))
                steps.append(step)
                if not _c.prune(bridge.constraints, steps):
                    walk(tuple(stack), nxt, remaining - {entry},
                         cleared + tuple(gone))
                steps.pop()

            if len(found) == before:
                dead.add(key)

        walk(start, start_colors, frozenset(entries), ())
