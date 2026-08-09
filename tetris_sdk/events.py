"""Game events: the classified outcome of locking a piece on the board.

Every lock produces one :class:`Event` whose :class:`EventKind` is determined
by ``(lines, spin)`` — a plain block placement, a spin that cleared nothing
(``spin-0``), or a line clear. Back-to-back difficulty is configurable between
TETR.IO's Season 1 (``S1``) and Season 2 (``S2``) rules.

Scoring is intentionally absent: events carry facts (names, difficulty, running
b2b/combo), and a future scoring layer consumes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tetris_sdk.pieces import PieceType
from tetris_sdk.engine import SpinType


class EventKind(Enum):
    """What a single lock did."""

    PLACEMENT = "PLACEMENT"  # cleared no lines, not a spin
    SPIN = "SPIN"            # a spin that cleared no lines ("spin-0")
    CLEAR = "CLEAR"          # cleared one or more lines


class B2BRule(Enum):
    """Back-to-back rule set."""

    S1 = "S1"  # TETR.IO Season 1: only quads + T-spins-with-lines
    S2 = "S2"  # TETR.IO Season 2: quads + any line-clearing spin (all-spin)


@dataclass(frozen=True)
class Event:
    """The classified outcome of locking a piece."""

    kind: EventKind
    piece: PieceType
    spin: SpinType
    lines: int
    name: str
    difficult: bool
    back_to_back: bool
    b2b: int
    combo: int
    perfect_clear: bool


_LINE_WORD = {1: "Single", 2: "Double", 3: "Triple", 4: "Quad"}


def classify_lock(
    piece: PieceType, spin: SpinType, lines: int
) -> tuple[EventKind, str]:
    """Map ``(piece, spin, lines)`` to an ``(EventKind, name)`` pair.

    Pure: independent of any running back-to-back/combo state.
    """
    if lines == 0:
        if spin == SpinType.NONE:
            return EventKind.PLACEMENT, "Placement"
        # spin-0: a spin that cleared nothing
        if piece == PieceType.T:
            base = "T-Spin Mini" if spin == SpinType.MINI else "T-Spin"
        else:
            base = f"{piece.name}-Spin"
        return EventKind.SPIN, base

    word = _LINE_WORD[lines]
    if spin == SpinType.NONE:
        return EventKind.CLEAR, word
    if piece == PieceType.T:
        prefix = "T-Spin Mini" if spin == SpinType.MINI else "T-Spin"
        return EventKind.CLEAR, f"{prefix} {word}"
    return EventKind.CLEAR, f"{piece.name}-Spin {word}"


def is_difficult(
    piece: PieceType, spin: SpinType, lines: int, rule: B2BRule
) -> bool:
    """Whether a clear is back-to-back-eligible under ``rule``."""
    if lines == 0:
        return False
    if lines == 4:
        return True
    if rule == B2BRule.S1:
        return piece == PieceType.T and spin != SpinType.NONE
    return spin != SpinType.NONE


# S2 attack: every clear sends 0/1/2/4 whatever spun it, except a full
# T-spin, which sends 2/4/6. A clear made with back-to-back active adds one.
_S2_ATTACK = {1: 0, 2: 1, 3: 2, 4: 4}
_S2_TSPIN_ATTACK = {1: 2, 2: 4, 3: 6}


def attack(
    piece: PieceType,
    spin: SpinType,
    lines: int,
    *,
    rule: B2BRule = B2BRule.S2,
    b2b: bool = False,
) -> int:
    """Lines sent by one lock under TETR.IO Season 2 rules.

    ``b2b`` is whether back-to-back was already alive when the piece locked;
    a difficult clear then sends one extra. Season 1's table is different and
    deliberately not implemented — asking for it raises rather than guessing.
    """
    if rule is not B2BRule.S2:
        raise NotImplementedError("only S2 attack is implemented")
    if lines == 0:
        return 0
    if piece == PieceType.T and spin == SpinType.FULL:
        base = _S2_TSPIN_ATTACK.get(lines, 6)
    else:
        base = _S2_ATTACK.get(lines, 4)
    if b2b and is_difficult(piece, spin, lines, rule):
        base += 1
    return base
