"""Tests for the DAS/ARR/SDF handling model (sim-handling)."""

from tetris_sdk.replay.model import Handling
from tetris_sdk.sim.handling import HandlingState, WALL, FLOOR


def _h(das=6.5, arr=0.0, sdf=41.0, dcd=0.0):
    return HandlingState(Handling(das=das, arr=arr, sdf=sdf, dcd=dcd))


class TestTap:
    def test_press_returns_one_cell_tap(self):
        h = _h()
        assert h.press_dir(1, is_das=False) == 1
        assert h.press_dir(-1, is_das=False) == -1

    def test_tap_does_not_auto_shift(self):
        h = _h()
        h.press_dir(1, is_das=False)
        for _ in range(20):
            assert h.tick().dx == 0  # not a DAS press -> no auto-shift


class TestDAS:
    def test_arr0_slams_to_wall_after_das(self):
        h = _h(das=6.5, arr=0.0)
        h.press_dir(1, is_das=True)
        # before DAS elapses: no shift
        for _ in range(6):
            assert h.tick().dx == 0
        # at/after DAS: slam to wall
        assert h.tick().dx == WALL

    def test_das_carries_to_next_piece_until_release(self):
        h = _h(das=6.5, arr=0.0)
        h.press_dir(-1, is_das=True)
        for _ in range(7):
            h.tick()
        assert h.tick().dx == -WALL  # still slamming while held
        h.release_dir(-1)
        assert h.tick().dx == 0

    def test_nonzero_arr_steps(self):
        h = _h(das=2.0, arr=2.0)
        h.press_dir(1, is_das=True)
        h.tick(); h.tick()  # charge to DAS (2 frames)
        # now auto-shift every arr=2 frames
        moved = sum(h.tick().dx for _ in range(8))
        assert moved >= 3  # several discrete steps to the right


class TestSoftDrop:
    def test_infinite_sdf_drops_to_floor(self):
        h = _h(sdf=41.0)
        h.press_soft()
        assert h.tick().soft == FLOOR

    def test_finite_sdf_steps(self):
        h = _h(sdf=6.0)
        h.press_soft()
        assert h.tick().soft == 6

    def test_release_stops_soft(self):
        h = _h(sdf=41.0)
        h.press_soft()
        h.release_soft()
        assert h.tick().soft == 0
