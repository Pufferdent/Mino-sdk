"""The shipped solver: exact routes, exact coverage, real-frame semantics."""
import pytest
import random
import time
from itertools import permutations

from tetris_sdk.board import Board
from tetris_sdk.engine import SpinType
from tetris_sdk.opener import (
    Bridge,
    Clears,
    KeepB2B,
    Node,
    NoGravityWait,
    TileSolver,
)
from tetris_sdk.pieces import PieceType
from tetris_sdk.types import Cell

BAG = tuple(PieceType[ch] for ch in "TILJSZO")


def _node(cells):
    board = Board()
    for r, c in cells:
        board.set_cell(r, c, Cell.GARBAGE)
    return Node.at(board, ())


EMPTY = _node([])


def test_impossible_tally_has_no_routes():
    # 1 piece cannot turn an empty board into 3 cells.
    assert Bridge(EMPTY, _node([(0, 0), (0, 1), (0, 2)]), pieces=1).routes() == []


def test_two_line_pc_is_impossible():
    # Proved twice in OPENER_SEARCH_NOTES.md §3; the solver agrees.
    bridge = Bridge(EMPTY, EMPTY, pieces=5)
    assert bridge.cleared_lines == 2
    assert bridge.odds() == (0, 5040)


def test_zero_clear_line_and_hold_coverage():
    # 2x4 block needs two O pieces: leftover O plus the bag's O.
    end = _node([(r, c) for r in range(2) for c in range(4)])
    bridge = Bridge(EMPTY, end, pieces=2, constraint="O")
    routes = bridge.routes()
    assert {r.order for r in routes} == {(PieceType.O, PieceType.O)}
    for route in routes:
        assert route.instant and not route.spins
    # The bag O must be playable second: with one hold it must sit in the
    # bag's first two slots, so 2 * 720 of the 5040 queues qualify.
    assert bridge.odds() == (1440, 5040)


def test_stretched_route_across_a_cleared_row():
    # Vertical I at col 0 clears row 1; the second vertical I then straddles
    # the vanished row (a stretched footprint in the lifted frame). The
    # reverse order collides at (1, 1) and must be absent.
    start = _node([(0, c) for c in range(2, 10)] +
                  [(1, c) for c in range(1, 10)])
    end = _node([(0, 0), (0, 1), (1, 0), (1, 1), (2, 1)])
    bridge = Bridge(start, end, pieces=2, constraint="II")
    routes = bridge.routes()
    assert len(routes) == 1
    (route,) = routes
    assert [sorted({c for _, c in s.cells}) for s in route.steps] == [[0], [1]]
    assert [s.cleared for s in route.steps] == [1, 1]


def test_t_spin_double_is_found_and_classified():
    start = _node(
        [(0, c) for c in range(10) if c != 4]
        + [(1, c) for c in (0, 1, 2, 6, 7, 8, 9)]
        + [(2, 5)]
    )
    end = _node([(0, 5)])
    bridge = Bridge(start, end, pieces=1, constraint="T")
    routes = bridge.routes()
    assert len(routes) == 1
    (step,) = routes[0].steps
    assert step.piece is PieceType.T
    assert step.spin is SpinType.FULL
    assert step.cleared == 2
    # A TSD keeps back-to-back, so KeepB2B must not reject it.
    assert Bridge(start, end, pieces=1, constraint="T",
                  constraints=(KeepB2B(),)).routes()
    # S2 attack: a full T-spin double sends 4, 5 with back-to-back alive.
    assert routes[0].attack() == 4
    assert routes[0].attack(b2b=True) == 5
    assert routes[0].b2b() == 0
    assert routes[0].b2b(initial=True) == 1


MID = dict(pieces=3, constraint="I")
MID_END = [(0, 8), (0, 9)]


def test_mid_clear_line_routes_and_odds():
    # Two I pieces fill row 0 (cols 0-7), the O tops cols 8-9; row 0 clears.
    bridge = Bridge(EMPTY, _node(MID_END), **MID)
    assert bridge.cleared_lines == 1
    routes = bridge.routes()
    assert len(routes) == 6  # both I entries in every slot around the O
    assert bridge.odds() == (720, 5040)


def test_mid_clear_line_matches_playable_brute_force():
    # The strongest check: the independent per-queue forward search must
    # agree queue by queue. Sampled to keep the suite fast; the full 5040
    # sweep was run during development and matched exactly (720/5040).
    bridge = Bridge(EMPTY, _node(MID_END), **MID)
    orders = [r.order for r in bridge.routes()]
    from tetris_sdk.opener import hold as _hold
    root = _hold.trie(orders)

    memo: dict = {}
    rng = random.Random(0)
    queues = [(PieceType.I,) + p for p in permutations(BAG)]
    for queue in rng.sample(queues, 400):
        assert _hold.producible(queue, root, bridge.pieces) == \
            bridge.playable(queue, memo), queue


def test_constraints_filter_routes():
    bridge = Bridge(EMPTY, _node(MID_END), **MID)
    # The single clear is a plain I/O single - never back-to-back eligible.
    assert Bridge(EMPTY, _node(MID_END), **MID,
                  constraints=(KeepB2B(),)).routes() == []
    assert Bridge(EMPTY, _node(MID_END), **MID,
                  constraints=(Clears(1),)).odds() == bridge.odds()
    assert Bridge(EMPTY, _node(MID_END), **MID,
                  constraints=(Clears(2),)).routes() == []
    # Every placement here works with an instant soft drop.
    assert Bridge(EMPTY, _node(MID_END), **MID,
                  constraints=(NoGravityWait(),)).odds() == bridge.odds()


def test_any_odds_is_a_union_over_queues():
    # Fork from empty: end A is an O square (only O fills it), end B a flat I
    # bar (only I). One piece each, so a queue works for a branch when that
    # piece sits in the bag's first two slots (head or hold). Exactly:
    # |O early| = |I early| = 2*6! = 1440, overlap {O,I} up front = 2*5! = 240,
    # union = 1440 + 1440 - 240 = 2640.
    from tetris_sdk.opener import any_chance, any_odds
    a = Bridge(EMPTY, _node([(0, 0), (0, 1), (1, 0), (1, 1)]), pieces=1)
    b = Bridge(EMPTY, _node([(0, c) for c in range(4)]), pieces=1)
    assert a.odds() == (1440, 5040)
    assert b.odds() == (1440, 5040)
    assert any_odds([a, b]) == (2640, 5040)
    assert any_chance([a, b]) == 2640 / 5040
    # Degenerate and invalid forks.
    assert any_odds([a]) == a.odds()
    with pytest.raises(ValueError):
        any_odds([a, Bridge(EMPTY, _node([(0, 0), (0, 1), (1, 0), (1, 1)]),
                            pieces=1, constraint="O")])


def test_rotation_system_is_configurable():
    # Default is TETR.IO SRS+; guideline SRS is a parameter away. This line
    # needs no 180s, so both systems must agree exactly.
    from tetris_sdk.pieces import SRS, SRSPlus
    default = Bridge(EMPTY, _node(MID_END), **MID)
    assert default.system == SRSPlus()
    assert Bridge(EMPTY, _node(MID_END), **MID, system=SRS()).odds() == \
        default.odds()


def test_solver_seam_still_accepts_alternatives():
    class Nothing:
        def solve(self, bridge, cap=None):
            return []

    bridge = Bridge(EMPTY, _node(MID_END), **MID)
    assert bridge.routes(solver=Nothing()) == []
    assert bridge.routes(solver=TileSolver(), cap=2) != []


def test_full_bag_line_within_time_budget():
    # The 3-clear line from examples/three_bags.py - the heaviest realistic
    # case; the target is about a second per bridge.
    start = Node("v115@pgB8GeD8BeH8CeF8EeD8EeF8BeF8JeAgH", ())
    end = Node("v115@fgA8IeA8IeC8FeD8CeF8DeG8BeH8CeD8JeAgH", ())
    bridge = Bridge(start, end, pieces=7, constraints=(KeepB2B(),))
    t0 = time.monotonic()
    assert bridge.odds() == (5040, 5040)
    assert time.monotonic() - t0 < 2.0
