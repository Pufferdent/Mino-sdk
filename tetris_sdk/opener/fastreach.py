"""Reachability on bitboards, for when the search runs it tens of thousands of times.

:func:`tetris_sdk.engine.reachable` is the readable reference: it works in
``Piece`` objects on a 40-row ``Board`` and costs a few milliseconds a call.
That is fine for inspecting one position and ruinous inside a bag-wide search,
which asks the same question for every stack it touches — the three-bag script
spent essentially all of its time there.

This is the same search over the same rules, with the board as one integer per
row and every orientation's column masks precomputed. Results are meant to
agree with the engine exactly; ``tests/test_fastreach.py`` checks that on random
stacks, and the engine stays the definition of correct.

The rotation system is a parameter. The opener default is TETR.IO's SRS+
(:data:`DEFAULT_SYSTEM`), whose 180 kicks enable the flip move, exactly as the
engine enables ``FLIP`` when a system defines 180 kicks. Pass ``system=SRS()``
(or any :class:`~tetris_sdk.pieces.RotationSystem`) to change the rules.
"""

from __future__ import annotations

from collections import deque
from functools import lru_cache

from tetris_sdk.board import COLS
from tetris_sdk.engine import SpinType
from tetris_sdk.pieces import PieceType, RotationSystem, SRSPlus

DEFAULT_SYSTEM: RotationSystem = SRSPlus()


@lru_cache(maxsize=None)
def _has_180(system: RotationSystem) -> bool:
    """Whether the system defines 180 kicks — the engine's flip-enable rule."""
    return bool(system.kicks(PieceType.T, 0, 2))


@lru_cache(maxsize=None)
def _shape(system: RotationSystem, piece: PieceType, rotation: int) -> tuple:
    """Cells of an orientation, as offsets from the piece origin."""
    return tuple(system.rotations(piece)[rotation])


@lru_cache(maxsize=None)
def _kicks(system: RotationSystem, piece: PieceType, frm: int, to: int) -> tuple:
    return tuple(system.kicks(piece, frm, to)) or ((0, 0),)


@lru_cache(maxsize=None)
def _bands(system: RotationSystem, piece: PieceType, rotation: int) -> tuple:
    """The orientation as bitmask row-bands: ``((dr, mask), ...), min_dc, max_dc``.

    ``mask`` is the row's columns encoded relative to ``min_dc``, so the test
    for a piece at ``(row, col)`` is a shift and an AND per band — no cell
    tuples are built anywhere on the hot path.
    """
    shape = _shape(system, piece, rotation)
    min_dc = min(dc for _, dc in shape)
    max_dc = max(dc for _, dc in shape)
    bands: dict = {}
    for dr, dc in shape:
        bands[dr] = bands.get(dr, 0) | 1 << (dc - min_dc)
    return tuple(sorted(bands.items())), min_dc, max_dc


def _cells(system: RotationSystem, piece: PieceType, rot: int,
           row: int, col: int) -> tuple:
    return tuple(sorted((row + dr, col + dc)
                        for dr, dc in _shape(system, piece, rot)))


def _blocked(rows: tuple, system: RotationSystem, piece: PieceType,
             rot: int, row: int, col: int) -> bool:
    """True if any cell is out of bounds or already filled."""
    bands, min_dc, max_dc = _bands(system, piece, rot)
    if col + min_dc < 0 or col + max_dc >= COLS:
        return True
    shift = col + min_dc
    height = len(rows)
    for dr, mask in bands:
        r = row + dr
        if r < 0:
            return True
        if r < height and rows[r] & (mask << shift):
            return True
    return False


def _filled(rows: tuple, r: int, c: int) -> bool:
    """Out of bounds counts as filled, matching the engine's corner rule."""
    if c < 0 or c >= COLS or r < 0:
        return True
    return r < len(rows) and bool(rows[r] >> c & 1)


def _t_corners(rows: tuple, system: RotationSystem, piece: PieceType,
               rot: int, row: int, col: int) -> int:
    cells = _cells(system, piece, rot, row, col)
    centre = next(
        (r, c) for r, c in cells
        if sum(abs(r - r2) + abs(c - c2) == 1 for r2, c2 in cells) == 3
    )
    return sum(
        _filled(rows, centre[0] + dr, centre[1] + dc)
        for dr in (-1, 1) for dc in (-1, 1)
    )


@lru_cache(maxsize=None)
def reach(rows: tuple, piece: PieceType, instant: bool = False,
          system: RotationSystem = DEFAULT_SYSTEM) -> dict:
    """``{locked cells: spin}`` for every placement reachable from spawn.

    ``instant`` models a soft drop that teleports to the floor, so descent is
    all-or-nothing and placements needing the piece halted partway are excluded.
    """
    top = len(rows)
    start = (0, top + 3, 3)
    if _blocked(rows, system, piece, *start):
        return {}

    # Hoist every per-system lookup out of the loop: cache hits on functions
    # keyed by the system re-hash it millions of times otherwise.
    rot_deltas = (1, 3, 2) if _has_180(system) else (1, 3)
    kick_table = [
        [(to, _kicks(system, piece, rot, to))
         for to in ((rot + d) % 4 for d in rot_deltas)]
        for rot in range(4)
    ]
    shapes = [_shape(system, piece, rot) for rot in range(4)]

    # Collision as one bit test. For each rotation, ``bad[row + _OFF]`` has
    # bit ``col - lo`` set when the piece collides at that origin. The offsets
    # conspire: with cols encoded from ``lo = -min_dc``, a band's blocked
    # columns are exactly ``rows[row + dr] >> b`` for each set bit ``b``.
    _OFF = 3
    height = top + _OFF + 8
    lo_hi: list = []
    bad: list = []
    for rot in range(4):
        bands, min_dc, max_dc = _bands(system, piece, rot)
        lo = -min_dc
        hi = COLS - 1 - max_dc
        span = (1 << (hi - lo + 1)) - 1
        rot_bad = []
        for row in range(-_OFF, height - _OFF):
            mask = 0
            for dr, band in bands:
                r = row + dr
                if r < 0:
                    mask = span
                    break
                if r < top:
                    pattern = rows[r]
                    b = band
                    while b:
                        low = b & -b
                        mask |= pattern >> low.bit_length() - 1
                        b ^= low
            rot_bad.append(mask)
        lo_hi.append((lo, hi))
        bad.append(rot_bad)

    def blocked(rot: int, row: int, col: int) -> bool:
        lo, hi = lo_hi[rot]
        if col < lo or col > hi:
            return True
        idx = row + _OFF
        if idx < 0:
            return True
        if idx >= height:
            return False  # open air above the precomputed window
        return bool(bad[rot][idx] >> (col - lo) & 1)

    # Open air above the stack is fully connected — sideways movement is free
    # and a rotation's first kick works — so instead of wandering there from
    # spawn, seed the search with every orientation at every column, one row
    # above the surface. Placements and spins are identical; the air walk that
    # dominated the state count is skipped.
    seen = {}
    queue = deque()
    for rot in range(4):
        lo, hi = lo_hi[rot]
        for col in range(lo, hi + 1):
            state = (rot, top + 2, col)
            seen[state] = False
            queue.append(state)
    while queue:
        rot, row, col = queue.popleft()

        moves = []
        for dc in (-1, 1):
            moves.append(((rot, row, col + dc), False))
        if instant:
            drop = row
            while not blocked(rot, drop - 1, col):
                drop -= 1
            if drop != row:
                moves.append(((rot, drop, col), False))
        else:
            moves.append(((rot, row - 1, col), False))
        for to, kicks in kick_table[rot]:
            for dr, dc in kicks:
                if not blocked(to, row + dr, col + dc):
                    moves.append(((to, row + dr, col + dc), True))
                    break

        for nxt, is_rot in moves:
            if blocked(*nxt):
                continue
            if nxt in seen:
                if is_rot and not seen[nxt]:
                    seen[nxt] = True
                continue
            seen[nxt] = is_rot
            queue.append(nxt)

    def immobile(rot: int, row: int, col: int) -> bool:
        for dr, dc in ((1, 0), (-1, 0), (0, -1), (0, 1)):
            if not blocked(rot, row + dr, col + dc):
                return False
        return True

    def spin(rot: int, row: int, col: int, rotated: bool) -> SpinType:
        if not rotated:
            return SpinType.NONE
        if piece is PieceType.T:
            if _t_corners(rows, system, piece, rot, row, col) >= 3:
                return (SpinType.FULL if immobile(rot, row, col)
                        else SpinType.MINI)
            return SpinType.NONE
        return SpinType.FULL if immobile(rot, row, col) else SpinType.NONE

    out: dict = {}
    for (rot, row, col), rotated in seen.items():
        if not blocked(rot, row - 1, col):
            continue  # still falling
        cells = frozenset((row + dr, col + dc) for dr, dc in shapes[rot])
        kind = spin(rot, row, col, rotated)
        if cells not in out or kind.rank > out[cells].rank:
            out[cells] = kind
    return out
