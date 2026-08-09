"""Tests for the seeded RNG, 7-bag queue, and hold (sim-queue)."""

from tetris_sdk.pieces import PieceType
from tetris_sdk.sim.rng import TetrioRng, JstrisRng
from tetris_sdk.sim.queue import Queue, Hold

_ALL = sorted(p.value for p in PieceType)


class TestTetrioRng:
    def test_deterministic(self):
        a = [p.name for p in TetrioRng(191836487).next_bag()]
        b = [p.name for p in TetrioRng(191836487).next_bag()]
        assert a == b

    def test_bag_is_permutation(self):
        rng = TetrioRng(191836487)
        for _ in range(10):
            bag = rng.next_bag()
            assert sorted(p.value for p in bag) == _ALL

    def test_matches_canonical_sequence(self):
        # Verified against the canonical TETR.IO Park-Miller RNG (16807 LCG +
        # Fisher-Yates over ["z","l","o","s","i","j","t"]).
        rng = TetrioRng(191836487)
        seq = "".join(p.name for p in rng.next_bag())
        seq += "".join(p.name for p in rng.next_bag())
        assert seq == "JISZTLO" + "LSIJZOT"

    def test_different_seeds_differ(self):
        a = [p.name for p in TetrioRng(1).next_bag()]
        b = [p.name for p in TetrioRng(2).next_bag()]
        assert a != b


class TestJstrisRng:
    def test_deterministic_permutation(self):
        a = [p.name for p in JstrisRng("4fkj9").next_bag()]
        b = [p.name for p in JstrisRng("4fkj9").next_bag()]
        assert a == b
        assert sorted(p.value for p in JstrisRng("4fkj9").next_bag()) == _ALL

    def test_alea_matches_client(self):
        # alea("4fkj9") first floats, verified bit-exact against the npm `alea`
        # package and the Jstris client (game.js blockRNG = alea(seed)).
        from tetris_sdk.sim.rng import _alea
        rng = _alea("4fkj9")
        got = [round(rng(), 10) for _ in range(4)]
        assert got == [0.689865204, 0.8750085328, 0.7408756374, 0.9659070212]

    def test_bag_matches_client_draw(self):
        # Draw-without-replacement bag for seed "4fkj9", ids {I0,O1,T2,L3,J4,S5,Z6}.
        seq = "".join(p.name for p in JstrisRng("4fkj9").next_bag())
        assert seq == "JZLSTIO"
        assert sorted(seq) == sorted("IOTLJSZ")


class TestQueue:
    def test_preview_is_stable_and_consumed_in_order(self):
        q = Queue(TetrioRng(191836487))
        preview = q.peek(5)
        assert q.peek(5) == preview  # peek does not consume
        drawn = [q.next() for _ in range(5)]
        assert drawn == preview

    def test_refills_across_bag_boundary(self):
        q = Queue(TetrioRng(191836487))
        first14 = [q.next() for _ in range(14)]
        # two full bags
        assert sorted(p.value for p in first14[:7]) == _ALL
        assert sorted(p.value for p in first14[7:]) == _ALL

    def test_no_szo_moves_leading_szo_to_back(self):
        # Blitz seed: raw first bag is OZTLSIJ; no_szo -> TLSIJOZ.
        plain = "".join(p.name for p in Queue(TetrioRng(1366895827)).peek(7))
        assert plain == "OZTLSIJ"
        fixed = "".join(
            p.name for p in Queue(TetrioRng(1366895827), no_szo=True).peek(7)
        )
        assert fixed == "TLSIJOZ"

    def test_no_szo_noop_when_front_is_safe(self):
        # 40L seed: first bag starts with J, so no_szo changes nothing.
        plain = "".join(p.name for p in Queue(TetrioRng(191836487)).peek(7))
        fixed = "".join(
            p.name for p in Queue(TetrioRng(191836487), no_szo=True).peek(7)
        )
        assert plain == fixed == "JISZTLO"


class TestHold:
    def test_first_hold_stores_and_signals_draw(self):
        h = Hold()
        assert h.piece is None
        assert h.swap(PieceType.T) is None  # empty slot -> caller draws
        assert h.piece == PieceType.T
        assert h.used is True

    def test_swap_returns_previous(self):
        h = Hold()
        h.swap(PieceType.T)
        h.reset()
        assert h.swap(PieceType.I) == PieceType.T
        assert h.piece == PieceType.I

    def test_reset_reenables(self):
        h = Hold()
        h.swap(PieceType.T)
        assert h.used is True
        h.reset()
        assert h.used is False
