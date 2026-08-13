"""Constraints on a line of a diagram, and the protocol for writing your own.

A line between two boards usually has more to say than "get from A to B": keep
back-to-back alive, land a T-spin double on the way, leave an O in hold for the
next line. Each of those is a :class:`Constraint`.

A constraint answers two questions. :meth:`Constraint.allows` judges a finished
route, and :meth:`Constraint.prune` judges a partial one. Implementing ``prune``
is what makes a constraint cheap: rejecting a route at the leaf still pays for
the whole subtree, while rejecting it at the placement that broke it cuts the
subtree away. Constraints are not only filters — they are most of what keeps
the search tractable.

To write your own, implement the protocol; nothing here needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

from mino_sdk.engine import SpinType
from mino_sdk.events import B2BRule, is_difficult
from mino_sdk.pieces import PieceType


@runtime_checkable
class Constraint(Protocol):
    """Something a route must satisfy."""

    def allows(self, route) -> bool:
        """Judge a finished route."""
        ...

    def prune(self, steps: Sequence) -> bool:
        """True when this prefix can no longer lead anywhere valid."""
        ...


class _Base:
    """Default ``prune``: no early cut. Override where a prefix can be judged."""

    def prune(self, steps: Sequence) -> bool:
        return False


@dataclass(frozen=True)
class KeepB2B(_Base):
    """Every line clear must be back-to-back eligible under ``rule``.

    Prunes at the placement that breaks the chain rather than at the leaf: a
    non-difficult clear is unrecoverable, so the whole subtree below it is dead.
    """

    rule: B2BRule = B2BRule.S2

    def _ok(self, step) -> bool:
        if not step.cleared:
            return True
        return is_difficult(step.piece, step.spin, step.cleared, self.rule,
                            perfect_clear=step.perfect_clear)

    def allows(self, route) -> bool:
        return all(self._ok(s) for s in route.steps)

    def prune(self, steps: Sequence) -> bool:
        return not all(self._ok(s) for s in steps)


@dataclass(frozen=True)
class Spin(_Base):
    """A spin clear that must happen somewhere on this line.

    ``Spin(PieceType.T, lines=2)`` is a T-spin double. Leave ``lines`` unset to
    accept any clear count, and ``kind`` unset to accept mini or full.
    """

    piece: PieceType
    lines: int | None = None
    kind: SpinType | None = None

    def _match(self, step) -> bool:
        if step.piece is not self.piece or step.spin is SpinType.NONE:
            return False
        if self.lines is not None and step.cleared != self.lines:
            return False
        if self.kind is not None and step.spin is not self.kind:
            return False
        return True

    def allows(self, route) -> bool:
        return any(self._match(s) for s in route.steps)


@dataclass(frozen=True)
class NoGravityWait(_Base):
    """Every placement must be reachable with an instant soft drop.

    Tucks and spins are free when soft drop teleports to the floor. What is not
    free is a placement needing the piece stopped partway down, which the player
    can only get by waiting for gravity.
    """

    def allows(self, route) -> bool:
        return not any(s.gravity_wait for s in route.steps)

    def prune(self, steps: Sequence) -> bool:
        return any(s.gravity_wait for s in steps)


@dataclass(frozen=True)
class Clears(_Base):
    """Exactly ``count`` lines cleared across the line."""

    count: int

    def allows(self, route) -> bool:
        return sum(s.cleared for s in route.steps) == self.count

    def prune(self, steps: Sequence) -> bool:
        return sum(s.cleared for s in steps) > self.count


@dataclass(frozen=True)
class Saves(_Base):
    """The pieces left over when the line ends — what carries into the next one.

    Written as piece letters. This is the coupling between lines: whatever a
    route saves becomes the leftover the following line starts from, which is
    why a diagram's chances are conditional and not independent.
    """

    pieces: str

    @property
    def wanted(self) -> tuple[PieceType, ...]:
        return tuple(PieceType[ch] for ch in self.pieces)

    def allows(self, route) -> bool:
        return tuple(sorted(route.saved, key=lambda p: p.value)) == tuple(
            sorted(self.wanted, key=lambda p: p.value)
        )


def allows(constraints: Sequence[Constraint], route) -> bool:
    return all(c.allows(route) for c in constraints)


def prune(constraints: Sequence[Constraint], steps: Sequence) -> bool:
    return any(c.prune(steps) for c in constraints)
