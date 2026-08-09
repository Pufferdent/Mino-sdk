"""The frame-stepped live-play loop: state + per-frame integration.

:class:`GameState` holds the board, queue, hold, active piece, and the timers
that decide when a grounded piece locks. The driver feeds discrete inputs
(rotate/hold/hard-drop and taps) as they occur in the replay timeline using the
``move_*`` helpers, then calls :func:`step_frame` once per frame to apply
auto-shift, soft drop, gravity, and lock-delay locking.

Rotation reuses :func:`mino_sdk.engine.rotate` (kick-aware); spin at lock time
is classified with :func:`mino_sdk.engine.classify_spin` from whether the last
successful action was a rotation; locking and line-clear/B2B/combo accounting
reuse :meth:`mino_sdk.board.Board.lock`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mino_sdk.board import Board
from mino_sdk.engine import Move, classify_spin, rotate, translate
from mino_sdk.events import Event
from mino_sdk.pieces import Piece, PieceType, RotationSystem
from mino_sdk.sim.gravity import GravityProfile
from mino_sdk.sim.handling import FLOOR, WALL, Motion
from mino_sdk.sim.queue import Hold, Queue


def _spawn_piece(piece_type: PieceType, system: RotationSystem) -> Piece:
    """Spawn ``piece_type`` at rotation 0 near the top of the playfield."""
    shape = system.rotations(piece_type)[0]
    min_dr = min(dr for dr, _ in shape)
    row = 19 - min_dr  # lowest cell sits at row 19 (top of the 20-tall well)
    col = 4 if piece_type == PieceType.O else 3
    return Piece(piece_type, rotation=0, row=row, col=col, system=system)


@dataclass
class GameState:
    """Mutable state of a game in progress."""

    board: Board
    queue: Queue
    hold: Hold
    system: RotationSystem
    active: Piece | None = None
    frame: int = 0
    pieces_placed: int = 0
    lines_cleared_total: int = 0
    last_was_rotation: bool = False
    grounded_frames: float = 0.0
    lock_resets_used: int = 0
    topped_out: bool = False
    events: list[Event] = field(default_factory=list)

    def _grounded(self) -> bool:
        return self.active is not None and translate(
            self.board, self.active, -1, 0
        ) is None

    def _reset_lock_timer(self) -> None:
        """Reset lock delay on a successful move/rotate while grounded."""
        if self._grounded() and self.lock_resets_used < 999_999:
            if self.grounded_frames > 0:
                self.lock_resets_used += 1
                self.grounded_frames = 0.0


def spawn_next(state: GameState) -> bool:
    """Draw and spawn the next piece. Returns ``False`` on top-out."""
    piece_type = state.queue.next()
    return _spawn_into(state, piece_type)


def _spawn_into(state: GameState, piece_type: PieceType) -> bool:
    piece = _spawn_piece(piece_type, state.system)
    if not state.board.can_place(piece):
        state.active = piece
        state.topped_out = True
        return False
    state.active = piece
    state.last_was_rotation = False
    state.grounded_frames = 0.0
    state.lock_resets_used = 0
    return True


def move(state: GameState, dx: int) -> bool:
    """Shift the active piece horizontally by ``dx`` (``±WALL`` = to wall).

    Returns ``True`` if the piece moved at least one cell.
    """
    if state.active is None or dx == 0:
        return False
    step = 1 if dx > 0 else -1
    count = abs(dx)
    moved = False
    for _ in range(count):
        nxt = translate(state.board, state.active, 0, step)
        if nxt is None:
            break
        state.active = nxt
        moved = True
        if count < WALL:
            continue
    if moved:
        state.last_was_rotation = False
        state._reset_lock_timer()
    return moved


def rotate_piece(state: GameState, direction: Move) -> bool:
    """Rotate the active piece with kicks. Returns ``True`` if it rotated."""
    if state.active is None:
        return False
    result = rotate(state.board, state.active, direction)
    if result is None:
        return False
    state.active = result[0]
    state.last_was_rotation = True
    state._reset_lock_timer()
    return True


def hold_piece(state: GameState) -> bool:
    """Swap the active piece into hold (once per piece). Returns success."""
    if state.active is None or state.hold.used:
        return False
    active_type = state.active.type
    swapped = state.hold.swap(active_type)
    if swapped is None:
        # Slot was empty: draw the next piece to become active.
        piece_type = state.queue.next()
    else:
        piece_type = swapped
    placed = _spawn_into(state, piece_type)
    state.hold.used = True  # _spawn_into reset lock state; keep hold spent
    return placed


def soft_drop_to(state: GameState, cells: int) -> None:
    """Soft-drop the active piece ``cells`` down (``FLOOR`` = to the floor)."""
    if state.active is None:
        return
    n = state.board.rows if cells >= FLOOR else cells
    for _ in range(n):
        nxt = translate(state.board, state.active, -1, 0)
        if nxt is None:
            break
        state.active = nxt


def _lock(state: GameState) -> None:
    """Lock the active piece, record the event, and spawn the next."""
    piece = state.active
    if piece is None:
        return
    spin = classify_spin(state.board, piece, state.last_was_rotation)
    event = state.board.lock(piece, spin)
    state.events.append(event)
    state.pieces_placed += 1
    state.lines_cleared_total += event.lines
    state.hold.reset()
    spawn_next(state)


def hard_drop(state: GameState) -> None:
    """Drop the active piece to the floor and lock it immediately."""
    soft_drop_to(state, FLOOR)
    _lock(state)


def step_frame(
    state: GameState,
    motion: Motion,
    gravity: GravityProfile,
) -> list[Event]:
    """Advance one frame: auto-shift, soft drop, gravity, and lock delay.

    Discrete inputs (taps, rotations, hold, hard drop) are applied by the driver
    *before* this call using the ``move_*``/:func:`hard_drop` helpers. Returns
    the events produced by any lock during this frame.
    """
    before = len(state.events)
    if state.active is None or state.topped_out:
        state.frame += 1
        return []

    # 1. horizontal auto-shift (DAS/ARR) from handling
    if motion.dx:
        move(state, motion.dx)

    # 2. soft drop from handling
    if motion.soft:
        soft_drop_to(state, motion.soft)

    # 3. gravity descent (fractional cells accumulate via grounded check)
    g = gravity.gravity_at(state.lines_cleared_total, state.frame)
    if gravity.is_20g or g >= state.board.rows:
        soft_drop_to(state, FLOOR)
    elif g > 0:
        cells = int(g) if g >= 1 else (1 if _accumulate(state, g) else 0)
        if cells:
            soft_drop_to(state, cells)

    # 4. lock delay: a grounded piece locks after lock_delay frames
    if state._grounded():
        state.grounded_frames += 1.0
        if state.grounded_frames >= gravity.lock_delay:
            _lock(state)
    else:
        state.grounded_frames = 0.0

    state.frame += 1
    return state.events[before:]


def _accumulate(state: GameState, g: float) -> bool:
    """Accumulate sub-cell gravity; return True when a whole cell is due."""
    state._grav_acc = getattr(state, "_grav_acc", 0.0) + g
    if state._grav_acc >= 1.0:
        state._grav_acc -= 1.0
        return True
    return False
