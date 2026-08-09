"""Tests for the per-mode gravity profile registry (sim-gravity)."""

import pytest

from tetris_sdk.replay.model import Platform, ReplayMeta
from tetris_sdk.sim.gravity import (
    GravityProfile,
    GRAVITY_PROFILES,
    ZENITH_G_LOCK_DELAY,
    ZENITH_GR_LOCK_DELAY,
    ZENITH_GRAVITY_BUMPS,
    gravity_for,
    zenith_floor,
)


def _meta(platform, gamemode):
    return ReplayMeta(
        platform=platform, seed=0, gamemode=gamemode, handling=None,
        allow180=False, spinbonuses="", version=0, raw_options={},
    )


class TestRegistry:
    def test_tetrio_40l_and_blitz_registered(self):
        assert (Platform.TETRIO, "40l") in GRAVITY_PROFILES
        assert (Platform.TETRIO, "blitz") in GRAVITY_PROFILES

    def test_lookup_by_mode(self):
        p = gravity_for(_meta(Platform.TETRIO, "40l"))
        assert p is GRAVITY_PROFILES[(Platform.TETRIO, "40l")]

    def test_jstris_falls_back_to_platform_default(self):
        p = gravity_for(_meta(Platform.JSTRIS, "cheese"))
        assert p is GRAVITY_PROFILES[(Platform.JSTRIS, "")]

    def test_unknown_mode_falls_back_to_default(self):
        p = gravity_for(_meta(Platform.TETRIO, "totally-unknown"))
        assert p.g > 0  # a sane low-gravity default, not an error


class TestBlitzRamp:
    def test_level_advances_with_lines(self):
        p = GRAVITY_PROFILES[(Platform.TETRIO, "blitz")]
        # Lines to reach level L is L^2 - 1 (up to L11).
        assert p.level_at(0) == 1
        assert p.level_at(3) == 2      # 2L+1 = 3 lines clears level 1
        assert p.level_at(119) == 10
        assert p.level_at(120) == 11   # 11^2 - 1 = 120

    def test_gravity_increases_with_level(self):
        p = GRAVITY_PROFILES[(Platform.TETRIO, "blitz")]
        g1 = p.gravity_at(0)       # level 1
        g_late = p.gravity_at(120)  # level 11
        assert g1 < 0.02
        assert g_late > g1
        assert g_late <= 20.0      # capped

    def test_gravity_caps_at_20(self):
        p = GRAVITY_PROFILES[(Platform.TETRIO, "blitz")]
        assert p.gravity_at(10_000) == 20.0


class TestProfile:
    def test_constant_profile_ignores_lines(self):
        p = GravityProfile(g=0.05)
        assert p.gravity_at(0) == 0.05
        assert p.gravity_at(500) == 0.05
        assert p.level_at(500) == 1

    def test_defaults(self):
        p = GRAVITY_PROFILES[(Platform.TETRIO, "40l")]
        assert p.lock_delay == 30
        assert p.lock_resets == 15

    def test_40l_is_constant_over_time(self):
        # Confirmed from the client bundle: g=0.02, no gincrease/gmargin.
        p = GRAVITY_PROFILES[(Platform.TETRIO, "40l")]
        assert p.gravity_at(0, frame=0) == 0.02
        assert p.gravity_at(40, frame=100_000) == 0.02


class TestTimeRamp:
    def test_league_ramp_starts_after_margin(self):
        p = GRAVITY_PROFILES[(Platform.TETRIO, "league")]
        assert p.gravity_at(frame=0) == 0.02
        assert p.gravity_at(frame=7200) == 0.02
        # One second past margin: g + gincrease * 1s
        assert p.gravity_at(frame=7260) == pytest.approx(0.02 + 0.0035)

    def test_zenith_ramp_has_no_margin(self):
        p = GRAVITY_PROFILES[(Platform.TETRIO, "zenith")]
        assert p.gravity_at(frame=0) == 0.02
        assert p.gravity_at(frame=60) == pytest.approx(0.02 + 0.0005)

    def test_ramp_caps_at_20(self):
        p = GravityProfile(g=0.02, gincrease=1.0)
        assert p.gravity_at(frame=100_000) == 20.0


class TestZenithFloors:
    def test_floor_from_altitude(self):
        assert zenith_floor(0) == 1
        assert zenith_floor(49.9) == 1
        assert zenith_floor(50) == 2
        assert zenith_floor(1404.75) == 9   # validated replay altitude
        assert zenith_floor(1650) == 10
        assert zenith_floor(99_999) == 10

    def test_mod_tables_cover_all_floors(self):
        # Index 0 is padding; floors 1-10.
        assert len(ZENITH_GRAVITY_BUMPS) == 11
        assert len(ZENITH_G_LOCK_DELAY) == 11
        assert len(ZENITH_GR_LOCK_DELAY) == 11
        assert ZENITH_GRAVITY_BUMPS[1] == 0.48
        assert ZENITH_G_LOCK_DELAY[10] == 16
        assert ZENITH_GR_LOCK_DELAY[10] == 11


class TestOptionOverrides:
    def test_replay_options_override_profile(self):
        meta = ReplayMeta(
            platform=Platform.TETRIO, seed=0, gamemode="zenith", handling=None,
            allow180=False, spinbonuses="", version=0,
            raw_options={"gincrease": 0.001, "locktime": 25},
        )
        p = gravity_for(meta)
        assert p.gincrease == 0.001
        assert p.lock_delay == 25
        assert p.g == 0.02  # untouched fields keep the profile value

    def test_absent_options_leave_profile_untouched(self):
        p = gravity_for(_meta(Platform.TETRIO, "league"))
        assert p == GRAVITY_PROFILES[(Platform.TETRIO, "league")]
