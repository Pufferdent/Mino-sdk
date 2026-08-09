"""Turning a line with mid-bag clears back into a static tiling problem.

A line that clears no rows is easy: its pieces tile ``end - start`` and
:func:`tetris_sdk.opener.tiling.tile` enumerates the possibilities directly.
A line that clears rows partway through looks like it has no such region —
once a row goes, everything above drops and later placements no longer
partition anything fixed.

They do, in the right frame. Undo every shift and each piece occupies a
distinct set of cells in the **lifted** board, the one where rows fill but never
disappear. That lifted board is exactly the end stack with the cleared rows put
back, so::

    region = lifted(end, cleared_rows) - start

is static, has exactly ``4 x pieces`` cells, and can be tiled. Which rows were
the cleared ones is not known, so every placement of them is tried — a handful
of combinations, not a search.

Ordering is still decided in the real frame: :func:`replay` walks a tiling in a
given order, clears rows the moment they fill, and maps each piece's lifted
cells down to where the player actually sees them.
"""

from __future__ import annotations

from itertools import combinations

from tetris_sdk.board import COLS

_FULL = (1 << COLS) - 1


def lift(end: tuple, cleared: tuple) -> tuple:
    """The end stack with full rows re-inserted at ``cleared`` row indices."""
    out, it = [], iter(end)
    total = len(end) + len(cleared)
    for row in range(total):
        out.append(_FULL if row in cleared else next(it, 0))
    while out and out[-1] == 0:
        out.pop()
    return tuple(out)


def frames(end: tuple, clears: int, start: tuple, cells: int):
    """Yield ``(lifted rows, region)`` for every placement of the cleared rows.

    A frame is dropped unless the start stack fits inside it and the region is
    exactly the size the pieces can fill — both cheap tests that discard most
    combinations before any tiling work.
    """
    height = len(end) + clears
    start_cells = {
        (r, c) for r, mask in enumerate(start)
        for c in range(COLS) if mask >> c & 1
    }
    seen = set()
    for cleared in combinations(range(height), clears):
        lifted = lift(end, cleared)
        if lifted in seen:
            continue
        seen.add(lifted)
        filled = {
            (r, c) for r, mask in enumerate(lifted)
            for c in range(COLS) if mask >> c & 1
        }
        if not start_cells <= filled:
            continue
        region = filled - start_cells
        if len(region) != cells:
            continue
        yield lifted, frozenset(region), cleared


def real_rows(lifted_filled: set, cleared: list, height: int) -> tuple:
    """The board as the player sees it: lifted cells, cleared rows removed."""
    rows = []
    for r in range(height):
        if r in cleared:
            continue
        mask = 0
        for c in range(COLS):
            if (r, c) in lifted_filled:
                mask |= 1 << c
        rows.append(mask)
    while rows and rows[-1] == 0:
        rows.pop()
    return tuple(rows)


def to_real(cells, cleared: list) -> tuple | None:
    """Map lifted cells down past the rows already gone, or ``None`` if in one."""
    out = []
    for r, c in cells:
        if r in cleared:
            return None
        out.append((r - sum(1 for x in cleared if x < r), c))
    return tuple(sorted(out))
