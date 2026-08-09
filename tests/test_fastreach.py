"""The bitboard search must agree with the engine, which stays the definition."""
import random

import pytest

from tetris_sdk.engine import reachable
from tetris_sdk.opener.bridge import _board_from, _cells_of, _spawn_for
from tetris_sdk.opener.fastreach import reach
from tetris_sdk.pieces import PieceType, SRS, SRSPlus

SYSTEMS = [SRS(), SRSPlus()]


def _stacks(n=25, seed=7):
    rng = random.Random(seed)
    out = [(), (0b1111111110,), (0b1000000001, 0b1000000001)]
    for _ in range(n):
        h = rng.randint(1, 5)
        rows = tuple(rng.getrandbits(10) for _ in range(h))
        while rows and rows[-1] == 0:
            rows = rows[:-1]
        out.append(rows)
    return out


@pytest.mark.parametrize("system", SYSTEMS, ids=lambda s: s.name)
def test_matches_engine_on_random_stacks(system):
    for rows in _stacks():
        board = _board_from(rows)
        for piece in PieceType:
            want = {}
            spawn = _spawn_for(rows, piece, system)
            for p in reachable(board, piece, system, spawn=spawn):
                cells = frozenset(_cells_of(piece, p.rotation, p.row, p.col,
                                            system))
                if cells not in want or p.spin.rank > want[cells].rank:
                    want[cells] = p.spin
            got = reach(rows, piece, system=system)
            assert set(got) == set(want), (rows, piece.name, system.name)
            assert got == want, (rows, piece.name, system.name, "spin mismatch")


@pytest.mark.parametrize("system", SYSTEMS, ids=lambda s: s.name)
def test_instant_is_a_subset_of_full_reachability(system):
    for rows in _stacks(10, seed=3):
        for piece in PieceType:
            assert set(reach(rows, piece, True, system)) <= \
                set(reach(rows, piece, system=system))
