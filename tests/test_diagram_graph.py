"""The diagram optimizer: forks, scoring, save-grouping, optimal play."""
import pytest

from tetris_sdk.board import Board
from tetris_sdk.opener import Bridge, Diagram, KeepB2B, Node
from tetris_sdk.opener import hold as _hold
from tetris_sdk.pieces import PieceType
from tetris_sdk.types import Cell


def _node(cells):
    board = Board()
    for r, c in cells:
        board.set_cell(r, c, Cell.GARBAGE)
    return Node.at(board, ())


EMPTY = _node([])
O_SQUARE = _node([(0, 0), (0, 1), (1, 0), (1, 1)])
I_BAR = _node([(0, c) for c in range(4)])


def _fork():
    d = Diagram()
    d.line(EMPTY, O_SQUARE, pieces=1)
    d.line(EMPTY, I_BAR, pieces=1)
    return d

# A queue can play a 1-piece branch when its piece is in the bag's first two
# slots: 2*6! = 1440 queues each, 2*5! = 240 overlap, union 2640.


def test_fork_matches_the_bridge_union():
    assert _fork().chance_to(EMPTY) == 2640 / 5040


def test_targeting_one_branch_ignores_the_other():
    # The O branch reaches the wrong node, so taking it is worth nothing.
    assert _fork().chance_to(EMPTY, I_BAR) == 1440 / 5040


def test_scored_choice_takes_the_better_route():
    def score(route):
        return 2.0 if route.steps[0].piece is PieceType.I else 1.0

    # I early -> take I for 2 (1440 queues, overlap included); O early only
    # -> settle for 1 (1200); otherwise nothing.
    assert _fork().optimize(EMPTY, score) == (1440 * 2 + 1200) / 5040


def test_on_fail_prices_the_dead_queues():
    assert _fork().optimize(EMPTY, None, terminal=lambda n: 1.0,
                            on_fail=-1.0) == (2640 - 2400) / 5040


def test_linear_chain_is_the_product_of_its_lines():
    a = Node("v115@vhAAgH", ())
    b = Node("v115@zgh0EewwBeg0Eeywwhg0AtEehlwhBtR4BeRpglwhAtR4CeRpglwhJeAgH", ())
    c = Node("v115@pgB8GeD8BeH8CeF8EeD8EeF8BeF8JeAgH", ())
    d = Diagram()
    d.line(a, b, constraints=(KeepB2B(),))
    d.line(b, c, constraints=(KeepB2B(),))
    got = d.chance_to(a)
    want = d.chained()  # both lines save nothing, so the product is exact
    assert abs(got - want) < 1e-12


# --- saves matter: the fork line chooses what the next line starts from ----

FORK_CELLS = [(0, c) for c in range(5)] + [(1, 0), (1, 1), (1, 2)]
# The region above tiles as {I, L} (saving TJSZO) or {J, O} (saving TILSZ).
FORK_END = _node(FORK_CELLS)

# Child: a detached O square (only an O covers it - so the TILSZ save is
# dead) plus a 16-cell block over the stack that {T,J,S,Z} tiles and that
# plays 5040/5040 from the canonical TJSZO leftover order.
_HEIGHTS = {0: 2, 1: 2, 2: 2, 3: 1, 4: 1}
_ADDS = (2, 3, 4, 4, 3)
_BLOCK = [(_HEIGHTS[c] + k, c) for c in range(5) for k in range(_ADDS[c])]
CHILD = _node(FORK_CELLS + _BLOCK + [(0, 8), (0, 9), (1, 8), (1, 9)])


def test_saves_split_into_separate_states():
    d = Diagram()
    d.line(EMPTY, FORK_END, pieces=2)
    d.line(FORK_END, CHILD, pieces=5)
    report = d.explain(EMPTY, terminal=lambda node: 1.0)

    (value, rows) = report[(EMPTY, "")]
    assert {row.saved for row in rows} == {"TJSZO", "TILSZ"}
    futures = {row.saved: row.future for row in rows}
    assert futures["TJSZO"] == 1.0  # child plays every queue from this save
    assert futures["TILSZ"] == 0.0  # no O saved, the O square is unfillable

    # The expected value is exactly the coverage of the {I, L} orders: only
    # that save leads anywhere, so only its queues count.
    il_orders = [row for row in rows if row.saved == "TJSZO"]
    hits = sum(row.playable for row in il_orders)
    assert value == hits / 5040
    assert d.chance_to(EMPTY, CHILD) == value


def test_dead_branch_contributes_nothing():
    d = Diagram()
    d.line(EMPTY, FORK_END, pieces=2)
    d.line(FORK_END, CHILD, pieces=5)
    # From the TILSZ save the child has no routes at all — that is a dead
    # end (worth on_fail), not a successful end (worth terminal).
    values = d.evaluate(EMPTY, terminal=lambda node: 1.0, on_fail=-5.0)
    assert values[(FORK_END, "TILSZ")] == -5.0
    assert values[(FORK_END, "TJSZO")] == 1.0


def test_two_level_value_cross_check():
    # Hand DP: per queue, the best of {value 1 via I-bar sink, value 0 via
    # O sink} - the diagram value must equal a per-queue max computed here
    # with the same tries but none of the diagram machinery.
    d = Diagram()
    d.line(EMPTY, O_SQUARE, pieces=1)
    d.line(EMPTY, I_BAR, pieces=1)

    i_root = _hold.trie([(PieceType.I,)])
    total = 0
    for q in _hold.queues(tuple(PieceType[c] for c in "TILJSZO")):
        total += 1 if _hold.producible(q, i_root, 1) else 0
    assert d.chance_to(EMPTY, I_BAR) == total / 5040


def test_cycles_are_rejected():
    d = Diagram()
    d.line(EMPTY, FORK_END, pieces=2)
    d.line(FORK_END, EMPTY, pieces=5)
    with pytest.raises(ValueError, match="cycle"):
        d.chance_to(EMPTY)
