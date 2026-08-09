"""Fumen "quiz" hold-state machine.

A replay fumen stores the lookahead queue once, as a ``#Q=[hold](current)next``
comment on the first page. Later pages don't repeat it — the queue is *derived*
by advancing this state machine as each piece locks, accounting for hold. This
mirrors ``tetris-fumen``'s quiz logic so per-placement queues (and therefore
hold occupancy) can be reconstructed from the operation stream.
"""

from __future__ import annotations

import re

_QUIZ_RE = re.compile(r"#Q=\[(\w*)\]\((\w*)\)(\w*)")


class Quiz:
    """Immutable hold/current/next queue state; :meth:`operate` returns the next."""

    __slots__ = ("hold", "current", "rest")

    def __init__(self, hold: str, current: str, rest: str) -> None:
        self.hold = hold
        self.current = current
        self.rest = rest

    @classmethod
    def from_comment(cls, comment: str) -> "Quiz":
        m = _QUIZ_RE.match(comment or "")
        if not m:
            return cls("", "", "")
        return cls(m.group(1), m.group(2), m.group(3))

    @property
    def next(self) -> str:
        return self.rest[0] if self.rest else ""

    def queue_str(self) -> str:
        """The 7-piece lookahead string (hold + current + next), as v2 stored it."""
        if self.hold:
            return self.hold + self.current + self.rest[:5]
        return self.current + self.rest[:6]

    def operate(self, used: str) -> "Quiz":
        """Advance the queue after placing piece ``used`` (handles hold)."""
        if used == self.current:
            return self._direct()
        if used == self.hold:
            return self._swap()
        if self.hold == "" and used == self.next:
            return self._stock()
        if self.hold != "" and self.current == "" and used == self.next:
            return self._direct()
        raise ValueError(
            f"piece {used!r} not placeable from quiz "
            f"[{self.hold}]({self.current}){self.rest[:6]}")

    def _direct(self) -> "Quiz":
        if self.current == "":
            least = self.rest[1:]
            return Quiz(self.hold, least[:1], least[1:])
        return Quiz(self.hold, self.next, self.rest[1:])

    def _swap(self) -> "Quiz":
        return Quiz(self.current, self.next, self.rest[1:])

    def _stock(self) -> "Quiz":
        least = self.rest[1:]
        return Quiz(self.current, least[:1], least[1:])
