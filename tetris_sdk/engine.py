"""Move engine: kick-aware rotation, drop, spin detection, and reachability.

This layer turns the static Board/Piece model into reachable play. It applies
the active rotation system's wall kicks, performs soft drops and unit
translations, detects immobility and T-corners, classifies spins under the
immobile convention, and enumerates every placement reachable from spawn.

All functions are written against the public Board/Piece API so a faster
backend can later implement the same operations behind the same signatures.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum

from tetris_sdk.board import Board
from tetris_sdk.pieces import Piece, PieceType, RotationSystem, SRS
from tetris_sdk.types import Cell


class Move(Enum):
    """A single input applied to an active piece."""

    LEFT = "LEFT"
    RIGHT = "RIGHT"
    SOFT_DROP = "SOFT_DROP"
    CW = "CW"
    CCW = "CCW"
    FLIP = "FLIP"
    HARD_DROP = "HARD_DROP"

    @property
    def is_rotation(self) -> bool:
        """True for the rotation moves (CW, CCW, FLIP)."""
        return self in (Move.CW, Move.CCW, Move.FLIP)


class SpinType(Enum):
    """Classification of a resting piece's spin, ordered NONE < MINI < FULL."""

    NONE = 0
    MINI = 1
    FULL = 2

    @property
    def rank(self) -> int:
        return self.value


@dataclass(frozen=True)
class Placement:
    """A reachable resting placement with its spin and an input path."""

    type: PieceType
    rotation: int
    row: int
    col: int
    spin: SpinType
    lines_cleared: int
    path: tuple[Move, ...]


# Rotation index delta per rotation move.
_ROT_DELTA = {Move.CW: 1, Move.CCW: 3, Move.FLIP: 2}


# --- movement primitives ----------------------------------------------------

def translate(board: Board, piece: Piece, drow: int, dcol: int) -> Piece | None:
    """Return ``piece`` shifted by ``(drow, dcol)`` if it fits, else ``None``."""
    moved = piece.copy(row=piece.row + drow, col=piece.col + dcol)
    return moved if board.can_place(moved) else None


def soft_drop(board: Board, piece: Piece) -> Piece:
    """Return ``piece`` dropped straight down to its resting position."""
    current = piece
    while True:
        below = translate(board, current, -1, 0)
        if below is None:
            return current
        current = below


def rotate(
    board: Board, piece: Piece, direction: Move
) -> tuple[Piece, bool] | None:
    """Rotate ``piece`` applying the system's kicks in order.

    Returns ``(rotated_piece, kick_used)`` for the first kick offset that
    fits, or ``None`` if no offset yields a valid placement. ``kick_used`` is
    True when the winning offset is not ``(0, 0)``.
    """
    if direction not in _ROT_DELTA:
        raise ValueError(f"{direction} is not a rotation move")
    to_rot = (piece.rotation + _ROT_DELTA[direction]) % 4
    tests = piece.system.kicks(piece.type, piece.rotation, to_rot) or [(0, 0)]
    for drow, dcol in tests:
        candidate = piece.copy(
            rotation=to_rot, row=piece.row + drow, col=piece.col + dcol
        )
        if board.can_place(candidate):
            return candidate, (drow, dcol) != (0, 0)
    return None


# --- spin primitives --------------------------------------------------------

_UNIT_DIRS = ((1, 0), (-1, 0), (0, -1), (0, 1))  # up, down, left, right


def immobile(board: Board, piece: Piece) -> bool:
    """True iff ``piece`` cannot move one cell in any of the four directions."""
    return all(
        translate(board, piece, drow, dcol) is None
        for drow, dcol in _UNIT_DIRS
    )


def _t_center(piece: Piece) -> tuple[int, int]:
    """The T-piece's center cell: the one orthogonally adjacent to the other 3."""
    cells = piece.cells
    for r, c in cells:
        neighbors = sum(
            (abs(r - r2) + abs(c - c2)) == 1 for r2, c2 in cells
        )
        if neighbors == 3:
            return r, c
    # Fallback (should not happen for a well-formed T): geometric mean.
    raise ValueError("piece has no T-center cell")


def _is_filled(board: Board, row: int, col: int) -> bool:
    """A corner counts as filled if out of bounds or occupied."""
    if not (0 <= row < board.rows and 0 <= col < board.cols):
        return True
    return board.get_cell(row, col) != Cell.EMPTY


def t_corners_filled(board: Board, piece: Piece) -> int:
    """Count filled diagonal corners around the T-piece's center (0-4)."""
    cr, cc = _t_center(piece)
    return sum(
        _is_filled(board, cr + dr, cc + dc)
        for dr in (-1, 1)
        for dc in (-1, 1)
    )


def classify_spin(
    board: Board, piece: Piece, last_action_was_rotation: bool
) -> SpinType:
    """Classify a resting piece's spin under the immobile convention."""
    if not last_action_was_rotation:
        return SpinType.NONE
    if piece.type == PieceType.T:
        if t_corners_filled(board, piece) >= 3:
            return SpinType.FULL if immobile(board, piece) else SpinType.MINI
        return SpinType.NONE
    return SpinType.FULL if immobile(board, piece) else SpinType.NONE


# --- reachability -----------------------------------------------------------

def _default_spawn(piece_type: PieceType, system: RotationSystem) -> Piece:
    """Spawn a piece at rotation 0 near the top of the playfield."""
    shape = system.rotations(piece_type)[0]
    min_dr = min(dr for dr, _ in shape)
    row = 19 - min_dr  # lowest cell sits at row 19
    col = 4 if piece_type == PieceType.O else 3
    return Piece(piece_type, rotation=0, row=row, col=col, system=system)


def _system_has_180(system: RotationSystem) -> bool:
    return bool(system.kicks(PieceType.T, 0, 2))


def _lines_cleared_if_locked(board: Board, piece: Piece) -> int:
    """Lines that would clear if ``piece`` were locked, without mutating board."""
    piece_cells = set(piece.cells)
    rows = {r for r, _ in piece_cells}
    cleared = 0
    for r in rows:
        full = all(
            (r, c) in piece_cells or board.get_cell(r, c) != Cell.EMPTY
            for c in range(board.cols)
        )
        if full:
            cleared += 1
    return cleared


def reachable(
    board: Board,
    piece_type: PieceType,
    system: RotationSystem | None = None,
    *,
    allow_flip: bool | None = None,
    spawn: Piece | None = None,
    instant: bool = False,
) -> list[Placement]:
    """Enumerate every distinct resting placement reachable from spawn.

    Results are deduplicated by the absolute set of locked cells; when two
    states lock the same cells, the higher-ranked ``SpinType`` is kept. ``FLIP``
    transitions are explored when ``allow_flip`` is True, disabled when False,
    and auto-enabled when ``None`` and the system defines 180 kicks.

    ``instant`` models a soft drop configured to teleport the piece straight to
    its resting row, as most players set it. Descent is then all-or-nothing, so
    the piece can only ever be at spawn height or at rest — placements that need
    it stopped partway must be ridden down under gravity, and those drop out of
    the result. Comparing the two sets is what identifies a gravity wait.
    """
    system = system or SRS()
    if allow_flip is None:
        allow_flip = _system_has_180(system)

    start = spawn if spawn is not None else _default_spawn(piece_type, system)
    start_state = (start.rotation, start.row, start.col)
    if not board.can_place(start):
        return []

    moves: list[Move] = [Move.LEFT, Move.RIGHT, Move.SOFT_DROP, Move.CW, Move.CCW]
    if allow_flip:
        moves.append(Move.FLIP)

    def piece_at(state: tuple[int, int, int]) -> Piece:
        rot, r, c = state
        return Piece(piece_type, rotation=rot, row=r, col=c, system=system)

    visited = {start_state}
    path: dict[tuple[int, int, int], tuple[Move, ...]] = {start_state: ()}
    by_rotation: dict[tuple[int, int, int], bool] = {start_state: False}
    queue: deque[tuple[int, int, int]] = deque([start_state])

    while queue:
        state = queue.popleft()
        piece = piece_at(state)
        for move in moves:
            if move == Move.LEFT:
                nxt = translate(board, piece, 0, -1)
            elif move == Move.RIGHT:
                nxt = translate(board, piece, 0, 1)
            elif move == Move.SOFT_DROP:
                if instant:
                    landed = soft_drop(board, piece)
                    nxt = landed if landed.row != piece.row else None
                else:
                    nxt = translate(board, piece, -1, 0)
            else:  # rotation
                result = rotate(board, piece, move)
                nxt = result[0] if result else None
            if nxt is None:
                continue
            nstate = (nxt.rotation, nxt.row, nxt.col)
            if move.is_rotation:
                by_rotation[nstate] = True
            else:
                by_rotation.setdefault(nstate, False)
            if nstate not in visited:
                visited.add(nstate)
                path[nstate] = path[state] + (move,)
                queue.append(nstate)

    best: dict[frozenset[tuple[int, int]], Placement] = {}
    for state in visited:
        piece = piece_at(state)
        if translate(board, piece, -1, 0) is not None:
            continue  # not resting
        spin = classify_spin(board, piece, by_rotation.get(state, False))
        cells = frozenset(piece.cells)
        placement = Placement(
            type=piece_type,
            rotation=piece.rotation,
            row=piece.row,
            col=piece.col,
            spin=spin,
            lines_cleared=_lines_cleared_if_locked(board, piece),
            path=path[state],
        )
        existing = best.get(cells)
        if existing is None or spin.rank > existing.spin.rank:
            best[cells] = placement

    return list(best.values())
