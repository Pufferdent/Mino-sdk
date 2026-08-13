"""Reachability on bitboards, for when the search runs it tens of thousands of times.

:func:`mino_sdk.engine.reachable` is the readable reference: it works in
``Piece`` objects on a 40-row ``Board`` and costs a few milliseconds a call.
That is fine for inspecting one position and ruinous inside a bag-wide search,
which asks the same question for every stack it touches — the three-bag script
spent essentially all of its time there.

This is the same search over the same rules, with the board as one integer per
row and every orientation's column masks precomputed. It is not a state-by-state
BFS: a column is one bit, so a whole row of states is one integer, and sideways
movement, dropping and each kick are shift-and-mask over all ten columns at once
— a fixpoint over ~4x15 integers instead of a queue of a quarter-million tuples.
Results are meant to agree with the engine exactly;
``tests/test_fastreach.py`` checks that on random stacks, and the engine stays
the definition of correct.

The rotation system is a parameter. The opener default is TETR.IO's SRS+
(:data:`DEFAULT_SYSTEM`), whose 180 kicks enable the flip move, exactly as the
engine enables ``FLIP`` when a system defines 180 kicks. Pass ``system=SRS()``
(or any :class:`~mino_sdk.pieces.RotationSystem`) to change the rules.
"""

from __future__ import annotations

from functools import lru_cache

from mino_sdk.board import COLS
from mino_sdk.engine import SpinType
from mino_sdk.pieces import PieceType, RotationSystem, SRSPlus

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

    # Collision as one bit test. For each rotation, ``free[rot][row + _OFF]``
    # has bit ``col - lo`` set when the piece fits at that origin. The offsets
    # conspire: with cols encoded from ``lo = -min_dc``, a band's blocked
    # columns are exactly ``rows[row + dr] >> b`` for each set bit ``b`` — and
    # those shifts are the same for every row, so they are found once here.
    _OFF = 3
    _PAD = 3  # guard entries so a kick's row can be indexed without a bounds test
    height = top + _OFF + 8
    lo_hi: list = []
    span_of: list = []
    free: list = []
    for rot in range(4):
        bands, min_dc, max_dc = _bands(system, piece, rot)
        lo = -min_dc
        hi = COLS - 1 - max_dc
        span = (1 << (hi - lo + 1)) - 1
        shifted = []
        for dr, band in bands:
            offsets = []
            b = band
            while b:
                low = b & -b
                offsets.append(low.bit_length() - 1)
                b ^= low
            shifted.append((dr, offsets))
        # Below the floor and above the window are the two constant answers:
        # nothing fits, everything fits.
        rot_free = [0] * _PAD
        for row in range(-_OFF, height - _OFF):
            mask = 0
            for dr, offsets in shifted:
                r = row + dr
                if r < 0:
                    mask = span
                    break
                if r < top:
                    pattern = rows[r]
                    for off in offsets:
                        mask |= pattern >> off
            rot_free.append(span & ~mask)
        rot_free.extend([span] * _PAD)
        lo_hi.append((lo, hi))
        span_of.append(span)
        free.append(rot_free)

    def blocked(rot: int, row: int, col: int) -> bool:
        lo, hi = lo_hi[rot]
        if col < lo or col > hi:
            return True
        return not (free[rot][row + _OFF + _PAD] >> (col - lo) & 1)

    # The search is over (rotation, row, column) states, but a column is one
    # bit, so a whole row of states is one integer: ``mask[rot][idx]`` has bit
    # ``col - lo`` set for every reachable column. Sideways movement, dropping
    # and each kick are then shift-and-mask over ten columns at once, and the
    # per-state Python loop — which was the whole cost of this module —
    # disappears.
    # Open air above the stack is fully connected — sideways movement is free
    # and a rotation's first kick works — so instead of wandering there from
    # spawn, seed the search with every orientation at every column, one row
    # above the surface. Placements and spins are identical; the air walk that
    # dominated the state count is skipped.
    seed = top + 2 + _OFF
    mask = [[0] * height for _ in range(4)]
    spun = [[0] * height for _ in range(4)]
    for rot in range(4):
        mask[rot][seed] = span_of[rot]

    # Shift from one orientation's column encoding to another's, given a kick.
    # A source bit sits at ``col - lo_from``; its destination bit is
    # ``col + dc - lo_to``, so every transfer is one shift by ``lo_from + dc -
    # lo_to`` — forward to move states, backward to pull the destination's free
    # columns into the source's frame.
    shifts = [
        [(to, tuple((dr, lo_hi[rot][0] + dc - lo_hi[to][0]) for dr, dc in kicks))
         for to, kicks in kick_table[rot]]
        for rot in range(4)
    ]

    changed = True
    while changed:
        changed = False
        # Top-down, so a piece falling many rows lands in a single sweep.
        for idx in range(height - 1, -1, -1):
            pad = idx + _PAD
            for rot in range(4):
                m = mask[rot][idx]
                if not m:
                    continue
                rot_free = free[rot]
                f = rot_free[pad]

                # Sideways: flood left and right through free columns.
                while True:
                    grown = (m | m << 1 | m >> 1) & f
                    if grown == m:
                        break
                    m = grown
                if m != mask[rot][idx]:
                    mask[rot][idx] = m
                    changed = True

                rot_mask = mask[rot]
                if instant:
                    # Soft drop teleports: only where the fall stops is a state.
                    falling, at = m, idx
                    while falling:
                        below = falling & rot_free[at + _PAD - 1]
                        landed = falling & ~below
                        if landed and at != idx and landed & ~rot_mask[at]:
                            rot_mask[at] |= landed
                            changed = True
                        falling, at = below, at - 1
                        if at < 0:
                            break
                elif idx:
                    down = m & rot_free[pad - 1]
                    if down & ~rot_mask[idx - 1]:
                        rot_mask[idx - 1] |= down
                        changed = True

                for to, kicks in shifts[rot]:
                    left = m
                    to_free = free[to]
                    for dr, s in kicks:
                        if not left:
                            break
                        nxt = idx + dr
                        ok = to_free[nxt + _PAD]
                        # The destination's free columns, read in this
                        # orientation's bit positions.
                        src_ok = (ok >> s if s >= 0 else ok << -s) & f
                        moved = left & src_ok
                        left &= ~src_ok  # a later kick is only tried when
                        if not moved:    # every earlier one is blocked
                            continue
                        if not 0 <= nxt < height:
                            continue
                        dest = moved << s if s >= 0 else moved >> -s
                        if dest & ~mask[to][nxt]:
                            mask[to][nxt] |= dest
                            changed = True
                        if dest & ~spun[to][nxt]:
                            spun[to][nxt] |= dest
                            changed = True

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

    # A state rests where the row below it is blocked, so the resting columns
    # of a row are one AND against that row's free mask — no need to visit the
    # states that are still falling.
    out: dict = {}
    for rot in range(4):
        lo = lo_hi[rot][0]
        shape = shapes[rot]
        rot_free = free[rot]
        for idx in range(height):
            resting = mask[rot][idx] & ~rot_free[idx + _PAD - 1]
            if not resting:
                continue
            rotated = spun[rot][idx]
            row = idx - _OFF
            while resting:
                bit = resting & -resting
                resting ^= bit
                col = bit.bit_length() - 1 + lo
                cells = frozenset((row + dr, col + dc) for dr, dc in shape)
                kind = spin(rot, row, col, bool(rotated & bit))
                if cells not in out or kind.rank > out[cells].rank:
                    out[cells] = kind
    return out
