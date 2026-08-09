"""Per-platform seeded RNGs that reproduce each platform's 7-bag order.

The piece sequence is *not* stored in a replay — only the seed is. To
reconstruct gameplay we must regenerate the exact same bag order the platform
produced, which means matching each platform's PRNG bit-for-bit. A wrong RNG
makes every placement wrong, so this is the make-or-break layer (see the
``add-replay-simulate`` design); it is validated in isolation by confirming each
generated bag is a permutation of the seven pieces and that a full reconstructed
game matches the replay's own final piece count.

TETR.IO
-------
TETR.IO uses the Park-Miller "minimal standard" multiplicative LCG
(``x -> 16807 * x mod 2147483647``) and a Fisher-Yates shuffle of the fixed bag
order ``["Z", "L", "O", "S", "I", "J", "T"]`` — exactly the routine in the
TETR.IO / ``@haelp/teto`` engine. ``next_float`` returns ``(x - 1) / 2147483646``
and the shuffle walks ``i`` from ``len-1`` down to ``1`` swapping with
``floor(next_float() * (i + 1))``.

Jstris
------
Jstris seeds its randomizer with the **string** ``c.seed`` (e.g. ``"4fkj9"``)
and uses Baagøe's **alea** PRNG (``blockRNG = alea(seed)`` in the client). Its
7-bag is *draw-without-replacement*, not an up-front shuffle: from a bag of the
seven block ids it repeatedly takes ``floor(alea() * len)`` and removes it,
refilling when empty. Jstris block ids map as ``{I:0, O:1, T:2, L:3, J:4, S:5,
Z:6}``. This reproduces Jstris's exact piece order; it is verified bit-exact
against the client randomizer (game.js ``Bag``/``alea``/``blockIds``).
"""

from __future__ import annotations

import math
from typing import Callable, Protocol, runtime_checkable

from tetris_sdk.pieces import PieceType


@runtime_checkable
class Rng(Protocol):
    """A seeded, deterministic source of bags and floats."""

    def next_float(self) -> float:
        """Return the next float in ``[0, 1)``."""
        ...

    def next_bag(self) -> list[PieceType]:
        """Return the next 7-bag as a list of :class:`PieceType`."""
        ...


def _fisher_yates(rng: "_FloatRng", order: list[PieceType]) -> list[PieceType]:
    """Shuffle a copy of ``order`` in place using ``rng.next_float``.

    Walks ``i`` from the last index down to 1, swapping element ``i`` with a
    randomly chosen element ``r = floor(next_float() * (i + 1))`` in ``[0, i]``.
    This is the guideline Fisher-Yates both platforms use.
    """
    arr = list(order)
    for i in range(len(arr) - 1, 0, -1):
        r = int(rng.next_float() * (i + 1))
        arr[i], arr[r] = arr[r], arr[i]
    return arr


class _FloatRng:
    """Mixin providing :meth:`next_bag` from a platform ``next_float``."""

    _BAG_ORDER: list[PieceType] = []

    def next_float(self) -> float:  # pragma: no cover - overridden
        raise NotImplementedError

    def next_bag(self) -> list[PieceType]:
        return _fisher_yates(self, self._BAG_ORDER)


class TetrioRng(_FloatRng):
    """TETR.IO's Park-Miller PRNG and 7-bag shuffle."""

    _MODULUS = 2147483647  # 2**31 - 1
    _MULT = 16807
    _BAG_ORDER = [
        PieceType.Z,
        PieceType.L,
        PieceType.O,
        PieceType.S,
        PieceType.I,
        PieceType.J,
        PieceType.T,
    ]

    def __init__(self, seed: int) -> None:
        t = int(seed) % self._MODULUS
        if t <= 0:
            t += self._MODULUS - 1
        self._t = t

    def next_float(self) -> float:
        self._t = (self._MULT * self._t) % self._MODULUS
        return (self._t - 1) / (self._MODULUS - 1)


def _u32(x: float) -> int:
    """JavaScript ``x >>> 0`` (ToUint32: truncate toward zero, mod 2**32)."""
    return int(math.trunc(x)) & 0xFFFFFFFF


def _make_mash() -> Callable[[object], float]:
    """Baagøe's Mash hash (stateful), as used by ``alea``."""
    n = 0xEFC8249D

    def mash(data: object) -> float:
        nonlocal n
        for ch in str(data):
            n += ord(ch)
            h = 0.02519603282416938 * n
            n = _u32(h)
            h -= n
            h *= n
            n = _u32(h)
            h -= n
            n += h * 0x100000000  # 2**32
        return _u32(n) * 2.3283064365386963e-10  # 2**-32

    return mash


def _alea(seed: object) -> Callable[[], float]:
    """Baagøe's alea PRNG seeded with ``seed``; returns a next-float callable.

    This is the exact generator Jstris uses for its block randomizer.
    """
    mash = _make_mash()
    c = 1
    s = [mash(" "), mash(" "), mash(" ")]
    for i in range(3):
        s[i] -= mash(seed)
        if s[i] < 0:
            s[i] += 1
    s0, s1, s2 = s

    def nxt() -> float:
        nonlocal s0, s1, s2, c
        t = 2091639 * s0 + c * 2.3283064365386963e-10
        s0 = s1
        s1 = s2
        c = int(t)  # JS `t | 0`; t >= 0 here, so truncation == floor
        s2 = t - c
        return s2

    return nxt


class JstrisRng:
    """Jstris's alea PRNG and draw-without-replacement 7-bag.

    Seeded with the **string** ``c.seed`` from the replay config. Each bag is
    drawn by repeatedly taking ``floor(alea() * remaining)`` from a bag of the
    seven block ids and removing it — exactly the client's ``Bag.getBlock``.
    """

    # Jstris block id -> PieceType (game.js `blockIds`).
    _ID = {
        0: PieceType.I, 1: PieceType.O, 2: PieceType.T, 3: PieceType.L,
        4: PieceType.J, 5: PieceType.S, 6: PieceType.Z,
    }

    def __init__(self, seed: object) -> None:
        self._next = _alea(seed)

    def next_float(self) -> float:
        return self._next()

    def next_bag(self) -> list[PieceType]:
        bag = list(range(7))
        out: list[PieceType] = []
        while bag:
            idx = int(math.floor(self._next() * len(bag)))
            out.append(self._ID[bag.pop(idx)])
        return out
