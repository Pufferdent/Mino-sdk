"""The piece queue (7-bag from an :class:`Rng`) and the hold slot.

:class:`Queue` lazily refills from the RNG so an arbitrarily long preview window
is available without precomputing the whole game. :class:`Hold` models the
once-per-piece swap that resets when a piece locks.
"""

from __future__ import annotations

from collections import deque

from tetris_sdk.pieces import PieceType
from tetris_sdk.sim.rng import Rng


# Pieces the TETR.IO "no SZO start" rule forbids at the very front of a game.
_SZO = (PieceType.S, PieceType.Z, PieceType.O)


class Queue:
    """A piece queue fed by a seeded 7-bag :class:`Rng`.

    ``no_szo`` applies TETR.IO's "no S/Z/O start" rule: any S, Z, or O pieces at
    the front of the *first* bag are moved to the back (e.g. ``OIJLSZT`` ->
    ``IJLSZTO``) so a game never opens on an overhang-prone piece. It affects the
    first bag only.
    """

    def __init__(self, rng: Rng, *, no_szo: bool = False) -> None:
        self._rng = rng
        self._pieces: deque[PieceType] = deque()
        self._no_szo = no_szo
        self._first_bag = True

    def _next_bag(self) -> list[PieceType]:
        bag = self._rng.next_bag()
        if self._first_bag:
            self._first_bag = False
            if self._no_szo:
                front = 0
                while front < len(bag) and bag[front] in _SZO:
                    front += 1
                bag = bag[front:] + bag[:front]
        return bag

    def _ensure(self, n: int) -> None:
        while len(self._pieces) < n:
            self._pieces.extend(self._next_bag())

    def peek(self, count: int = 1) -> list[PieceType]:
        """Return the next ``count`` pieces without consuming them."""
        self._ensure(count)
        return [self._pieces[i] for i in range(count)]

    def next(self) -> PieceType:
        """Pop and return the next piece, refilling from the RNG as needed."""
        self._ensure(1)
        return self._pieces.popleft()


class Hold:
    """A single hold slot with once-per-piece locking.

    :meth:`swap` exchanges the active piece type with the held one and marks
    hold as used for the current piece; :meth:`reset` re-enables it (called when
    a piece locks). When the slot is empty, swapping stores the active type and
    signals the caller to draw the next piece by returning ``None``.
    """

    def __init__(self) -> None:
        self.piece: PieceType | None = None
        self.used: bool = False

    def reset(self) -> None:
        """Re-enable hold for the next piece (call on lock)."""
        self.used = False

    def swap(self, active: PieceType) -> PieceType | None:
        """Swap ``active`` into the slot.

        Returns the previously held type to make active, or ``None`` if the slot
        was empty (caller draws from the queue). Does nothing and returns the
        sentinel ``active`` unchanged-marker via ``used`` if hold is already
        spent this piece — callers must check :attr:`used` first.
        """
        prev = self.piece
        self.piece = active
        self.used = True
        return prev
