"""The bitboard search must agree with the engine, which stays the definition.

One rotation system and one descent mode per run — whichever ``--system`` and
``--mode`` name (see ``conftest.py``), defaulting to the opener package's own
SRS+ and full soft drop. ``benchmarks/check_reach.py`` is the same check over a
much larger stack corpus when a combination needs proving properly.
"""
import random

from mino_sdk.engine import reachable
from mino_sdk.opener.bridge import _board_from, _cells_of, _spawn_for
from mino_sdk.opener.fastreach import reach
from mino_sdk.pieces import PieceType


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


def _engine_map(rows, piece, system, instant):
    """What the engine says, keyed the way :func:`reach` keys its answer."""
    want = {}
    for p in reachable(_board_from(rows), piece, system,
                       spawn=_spawn_for(rows, piece, system), instant=instant):
        cells = frozenset(_cells_of(piece, p.rotation, p.row, p.col, system))
        if cells not in want or p.spin.rank > want[cells].rank:
            want[cells] = p.spin
    return want


def test_matches_engine_on_random_stacks(system, instant):
    """The same placements the engine finds, with the same spins.

    Equality, not containment: an instant search that quietly drops placements
    it should find passes a subset check, and that is exactly how the
    bit-parallel descent could go wrong.
    """
    for rows in _stacks():
        for piece in PieceType:
            want = _engine_map(rows, piece, system, instant)
            got = reach(rows, piece, instant, system)
            assert set(got) == set(want), (rows, piece.name, system.name)
            assert got == want, (rows, piece.name, system.name, "spin mismatch")
