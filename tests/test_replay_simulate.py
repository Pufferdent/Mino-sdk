"""Tests for the replay-simulate driver (replay-simulate).

The exact-reconstruction assertions use the ``engine="teto"`` path (the real
TETR.IO engine) and are skipped when Node.js / the runner dependencies are not
available. The native engine is exercised for structural correctness.
"""

import pytest

from tetris_sdk.replay import decode_replay
from tetris_sdk.replay.simulate import simulate
from tetris_sdk.replay.teto import teto_available

_40L = "tests/bcf469fc701e.ttr"
_BLITZ = "tests/cf4f62a670db.ttr"
_JSTRIS = "tests/replay_28371693.txt"

needs_teto = pytest.mark.skipif(
    not teto_available(), reason="Node.js / @haelp/teto runner not available"
)


class TestTetoExact:
    @needs_teto
    def test_40l_matches_oracle(self):
        sim = simulate(decode_replay(_40L), engine="teto")
        r = sim.report
        assert sim.engine == "teto"
        assert r.pieces_placed == (100, 100)
        assert r.lines == (40, 40)
        assert r.perfect_clears == (7, 7)
        assert r.matches is True

    @needs_teto
    def test_blitz_matches_oracle(self):
        sim = simulate(decode_replay(_BLITZ), engine="teto")
        r = sim.report
        assert r.pieces_placed == (319, 319)
        assert r.lines == (126, 126)
        assert r.perfect_clears == (26, 26)
        assert r.matches is True

    @needs_teto
    def test_final_board_and_events_populated(self):
        sim = simulate(decode_replay(_40L), engine="teto")
        assert len(sim.events) == 100              # one per locked piece
        assert sum(e.lines for e in sim.events) == 40
        assert any(e.perfect_clear for e in sim.events)


class TestNativeEngine:
    def test_native_runs_and_reports(self):
        sim = simulate(decode_replay(_40L))  # engine="native" default
        assert sim.engine == "native"
        assert sim.report.pieces_placed[1] == 100   # expected from oracle
        assert sim.pieces_placed > 0
        assert isinstance(sim.lines_cleared, int)

    def test_gravity_override_accepted(self):
        from tetris_sdk.sim.gravity import GravityProfile
        sim = simulate(decode_replay(_40L), gravity=GravityProfile(g=0.0))
        assert sim.pieces_placed > 0


class TestJstris:
    def test_pc_mode_reconstructs_exactly(self):
        # The fixture is a Jstris PC-Mode game: the board is perfect-cleared
        # every 10 pieces for the entire run. A faithful reconstruction must
        # place every piece without topping out and empty the board on a strict
        # 10-piece cadence — a strong oracle even though Jstris stores no stats.
        sim = simulate(decode_replay(_JSTRIS))
        assert not sim.topped_out
        assert sim.pieces_placed == 2409

        pc_pieces = [i + 1 for i, e in enumerate(sim.events) if e.perfect_clear]
        assert len(pc_pieces) >= 240
        # In PC Mode a perfect clear lands at least every 10 pieces (loops are
        # 10 pieces, occasionally a shorter 5-piece clear). If reconstruction
        # diverges, PCs stop — so a >10 gap anywhere means something is wrong.
        assert pc_pieces[0] <= 10
        assert max(b - a for a, b in zip(pc_pieces, pc_pieces[1:])) <= 10

    def test_teto_rejects_jstris(self):
        with pytest.raises(ValueError):
            simulate(decode_replay(_JSTRIS), engine="teto")


class TestEngineArg:
    def test_unknown_engine_raises(self):
        with pytest.raises(ValueError):
            simulate(decode_replay(_40L), engine="bogus")
