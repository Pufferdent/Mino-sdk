"""Opener-graph nodes: a canonical fumen plus the pieces still to come.

A node is a *key*, not a record — two fields, both irreducible:

* ``fumen`` — the stack, encoded with every filled cell painted one colour.
  Piece colours are decoration, so normalising them makes the string canonical:
  two stacks with identical occupancy produce the same fumen however they were
  built, which is what makes distinct orderings converge onto one node. It is
  also directly viewable, so every node in the graph is a link.
* ``queue`` — the pieces still to come, hold included as the first element.
  Under 7-bag a known window spans at most two bags, so a type appears at most
  twice; that multiplicity *is* the bag structure, and :meth:`Node.sets`
  recovers it by counting rather than storing it.

Everything else is calculated: placements from
:func:`tetris_sdk.engine.reachable`, spins from
:func:`tetris_sdk.engine.classify_spin`, names from :mod:`tetris_sdk.events`.
Back-to-back and combo are deliberately not node state — they are accumulated
along edges, so two routes to the same stack share a node for reachability
while still scoring their own damage.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import permutations

from tetris_sdk.board import Board
from tetris_sdk.fumen.encoder import encode_fumen
from tetris_sdk.fumen.parser import parse_fumen
from tetris_sdk.pieces import PieceType
from tetris_sdk.types import Cell

# PCReview's canonical ordering; a bag; how many bags a known queue may span.
_ORDER = (
    PieceType.T, PieceType.I, PieceType.L, PieceType.J,
    PieceType.S, PieceType.Z, PieceType.O,
)
_BAG = frozenset(_ORDER)
_MAX_SETS = 2

# Every filled cell is painted this so the encoding depends only on occupancy.
_FILL = Cell.GARBAGE


def _canonical(pieces) -> tuple[PieceType, ...]:
    return tuple(sorted(pieces, key=_ORDER.index))


def _normalized(board: Board) -> Board:
    """A copy of ``board`` with every filled cell repainted to one colour."""
    flat = Board()
    for row in range(board.rows):
        for col in range(board.cols):
            if board.get_cell(row, col) != Cell.EMPTY:
                flat.set_cell(row, col, _FILL)
    return flat


def _render(pieces: tuple[PieceType, ...], count: int) -> str:
    if frozenset(pieces) == _BAG and len(pieces) == len(_BAG):
        return f"*p{count}"
    return f"[{''.join(p.name for p in pieces)}]p{count}"


@lru_cache(maxsize=4096)
def _canonical_fumen(fumen: str) -> str:
    """Repaint every filled cell one colour and re-encode.

    Fumens drawn by hand carry piece colours. Those are decoration: two stacks
    with the same occupancy are the same node, so colour is normalised away on
    the way in and every fumen handed to a node is canonical whatever it looked
    like when it arrived.
    """
    return encode_fumen([(_normalized(parse_fumen(fumen)[0]), "")])


@dataclass(frozen=True)
class Node:
    """A node in the opener graph: a canonical fumen and the pieces to come."""

    fumen: str
    queue: tuple[PieceType, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fumen", _canonical_fumen(self.fumen))
        for piece in set(self.queue):
            if self.queue.count(piece) > _MAX_SETS:
                raise ValueError(
                    f"{piece.name} appears {self.queue.count(piece)} times; "
                    f"a known queue spans at most {_MAX_SETS} bags"
                )

    @classmethod
    def at(cls, board: Board, queue) -> "Node":
        """Build from a board; colour is normalised by the constructor."""
        return cls(encode_fumen([(_normalized(board), "")]), tuple(queue))

    def board(self) -> Board:
        """Decode the fumen back to a board for the engine."""
        return parse_fumen(self.fumen)[0]

    def sets(self) -> tuple[tuple[PieceType, ...], ...]:
        """Recover the bag structure by multiplicity, smaller set first.

        A type present twice is still pending in both bags the queue spans, so
        counting recovers the split without storing it: ``TTILO`` is ``T`` plus
        ``TILO``. Sets are in canonical order.
        """
        out: list[tuple[PieceType, ...]] = []
        left = list(self.queue)
        while left:
            layer = _canonical(dict.fromkeys(left))
            out.append(layer)
            for piece in layer:
                left.remove(piece)
        return tuple(reversed(out))

    def pattern(self) -> str:
        """Render the queue as an sfinder pattern string.

        sfinder draws each type at most once per term, so the bag split from
        :meth:`sets` becomes one term each — ``TTILO`` is ``[T]p1,[TILO]p4``.
        """
        return ",".join(_render(s, len(s)) for s in self.sets())

    def futures(self):
        """Yield every distinct order the queue could arrive in.

        Duplicates are interchangeable, so an ordering is never yielded twice —
        counting it twice would bias any coverage measured over this node.
        """
        yield from dict.fromkeys(permutations(self.queue))

    @property
    def active(self) -> tuple[PieceType, ...]:
        """The pieces placeable now: the queue head and, via hold, the next.

        Deduplicated — when both are the same type, holding changes nothing.
        """
        return tuple(dict.fromkeys(self.queue[:2]))

    def consume(self, index: int, board: Board, drawn: PieceType | None = None) -> "Node":
        """Play ``queue[index]`` onto ``board``, optionally revealing ``drawn``.

        ``index`` is 0 for the head or 1 to hold it and play the next, which is
        the whole of hold semantics: consuming index 1 leaves the head in front.
        """
        if not 0 <= index < len(self.queue):
            raise IndexError(f"queue index {index} out of range")
        if index > 1:
            raise ValueError("only the first two queue entries are placeable")
        queue = self.queue[:index] + self.queue[index + 1:]
        if drawn is not None:
            queue += (drawn,)
        return Node.at(board, queue)

    def holes(self) -> int:
        """Empty cells with at least one filled cell somewhere above them."""
        board = self.board()
        count = 0
        for col in range(board.cols):
            covered = False
            for row in reversed(range(board.rows)):
                if board.get_cell(row, col) != Cell.EMPTY:
                    covered = True
                elif covered:
                    count += 1
        return count

    def mirrored(self) -> "Node":
        """The left-right reflection of this node's stack, queue unchanged."""
        board = self.board()
        flipped = Board()
        for row in range(board.rows):
            for col in range(board.cols):
                if board.get_cell(row, col) != Cell.EMPTY:
                    flipped.set_cell(row, board.cols - 1 - col, _FILL)
        return Node.at(flipped, self.queue)
