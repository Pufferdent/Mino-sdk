"""Partitioning the cells a line adds into tetrominoes.

A line's pieces have to fill a specific region: the pre-clear target minus the
stack already there. That is an exact-cover problem, not a perfect clear, and
the difference matters. Encoding it as a PC means declaring every cell outside
the region to be solid garbage, and a line whose region leaves wide open
columns — anything clearing few or no lines — then has the middle of the board
walled off and reports impossible. The pieces really fall through those
columns; the walls were fiction.

So the region is tiled directly here, and reachability is judged separately by
replaying in the real frame. sfinder still owns genuine perfect clears; this
owns the rest.

Search fills the lowest-leftmost uncovered cell first. That cell must be
covered by *some* piece, so branching on it only enumerates real alternatives
and a region with an unfillable notch dies immediately.
"""

from __future__ import annotations

from functools import lru_cache

from tetris_sdk.opener.fastreach import DEFAULT_SYSTEM
from tetris_sdk.pieces import PieceType, RotationSystem

_ORDER = (
    PieceType.T, PieceType.I, PieceType.L, PieceType.J,
    PieceType.S, PieceType.Z, PieceType.O,
)


@lru_cache(maxsize=None)
def _shapes(piece: PieceType,
            system: RotationSystem = DEFAULT_SYSTEM) -> tuple:
    """Distinct normalised orientations of a piece, anchored on its first cell.

    Cells are offsets from the piece's lowest-leftmost cell, so a shape can be
    dropped straight onto the cell the search is currently filling.
    """
    out = []
    for rotation in range(4):
        cells = system.rotations(piece)[rotation]
        base_r = min(r for r, _ in cells)
        shape = sorted((r - base_r, c) for r, c in cells)
        anchor_r, anchor_c = shape[0]
        normalised = tuple(sorted((r - anchor_r, c - anchor_c) for r, c in shape))
        if normalised not in out:
            out.append(normalised)
    return tuple(out)


def _variants(shape, ar: int, ac: int, cleared: frozenset) -> list:
    """Anchored cell-sets for ``shape``: connected, plus stretched across ``cleared``.

    A piece placed *after* a clear straddles the vanished row: in the lifted
    frame its rows are pulled apart by a gap at that row. So besides the
    connected placement, every widening of the shape's row spacing whose skipped
    rows all lie in ``cleared`` is a legal footprint. Which of those the player
    can actually produce — the straddled rows must already be gone when the
    piece lands — is not decided here; the real-frame replay rejects the rest.
    """
    rows = sorted({r for r, _ in shape})
    by_row = [tuple(c for r, c in shape if r == row) for row in rows]
    out: list = []

    def go(i: int, lifted_row: int, acc: list):
        row_cells = tuple((lifted_row, ac + dc) for dc in by_row[i])
        if i == len(rows) - 1:
            out.append(frozenset(acc + list(row_cells)))
            return
        nxt = lifted_row + 1
        go(i + 1, nxt, acc + list(row_cells))
        while nxt in cleared:
            nxt += 1
            go(i + 1, nxt, acc + list(row_cells))

    go(0, ar, [])
    return out


def tile(
    region: frozenset,
    pool: tuple[PieceType, ...],
    limit: int | None = None,
    cleared: frozenset = frozenset(),
    system: RotationSystem = DEFAULT_SYSTEM,
) -> list:
    """Every way to partition ``region`` into the pieces of ``pool``.

    Returns a list of ``[(piece, frozenset(cells)), ...]``. A list rather than
    a dict because a pool may hold a type twice, and two placements of the same
    type must both survive. Orderings are not enumerated here, only partitions —
    ordering is decided later by what the player can reach.

    ``cleared`` names the lifted rows that vanish partway through the line;
    pieces may then also occupy stretched footprints across them (see
    :func:`_variants`). With no cleared rows this is plain exact cover.
    """
    if len(region) != 4 * len(pool):
        return []

    out: list = []
    counts: dict = {}
    for piece in pool:
        counts[piece] = counts.get(piece, 0) + 1

    def walk(left: frozenset, remaining: dict, placed: list):
        if limit is not None and len(out) >= limit:
            return
        if not left:
            out.append(list(placed))
            return
        # The lowest-leftmost open cell has to be covered by something.
        anchor = min(left)
        ar, ac = anchor
        for piece, count in remaining.items():
            if count == 0:
                continue
            for shape in _shapes(piece, system):
                for cells in _variants(shape, ar, ac, cleared):
                    if not cells <= left:
                        continue
                    remaining[piece] = count - 1
                    placed.append((piece, cells))
                    walk(left - cells, remaining, placed)
                    placed.pop()
                    remaining[piece] = count

    walk(frozenset(region), counts, [])
    return out
