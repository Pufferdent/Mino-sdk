"""A diagram: the boards you drew, the lines between them, and their chances.

This is the shape the work usually arrives in — a sequence of stacks sketched
out, each a bag apart, with something required of the play between them. Turn
each board into a fumen, name the lines, attach constraints, ask for the odds::

    d = Diagram()
    a, b, c = d.board(fumen_a), d.board(fumen_b), d.board(fumen_c)
    d.line(a, b, constraints=[KeepB2B()])
    d.line(b, c, constraints=[KeepB2B(), Spin(PieceType.T, lines=2)])
    d.chances()

Lines are not independent. Whatever a line leaves in hold is what the next line
starts holding, so the second chance is conditional on the first and
:meth:`Diagram.chances` reports the running product alongside each line.

Diagrams may also fork — several lines drawn from the same board — and then the
question is not one chain's chance but *what a player choosing well can expect*.
:meth:`Diagram.optimize` answers it: you write a scoring function over a route
(that is the whole interface — any callable taking a
:class:`~tetris_sdk.opener.bridge.Route`), and every queue is attributed to the
playable way through with the highest score plus expected future::

    def score(route):
        pts = 0.0
        for step in route.steps:
            if step.cleared and step.spun:  pts += 1.0   # spin clears keep B2B
            elif step.cleared == 4:         pts += 1.0   # so do quads
            elif step.cleared:              pts += 0.4   # plain clears
        return pts

    d.optimize(a, score)                  # expected score, playing optimally
    d.chance_to(a, target)                # probability sugar over the same walk

The semantics, stated once: the player sees the current bag when choosing (per
queue), bags are independent of each other, choosing a route also chooses what
it saves (the leftover the next line starts from), and the diagram must be
acyclic. Values are computed upside down — leaves first, then any state whose
children are done — with no cleverness beyond that.

One simplification to know about, inherited from how lines have always taken
their leftover: a save is carried as a *canonically ordered* string, so the
next line sees those pieces arrive in that fixed order. In real play the
unspent pieces keep whatever relative order the actual queue gave them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tetris_sdk.opener import hold as _hold
from tetris_sdk.opener.bridge import _ORDER, Bridge
from tetris_sdk.opener.fastreach import DEFAULT_SYSTEM
from tetris_sdk.opener.node import Node
from tetris_sdk.pieces import PieceType, RotationSystem


@dataclass(frozen=True)
class Odds:
    """One line's result: its own chance, and the chance of reaching its end."""

    line: "Line"
    playable: int
    total: int

    @property
    def chance(self) -> float:
        return self.playable / self.total if self.total else 0.0


@dataclass(frozen=True)
class Choice:
    """One way to play one line, as :meth:`Diagram.explain` reports it."""

    line: "Line"
    score: float
    saved: str
    playable: int
    total: int
    future: float

    @property
    def chance(self) -> float:
        return self.playable / self.total if self.total else 0.0


@dataclass
class Line:
    """A line of the diagram — one bag of play between two boards."""

    start: Node
    end: Node
    pieces: int = 7
    constraints: tuple = ()
    leftover: str = ""
    label: str = ""

    def bridge(self, jar: str | None = None,
               system: RotationSystem = DEFAULT_SYSTEM,
               leftover: str | None = None) -> Bridge:
        """``leftover`` supplies the graph walk's carry; an explicit
        ``line.leftover`` still wins, as it always has."""
        return Bridge(
            start=self.start, end=self.end, pieces=self.pieces,
            constraint=self.leftover or (leftover or ""),
            constraints=tuple(self.constraints),
            jar=jar, system=system,
        )


@dataclass
class Diagram:
    """Boards and the lines between them.

    ``system`` is the rotation rules every line is judged under — TETR.IO's
    SRS+ by default; pass ``system=SRS()`` (or any other system) to change.
    """

    lines: list = field(default_factory=list)
    jar: str | None = None
    system: RotationSystem = DEFAULT_SYSTEM

    def board(self, fumen: str) -> Node:
        """A board in the diagram, from the fumen you drew it as."""
        return Node(fumen, ())

    def line(
        self,
        start: Node,
        end: Node,
        *,
        pieces: int = 7,
        constraints=(),
        leftover: str = "",
        label: str = "",
    ) -> Line:
        line = Line(start, end, pieces, tuple(constraints), leftover, label)
        self.lines.append(line)
        return line

    def chances(self, solver=None, cap: int | None = None) -> list:
        """Each line's odds, in order.

        A line inherits the previous line's saved pieces as its leftover unless
        one was set explicitly, which is what makes these conditional.
        """
        out: list = []
        carried = ""
        for line in self.lines:
            if not line.leftover and carried:
                line.leftover = carried
            bridge = line.bridge(self.jar, self.system)
            routes = bridge.routes(solver, cap)
            playable, total = _hold.coverage(
                [r.order for r in routes], _ORDER, bridge.pieces, bridge.leftover)
            out.append(Odds(line, playable, total))
            carried = "".join(p.name for p in routes[0].saved) if routes else ""
        return out

    def chained(self, solver=None, cap: int | None = None) -> float:
        """The chance of getting all the way through, as a running product."""
        product = 1.0
        for odds in self.chances(solver, cap):
            product *= odds.chance
        return product

    # --- the optimizer -----------------------------------------------------

    def optimize(self, start: Node, score=None, *, terminal=None,
                 on_fail: float = 0.0, leftover: str = "", stop=(),
                 solver=None, cap: int | None = None) -> float:
        """Expected score from ``start``, playing every queue optimally.

        ``score`` is the whole interface: any callable judging a
        :class:`~tetris_sdk.opener.bridge.Route` (``None`` scores everything
        0, which turns this into pure reachability). ``terminal`` optionally
        scores where the play ends (``callable(Node) -> float``); ``on_fail``
        is what a queue earns when no line is playable — a large negative
        models death. Nodes in ``stop`` are treated as ends even if lines
        continue past them. A ``cap`` bounds each line's routes, so the value
        becomes a lower bound in the same sense as :meth:`Bridge.odds`.
        """
        values, _ = self._walk(start, score, terminal, on_fail, leftover,
                               stop, solver, cap)
        return values[(start, leftover)]

    def evaluate(self, start: Node, score=None, *, terminal=None,
                 on_fail: float = 0.0, leftover: str = "", stop=(),
                 solver=None, cap: int | None = None) -> dict:
        """Every reachable ``(node, leftover)`` state's optimal value."""
        values, _ = self._walk(start, score, terminal, on_fail, leftover,
                               stop, solver, cap)
        return values

    def explain(self, start: Node, score=None, *, terminal=None,
                on_fail: float = 0.0, leftover: str = "", stop=(),
                solver=None, cap: int | None = None) -> dict:
        """Per state: its value, and every choice with its own numbers."""
        values, options = self._walk(start, score, terminal, on_fail,
                                     leftover, stop, solver, cap)
        report: dict = {}
        for state, opts in options.items():
            rows = []
            for line, pts, saved, root, pieces, child in opts:
                every = _hold.queues(_ORDER, _pieces_of(state[1]))
                playable = sum(
                    1 for q in every if _hold.producible(q, root, pieces))
                rows.append(Choice(line, pts, saved, playable, len(every),
                                   values[child]))
            report[state] = (values[state], rows)
        return report

    def chance_to(self, start: Node, target: Node | None = None, *,
                  leftover: str = "", solver=None,
                  cap: int | None = None) -> float:
        """Probability of reaching ``target`` (any end, when ``None``).

        Sugar over :meth:`optimize`: no scores, worth 1 where you wanted to
        get and 0 anywhere else the play stops.
        """
        if target is None:
            return self.optimize(start, terminal=lambda node: 1.0,
                                 leftover=leftover, solver=solver, cap=cap)
        return self.optimize(
            start, terminal=lambda node: 1.0 if node == target else 0.0,
            leftover=leftover, stop=(target,), solver=solver, cap=cap)

    def _walk(self, start, score, terminal, on_fail, leftover, stop,
              solver, cap):
        """Discover states going down, then value them going up."""
        adj: dict = {}
        for line in self.lines:
            adj.setdefault(line.start, []).append(line)
        self._check_acyclic(adj, start)

        score = score or (lambda route: 0.0)
        terminal = terminal or (lambda node: 0.0)
        stop = set(stop)

        # Down: every (node, leftover) the play could visit, with its options.
        # An option is one way to play one line — routes sharing a score and a
        # save are interchangeable, so they share a trie and one entry here.
        options: dict = {}
        ends: set = set()
        todo = [(start, leftover)]
        while todo:
            node, left = state = todo.pop()
            if state in options:
                continue
            opts: list = []
            if node in stop or node not in adj:
                # A true end: nothing was drawn past this board. A state
                # whose lines exist but yield no routes is NOT an end — it
                # is a dead end, and every queue there fails.
                ends.add(state)
            else:
                for line in adj.get(node, ()):
                    bridge = line.bridge(self.jar, self.system, leftover=left)
                    groups: dict = {}
                    for route in bridge.routes(solver, cap):
                        saved = "".join(p.name for p in route.saved)
                        key = (float(score(route)), saved)
                        groups.setdefault(key, []).append(route.order)
                    for (pts, saved), orders in groups.items():
                        child = (line.end, saved)
                        opts.append((line, pts, saved, _hold.trie(orders),
                                     bridge.pieces, child))
                        todo.append(child)
            options[state] = opts

        # Up: leaves first, then any state whose children are all valued.
        # On a DAG every round resolves something, so this always finishes.
        values: dict = {}
        while len(values) < len(options):
            progressed = False
            for state, opts in options.items():
                if state in values or any(
                        opt[5] not in values for opt in opts):
                    continue
                node, left = state
                if state in ends:
                    values[state] = terminal(node)
                elif not opts:
                    values[state] = on_fail  # dead end: lines, but no way
                else:
                    # Options sorted best-first: a queue takes the first one
                    # it can play, which is exactly the max.
                    ranked = sorted(
                        ((pts + values[child], root, pieces)
                         for _, pts, _, root, pieces, child in opts),
                        key=lambda option: -option[0])
                    total = 0.0
                    every = _hold.queues(_ORDER, _pieces_of(left))
                    for q in every:
                        for worth, root, pieces in ranked:
                            if _hold.producible(q, root, pieces):
                                total += worth
                                break
                        else:
                            total += on_fail
                    values[state] = total / len(every)
                progressed = True
            if not progressed:  # pragma: no cover - unreachable on a DAG
                raise RuntimeError("state graph did not resolve")
        return values, options

    def _check_acyclic(self, adj: dict, start: Node) -> None:
        """Reject cycles reachable from ``start`` — loops are a later story."""
        DOING, DONE = 1, 2
        state: dict = {}

        def visit(node):
            state[node] = DOING
            for line in adj.get(node, ()):
                mark = state.get(line.end)
                if mark == DOING:
                    raise ValueError(
                        "diagram has a cycle; loop analysis is not supported")
                if mark is None:
                    visit(line.end)
            state[node] = DONE

        visit(start)


def _pieces_of(leftover: str) -> tuple:
    return tuple(PieceType[ch] for ch in leftover)
