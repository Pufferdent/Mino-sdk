"""Bridges: every way one node becomes another across a whole queue.

Nodes in the opener graph sit a queue apart, not a piece apart, so the edge
between them is not a placement — it is a whole bag's worth of work. A
:class:`Bridge` describes that span: how many pieces are placed, what leftover
is carried in, and every distinct way to get from one stack to the other.

The clear count is never searched for. Cells are conserved — each piece adds
four, each clear removes ten — so::

    cleared_lines = (start_cells + 4 * pieces - end_cells) / 10

A bridge whose tally is not a whole number is impossible, and reports nothing
without searching at all.

Given the tally, a bridge *is* a perfect-clear problem. Build a field of
``cleared_lines + end_height`` rows: the bottom rows empty (those are the ones
that clear) and the top rows pre-filled with the **complement** of the end
shape. Every PC of that field is exactly a bridge landing on the end state, so
the search is handed to ``sfinder.jar`` rather than reimplemented — see
:mod:`mino_sdk.pc.sfinder`.

Ordering is then solved on top of each tiling by replaying it in the **real**
frame — the complement empty, rows clearing the moment they fill — using
:func:`mino_sdk.engine.reachable`, whose search covers rotation, kicks and
movement after the drop. So routes needing a tuck or a spin are found rather
than skipped. Each placement is classified by what it costs the player: with an
instant soft drop a tuck or a spin is free, so the only expensive placement is
one needing the piece halted partway down — ``Step.gravity_wait``.

A line's *chance* is then coverage over queue space. Routes are placement
orders, but a player gets a queue and one hold slot, so most orders are out of
reach; :mod:`mino_sdk.opener.hold` decides which queues can actually produce
one. Constraints live in :mod:`mino_sdk.opener.constraints`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations

from mino_sdk.board import Board, COLS
from mino_sdk.engine import SpinType, reachable
from mino_sdk.fumen.encoder import encode_fumen
from mino_sdk.fumen.parser import parse_fumen
from mino_sdk.opener import constraints as _c
from mino_sdk.opener import fastreach as _fast
from mino_sdk.opener import hold as _hold
from mino_sdk.opener.node import Node
from mino_sdk.pieces import Piece, PieceType, RotationSystem
from mino_sdk.opener.fastreach import DEFAULT_SYSTEM
from mino_sdk.types import Cell

_ORDER = (
    PieceType.T, PieceType.I, PieceType.L, PieceType.J,
    PieceType.S, PieceType.Z, PieceType.O,
)
_DEFAULT_JAR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "reference", "sfinder.jar",
)

_FULL_ROW = (1 << COLS) - 1


# --- results ----------------------------------------------------------------

@dataclass(frozen=True)
class LineClear:
    """A clear the bridge performs, in the frame where clears resolve at the end."""

    rows: tuple[int, ...]
    lines: int

    @property
    def name(self) -> str:
        from mino_sdk.events import classify_lock
        return classify_lock(PieceType.I, SpinType.NONE, min(self.lines, 4))[1]


@dataclass(frozen=True)
class Step:
    """One placement: the piece, where it landed, and the stack it leaves."""

    piece: PieceType
    rotation: int
    row: int
    col: int
    spin: SpinType
    cells: tuple[tuple[int, int], ...]
    colors: tuple = ()
    cleared: int = 0
    gravity_wait: bool = False

    @property
    def fumen(self) -> str:
        """The stack after this placement. Encoded on demand — encoding every
        candidate during the search costs more than the search itself."""
        return _encode_colors(self.colors)

    @property
    def spun(self) -> bool:
        """True when the piece locked as a spin under the immobile rule."""
        return self.spin is not SpinType.NONE

    @property
    def note(self) -> str:
        marks = []
        if self.gravity_wait:
            marks.append("gravity-wait")
        if self.spun:
            marks.append(f"{self.spin.name.lower()}-spin")
        if self.cleared:
            marks.append(f"clear x{self.cleared}")
        return "+".join(marks)


@dataclass(frozen=True)
class Route:
    """One way across a bridge: an ordering, and the stack after each piece."""

    steps: tuple[Step, ...]
    clear: LineClear
    saved: tuple = ()

    @property
    def order(self) -> tuple[PieceType, ...]:
        return tuple(step.piece for step in self.steps)

    @property
    def spins(self) -> tuple[Step, ...]:
        """Placements that locked as a spin."""
        return tuple(s for s in self.steps if s.spun)

    @property
    def waits(self) -> tuple[Step, ...]:
        """Placements the player must ride down under gravity."""
        return tuple(s for s in self.steps if s.gravity_wait)

    @property
    def instant(self) -> bool:
        """True when every placement works with an instant soft drop."""
        return not self.waits

    @property
    def used(self) -> tuple[PieceType, ...]:
        return tuple(s.piece for s in self.steps)

    def attack(self, *, b2b: bool = False,
               rule: "B2BRule | None" = None) -> int:
        """Lines this route sends, back-to-back tracked step by step.

        ``b2b`` is whether the chain was already alive when the route began —
        what the previous line ended on. S2 rules; see
        :func:`mino_sdk.events.attack`.
        """
        from mino_sdk.events import B2BRule, attack, is_difficult
        rule = rule or B2BRule.S2
        total = 0
        for step in self.steps:
            total += attack(step.piece, step.spin, step.cleared,
                            rule=rule, b2b=b2b)
            if step.cleared:
                b2b = is_difficult(step.piece, step.spin, step.cleared, rule)
        return total

    def b2b(self, *, initial: bool = False,
            rule: "B2BRule | None" = None) -> int:
        """How many of this route's clears landed with back-to-back alive."""
        from mino_sdk.events import B2BRule, is_difficult
        rule = rule or B2BRule.S2
        count = 0
        alive = initial
        for step in self.steps:
            if not step.cleared:
                continue
            difficult = is_difficult(step.piece, step.spin, step.cleared, rule)
            if difficult and alive:
                count += 1
            alive = difficult
        return count

    def fumens(self) -> tuple[str, ...]:
        """The board state after each placement, one fumen per piece."""
        return tuple(step.fumen for step in self.steps)

    def animation(self) -> str:
        """All states as a single multi-page fumen, one page per placement."""
        pages = [(parse_fumen(step.fumen)[0], step.piece.name) for step in self.steps]
        return encode_fumen(pages)


# --- geometry ---------------------------------------------------------------

def _rows_of(node: Node) -> tuple[int, ...]:
    board = node.board()
    rows = []
    for r in range(board.rows):
        mask = 0
        for c in range(board.cols):
            if board.get_cell(r, c) != Cell.EMPTY:
                mask |= 1 << c
        rows.append(mask)
    while rows and rows[-1] == 0:
        rows.pop()
    return tuple(rows)


def _count(rows: tuple[int, ...]) -> int:
    return sum(bin(row).count("1") for row in rows)


def _cells_of(piece: PieceType, rotation: int, row: int, col: int,
              system: RotationSystem = DEFAULT_SYSTEM) -> tuple:
    return tuple(sorted(Piece(piece, rotation=rotation, row=row, col=col,
                              system=system).cells))


@lru_cache(maxsize=None)
def _board_from(rows: tuple) -> Board:
    board = Board()
    for r, mask in enumerate(rows):
        for c in range(COLS):
            if mask >> c & 1:
                board.set_cell(r, c, Cell.GARBAGE)
    return board


@lru_cache(maxsize=None)
def _orients(piece: PieceType,
             system: RotationSystem = DEFAULT_SYSTEM) -> tuple:
    """Distinct orientations as (rotation, cells, width, height), row-0/col-0 based."""
    seen: dict = {}
    for rotation in range(4):
        cells = system.rotations(piece)[rotation]
        br = min(r for r, _ in cells)
        bc = min(c for _, c in cells)
        shape = tuple(sorted((r - br, c - bc) for r, c in cells))
        seen.setdefault(shape, rotation)
    return tuple(
        (rot, shape, max(c for _, c in shape) + 1, max(r for r, _ in shape) + 1)
        for shape, rot in seen.items()
    )


@lru_cache(maxsize=None)
def _resting(rows: tuple, piece: PieceType, cap: int,
             system: RotationSystem = DEFAULT_SYSTEM) -> tuple:
    """Every position the piece can *lock* in, by geometry alone.

    Candidate generation, not reachability: a placement qualifies if its cells
    are free and it cannot fall further. Whether the player can actually get it
    there is settled later, on the few placements that survive the search.
    """
    out = []
    for rot, shape, w, h in _orients(piece, system):
        for col in range(COLS - w + 1):
            for row in range(cap - h + 1):
                cells = tuple((row + dr, col + dc) for dr, dc in shape)
                if any(r < len(rows) and rows[r] >> c & 1 for r, c in cells):
                    continue
                if not any(
                    r == 0 or ((r - 1, c) not in cells and
                               r - 1 < len(rows) and rows[r - 1] >> c & 1)
                    for r, c in cells
                ):
                    continue
                out.append((rot, row, col, cells))
    return tuple(out)


def _reach_map(rows: tuple, piece: PieceType,
               system: RotationSystem = DEFAULT_SYSTEM) -> dict:
    """``{locked cells: spin}`` — the bitboard search, checked against the engine."""
    return _fast.reach(rows, piece, system=system)


def _instant_set(rows: tuple, piece: PieceType,
                 system: RotationSystem = DEFAULT_SYSTEM) -> frozenset:
    """Placements needing no gravity wait. Only consulted when something asks."""
    return frozenset(_fast.reach(rows, piece, True, system=system))


def _spawn_for(rows: tuple, piece: PieceType,
               system: RotationSystem = DEFAULT_SYSTEM) -> Piece:
    """Spawn just above the stack rather than at row 19.

    Everything between is empty, and a piece can always slide sideways up
    there, so the low spawn reaches the same placements — it just skips the
    dozen empty rows the BFS would otherwise walk down one at a time.
    """
    shape = system.rotations(piece)[0]
    top = min(19, len(rows) + 3)
    return Piece(piece, rotation=0, row=top - min(dr for dr, _ in shape),
                 col=4 if piece == PieceType.O else 3, system=system)


def _paint(colors) -> Board:
    board = Board()
    items = colors.items() if isinstance(colors, dict) else colors
    for (r, c), piece in items:
        board.set_cell(r, c, Cell.GARBAGE if piece is None else piece.cell)
    return board


@lru_cache(maxsize=16384)
def _encode_colors(colors: tuple) -> str:
    return encode_fumen([(_paint(colors), "")])


# --- the bridge -------------------------------------------------------------

@dataclass(frozen=True)
class Bridge:
    """How one node becomes another across a queue.

    ``pieces`` defaults to a whole queue of seven. ``constraint`` is the
    leftover carried in, written as piece letters: ``""`` is a fresh bag,
    ``"O"`` an O followed by a fresh bag. The leftover is consumed in full and
    the balance drawn from the new bag.

    ``system`` is the rotation rules the player is under — TETR.IO's SRS+
    (180s included) unless told otherwise. Pass ``system=SRS()`` for guideline
    SRS, or any other :class:`~mino_sdk.pieces.RotationSystem`.
    """

    start: Node
    end: Node
    pieces: int = 7
    constraint: str = ""
    constraints: tuple = ()
    jar: str | None = None
    system: RotationSystem = DEFAULT_SYSTEM

    @property
    def leftover(self) -> tuple[PieceType, ...]:
        return tuple(PieceType[ch] for ch in self.constraint)

    @property
    def cleared_lines(self) -> int | None:
        """Lines cleared, from the mino tally; ``None`` if the tally is impossible."""
        delta = _count(_rows_of(self.start)) + 4 * self.pieces - _count(_rows_of(self.end))
        if delta < 0 or delta % COLS:
            return None
        return delta // COLS

    def pools(self) -> tuple[tuple[PieceType, ...], ...]:
        """Piece multisets this bridge can be built from."""
        need = self.pieces - len(self.leftover)
        if need < 0:
            raise ValueError("constraint is longer than the piece count")
        if need > len(_ORDER):
            raise ValueError("a bridge cannot draw more than one new bag")
        return tuple(
            tuple(sorted(self.leftover + combo, key=_ORDER.index))
            for combo in combinations(_ORDER, need)
        )

    def pattern(self) -> str:
        """The sfinder pattern covering this bridge's pools."""
        need = self.pieces - len(self.leftover)
        lead = "".join(p.name for p in self.leftover)
        terms = [f"[{lead}]p{len(self.leftover)}"] if lead else []
        terms.append(f"*p{need}")
        return ",".join(terms)

    def field(self) -> str:
        """The PC field this bridge reduces to: complement of the end above the clears."""
        clears = self.cleared_lines
        if clears is None:
            raise ValueError("bridge tally is impossible; there is no field")
        end = _rows_of(self.end)
        board = Board()
        for r, mask in enumerate(end):
            for c in range(COLS):
                if not (mask >> c & 1):
                    board.set_cell(clears + r, c, Cell.GARBAGE)
        return encode_fumen([(board, "")])

    def target(self) -> tuple[frozenset, frozenset]:
        """``(pre-clear target cells, cells the pieces must add)``.

        The target is the cleared rows — taken to be the bottom ones — with the
        end stack sitting on top. Whatever the start stack already occupies is
        not the pieces' work, so the region they fill is the difference. A start
        stack that does not fit inside the target means this line cannot happen.
        """
        clears = self.cleared_lines
        if clears is None:
            return frozenset(), frozenset()
        end = _rows_of(self.end)
        target = {(r, c) for r in range(clears) for c in range(COLS)}
        for r, mask in enumerate(end):
            target |= {(clears + r, c) for c in range(COLS) if mask >> c & 1}
        start = {
            (r, c) for r, mask in enumerate(_rows_of(self.start))
            for c in range(COLS) if mask >> c & 1
        }
        if not start <= target:
            return frozenset(), frozenset()
        return frozenset(target), frozenset(target - start)

    def _saved(self, steps) -> tuple:
        """Pieces available to this line that a route did not place."""
        pool = list(self.leftover) + list(_ORDER)
        for step in steps:
            if step.piece in pool:
                pool.remove(step.piece)
        return tuple(sorted(pool, key=_ORDER.index))

    def playable(self, queue: tuple, memo: dict | None = None) -> bool:
        """Can this exact queue be played across the line, using hold?

        Only two pieces are ever in reach — the front of the queue and whatever
        is held — so per queue this is a small search. The memo is keyed on the
        *remaining queue*, so every queue sharing a suffix shares the work.
        Enumerating all routes and then asking which queues could produce them
        does the same job the expensive way round: there are far more orderings
        than there are queues.
        """
        budget = self.cleared_lines
        if budget is None:
            return False
        target = _rows_of(self.end)
        target_cells = _count(target)
        start = _rows_of(self.start)
        memo = {} if memo is None else memo
        needs = tuple(c for c in self.constraints if type(c).__name__ == "Spin")
        per_step = tuple(c for c in self.constraints if c not in needs)

        def fits(rows) -> bool:
            return len(rows) <= len(target) and all(
                row & ~target[i] == 0 for i, row in enumerate(rows)
            )

        target_cells_set = {
            (r, c) for r, mask in enumerate(target)
            for c in range(COLS) if mask >> c & 1
        }

        def go(rows, queue, clears, placed, met) -> bool:
            if placed == self.pieces:
                return rows == target and all(met)
            key = (rows, queue, clears, met)
            hit = memo.get(key)
            if hit is not None:
                return hit
            memo[key] = False

            # With the clear budget spent the stack only grows into the end
            # shape, so anything landing outside it is dead. That collapses the
            # branching factor from every resting position to a handful.
            allowed = None
            if budget == clears:
                allowed = target_cells_set - {
                    (r, c) for r, mask in enumerate(rows)
                    for c in range(COLS) if mask >> c & 1
                }

            seen = []
            for index in (0, 1):
                if index >= len(queue):
                    break
                piece = queue[index]
                if piece in seen:
                    continue
                seen.append(piece)
                rest = queue[:index] + queue[index + 1:]
                room = len(target) + (budget - clears)
                for rot, prow, pcol, cells in _resting(rows, piece, room,
                                                       self.system):
                    if allowed is not None and not set(cells) <= allowed:
                        continue
                    stack = list(rows) + [0] * max(
                        0, max(r for r, _ in cells) + 1 - len(rows))
                    for r, c in cells:
                        stack[r] |= 1 << c
                    full = [r for r in {r for r, _ in cells}
                            if stack[r] == _FULL_ROW]
                    clears2 = clears + len(full)
                    if clears2 > budget:
                        continue
                    spin = _reach_map(rows, piece, self.system).get(
                        frozenset(cells))
                    if spin is None:
                        continue
                    waited = frozenset(cells) not in _instant_set(
                        rows, piece, self.system)
                    step = Step(piece=piece, rotation=rot, row=prow, col=pcol,
                                spin=spin, cells=cells, cleared=len(full),
                                gravity_wait=waited)
                    if _c.prune(per_step, (step,)):
                        continue
                    for r in sorted(full, reverse=True):
                        stack.pop(r)
                    while stack and stack[-1] == 0:
                        stack.pop()
                    rows2 = tuple(stack)
                    if len(rows2) > len(target) + (budget - clears2):
                        continue
                    if budget == clears2:
                        if not fits(rows2):
                            continue
                        if target_cells - _count(rows2) != 4 * (
                                self.pieces - placed - 1):
                            continue
                    met2 = tuple(m or n._match(step) for m, n in zip(met, needs))
                    if go(rows2, rest, clears2, placed + 1, met2):
                        memo[key] = True
                        return True
            return False

        return go(start, tuple(queue), 0, 0, tuple(False for _ in needs))

    def routes(self, solver=None, cap: int | None = None) -> list:
        """Every playable way across this line, found by ``solver``.

        The line knows what it is asking for — the boards, the piece budget,
        the clear tally, the constraints. It does not know how to search; that
        is the solver's job. Left unspecified, the shipped
        :class:`~mino_sdk.opener.tiles.TileSolver` is used.
        """
        if solver is None:
            from mino_sdk.opener.tiles import TileSolver
            solver = TileSolver()
        return solver.solve(self, cap)

    def odds(self, solver=None, cap: int | None = None) -> tuple[int, int]:
        """``(playable, total)`` queues — the numerator and denominator of a chance.

        Solve first, then test queues against the solves: one solve admits many
        placement orders, and hold lets many queues produce one of them. A
        ``cap`` bounds the solves and so gives a lower bound on the chance.
        """
        orders = [r.order for r in self.routes(solver, cap)]
        return _hold.coverage(orders, _ORDER, self.pieces, self.leftover)

    def chance(self, solver=None, cap: int | None = None) -> float:
        """Fraction of queues that can play this line, hold included."""
        hits, total = self.odds(solver, cap)
        return hits / total if total else 0.0


def any_odds(bridges, solver=None, cap: int | None = None) -> tuple[int, int]:
    """``(playable, total)`` queues able to play **at least one** of ``bridges``.

    This is the fork question: the same start board drawn toward several end
    boards, each line under its own constraints, and a queue counts when any
    of the alternatives works for it. A union, not a sum — the alternatives
    overlap on many queues, and per-line chances added together overstate it.

    The bridges must share a leftover: they fork from the same moment, so
    they face the same queues. Their piece counts may differ.
    """
    bridges = list(bridges)
    if not bridges:
        raise ValueError("no bridges to combine")
    if len({b.leftover for b in bridges}) != 1:
        raise ValueError(
            "forking bridges must share a leftover: they face the same queues")
    groups = [
        ([r.order for r in b.routes(solver, cap)], b.pieces) for b in bridges
    ]
    return _hold.coverage_any(groups, _ORDER, bridges[0].leftover)


def any_chance(bridges, solver=None, cap: int | None = None) -> float:
    """Fraction of queues that can play at least one of ``bridges``."""
    hits, total = any_odds(bridges, solver, cap)
    return hits / total if total else 0.0
