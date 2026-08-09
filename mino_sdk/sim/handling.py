"""Input-handling model: held keys -> discrete motion per frame.

A replay records *key transitions* (press/release at a frame+subframe), not the
realized auto-shift. This module turns those held intervals into per-frame
horizontal cells and soft-drop motion using the player's
:class:`~mino_sdk.replay.model.Handling` (DAS/ARR/SDF/DCD), at the engine's
60 fps. The driver feeds press/release edges as they occur in the timeline and
calls :meth:`tick` once per frame to read the resulting :class:`Motion`.

Conventions (TETR.IO frame units):

* **Tap** — a press moves exactly one cell immediately and starts the DAS timer.
* **DAS** — after ``das`` frames held, auto-shift engages.
* **ARR** — once charged, repeat every ``arr`` frames; ``arr == 0`` snaps to the
  wall in a single frame (the engine applies the move until blocked).
* **SDF** — soft-drop factor; a large value (TETR.IO uses 41 for "infinite")
  snaps the piece to the floor each frame, otherwise it descends ``sdf`` cells.
* **DCD** — DAS cut delay: when another direction is pressed the opposite charge
  is partly reset; modeled as restarting the DAS timer to ``das - dcd``.

``arr``/``das``/``sdf`` are read in frames/cells from the handling block; a wall
snap and floor snap are signaled with the :data:`WALL` / :data:`FLOOR` sentinels
so the engine resolves them against collisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from mino_sdk.replay.model import Handling

WALL = 10_000  # sentinel: shift until blocked (ARR 0)
FLOOR = 10_000  # sentinel: soft-drop until grounded (infinite SDF)

# SDF values at or above this are treated as instant ("slam to floor").
_INFINITE_SDF = 20.0


@dataclass(frozen=True)
class Motion:
    """The horizontal and soft-drop motion produced for a single frame.

    ``dx`` is signed cells to attempt (``±WALL`` = shift to wall). ``soft`` is
    cells to soft-drop (``FLOOR`` = drop to floor); ``0`` when no soft drop.
    """

    dx: int = 0
    soft: int = 0


class HandlingState:
    """Frame-stepped DAS/ARR/SDF state driven by press/release edges."""

    def __init__(self, handling: Handling | None) -> None:
        h = handling
        self.das = float(h.das) if h else 10.0
        self.arr = float(h.arr) if h else 2.0
        self.sdf = float(h.sdf) if h else 6.0
        self.dcd = float(h.dcd) if h else 0.0

        # Per-direction charge state. dir is -1 (left) or +1 (right).
        self._held: dict[int, bool] = {-1: False, 1: False}
        self._charge: dict[int, float] = {-1: 0.0, 1: 0.0}  # frames since press
        self._is_das: dict[int, bool] = {-1: False, 1: False}  # held past DAS?
        self._fired: dict[int, bool] = {-1: False, 1: False}   # arr0 slam done
        self._arr_acc: dict[int, float] = {-1: 0.0, 1: 0.0}  # arr accumulator
        self._last_dir: int = 0  # most-recently pressed direction wins
        self._soft_held: bool = False

    # --- edges (called by the driver in timeline order) --------------------

    def press_dir(self, direction: int, is_das: bool = False) -> int:
        """Register a left/right keydown (``direction`` is -1 or +1).

        ``is_das`` is the driver's subframe-exact verdict — whether this press is
        held at least ``das`` frames before release — so borderline presses are
        classified by true duration rather than integer-frame rounding. Returns
        the immediate tap to apply now (``direction`` on a fresh press, ``0`` if
        already held) for correct ordering against same-frame rotations.
        """
        tap = direction if not self._held[direction] else 0
        self._held[direction] = True
        self._charge[direction] = 0.0
        self._is_das[direction] = is_das
        self._fired[direction] = False
        self._arr_acc[direction] = 0.0
        # DAS cut on the opposite direction's charge.
        other = -direction
        if self._held[other] and self.dcd:
            self._charge[other] = min(self._charge[other], self.das - self.dcd)
        self._last_dir = direction
        return tap

    def release_dir(self, direction: int) -> None:
        """Register a left/right keyup."""
        self._held[direction] = False
        self._charge[direction] = 0.0
        self._is_das[direction] = False
        self._fired[direction] = False
        self._arr_acc[direction] = 0.0
        if self._last_dir == direction:
            self._last_dir = -direction if self._held[-direction] else 0

    def press_soft(self) -> None:
        self._soft_held = True

    def release_soft(self) -> None:
        self._soft_held = False

    # --- per-frame motion --------------------------------------------------

    def tick(self) -> Motion:
        """Advance one frame and return the auto-shift/soft motion this frame.

        Taps are returned by :meth:`press_dir` at the moment of the press; this
        reports only DAS/ARR continuation plus soft drop.
        """
        dx = 0
        d = self._last_dir
        if d != 0 and self._held[d] and self._is_das[d]:
            self._charge[d] += 1.0
            if self._charge[d] >= self.das:
                if self.arr <= 0:
                    dx += d * WALL  # arr 0: slam to wall (idempotent if there)
                else:
                    self._arr_acc[d] += 1.0
                    steps = 0
                    while self._arr_acc[d] >= self.arr:
                        self._arr_acc[d] -= self.arr
                        steps += 1
                    dx += d * steps

        soft = 0
        if self._soft_held:
            soft = FLOOR if self.sdf >= _INFINITE_SDF else max(1, int(self.sdf))

        return Motion(dx=dx, soft=soft)
