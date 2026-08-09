"""Per-mode gravity profiles.

Gravity is **not** stored in a replay — it is implied by the game mode and can
ramp with level. This module holds a registry keyed by ``(platform, gamemode)``
plus :func:`gravity_for`, which resolves a profile for a decoded
:class:`~mino_sdk.replay.model.ReplayMeta` (falling back to a sane default and
signaling when it does).

Values are pinned from TETR.IO's official client bundle (``tetr.io/js/tetrio.js``
— its ``gameModes`` config block and mode presets are plain text; see
``research/tetrio-gravity.md``):

* **TETR.IO ``40l`` (Sprint)** — CONFIRMED: the mode sets ``g = 0.02`` and
  nothing else; engine defaults give ``gincrease = 0, gmargin = 0``, so gravity
  is a true constant 0.02G.
* **TETR.IO ``blitz``** — SOLVED. Level advances with line clears
  (lines to reach level ``L`` = ``L² − 1``, with the documented L11→L12 +3
  anomaly) and gravity follows the guideline marathon curve
  ``G(L) = min(20, 1 / (60 · (levelgbase − (levelspeed/60)(L−1))^(L−1)))`` with
  ``levelgbase = 0.65``, ``levelspeed = 0.42``.
* **TETR.IO ``league`` (Tetra League)** — bundle preset: ``g = 0.02``,
  ``gincrease = 0.0035``/s after ``gmargin = 7200`` frames (2 min).
* **TETR.IO ``zenith`` (Quick Play)** — base time ramp only (``g = 0.02``,
  ``gincrease = 0.0005``/s, no margin). Floor — which is driven by altitude
  (:data:`ZENITH_FLOOR_DISTANCE`) — changes *gravity* only under the **gravity
  mod** (``g += ZENITH_GRAVITY_BUMPS[floor]``, ``lock_delay =
  ZENITH_G_LOCK_DELAY[floor]``) and the **freefall mod** (``g = 20``,
  ``lock_delay = ZENITH_GR_LOCK_DELAY[floor]``). Those tables are exported as
  data; the frame engine does not track altitude itself.
* **Jstris single-player** — near-constant low gravity (Sprint/Cheese/etc.).

The time ramp matches the client exactly: each frame past ``gmargin``,
``g += gincrease / 60``. Engine runs at 60 fps; gravity is in cells/frame
(``G``). Default lock timing is ``lock_delay = 30`` frames and
``lock_resets = 15``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from mino_sdk.replay.model import Platform, ReplayMeta

_GRAVITY_CAP = 20.0
_FPS = 60.0

# Zenith (Quick Play) floor tables, from the client bundle. Index 0 is unused
# padding; floors are 1-10. Floor is derived from altitude via
# ZENITH_FLOOR_DISTANCE; only the gravity/freefall mods apply the other tables.
ZENITH_FLOOR_DISTANCE = (0, 50, 150, 300, 450, 650, 850, 1100, 1350, 1650,
                         float("inf"))
ZENITH_GRAVITY_BUMPS = (0, 0.48, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3)
ZENITH_G_LOCK_DELAY = (0, 30, 29, 28, 27, 26, 24, 22, 20, 18, 16)
ZENITH_GR_LOCK_DELAY = (0, 24, 22, 20, 18, 16, 15, 14, 13, 12, 11)


def zenith_floor(altitude: float) -> int:
    """Quick Play floor (1-10) for an altitude in meters.

    Mirrors the client's ``GetFloorLevel``: the number of floor-distance bounds
    at or below the altitude.
    """
    return sum(1 for bound in ZENITH_FLOOR_DISTANCE if altitude >= bound) or 1

# Blitz drivers (standard; replays carry these in options).
_BLITZ_GBASE = 0.65
_BLITZ_SPEED = 0.42


def _blitz_level_for_lines(lines: int) -> int:
    """Blitz level from cumulative lines cleared.

    Step cost L→L+1 is ``2L+1`` lines, except the documented L11→L12 step which
    costs 24 (not 23). Cumulative lines to reach level ``L`` is therefore
    ``L² − 1`` up to L11.
    """
    level = 1
    cumulative = 0
    while True:
        step = 24 if level == 11 else (2 * level + 1)
        if cumulative + step > lines:
            return level
        cumulative += step
        level += 1


def _blitz_gravity(level: int, gbase: float = _BLITZ_GBASE,
                   speed: float = _BLITZ_SPEED) -> float:
    """Guideline marathon gravity curve for a Blitz level (cells/frame)."""
    sec_per_row = (gbase - (speed / 60.0) * (level - 1)) ** (level - 1)
    if sec_per_row <= 0:
        return _GRAVITY_CAP
    return min(_GRAVITY_CAP, 1.0 / (60.0 * sec_per_row))


@dataclass(frozen=True)
class GravityProfile:
    """Gravity, lock timing, and level behavior for a mode.

    ``ramp`` (level → cells/frame) overrides the constant ``g`` when present;
    ``level_for_lines`` (cumulative lines → level) drives the ramp from cleared
    lines. ``gincrease`` (G per second) adds the client's time ramp on top:
    past ``gmargin`` frames, gravity grows by ``gincrease/60`` each frame.
    ``is_20g`` snaps the piece to the bottom each step.
    """

    g: float
    lock_delay: int = 30
    lock_resets: int = 15
    is_20g: bool = False
    gincrease: float = 0.0
    gmargin: int = 0
    ramp: Callable[[int], float] | None = None
    level_for_lines: Callable[[int], int] | None = None
    name: str = ""

    def level_at(self, lines: int) -> int:
        """The level after clearing ``lines`` total lines."""
        return self.level_for_lines(lines) if self.level_for_lines else 1

    def gravity_at(self, lines: int = 0, frame: int = 0) -> float:
        """Cells/frame after ``lines`` cleared at ``frame`` (ramps applied)."""
        if self.ramp is not None:
            base = self.ramp(self.level_at(lines))
        else:
            base = self.g
        if self.gincrease:
            base += self.gincrease * max(0, frame - self.gmargin) / _FPS
        return min(_GRAVITY_CAP, base)


# Registry keyed by (platform, gamemode). gamemode "" is the per-platform
# single-player default.
GRAVITY_PROFILES: dict[tuple[Platform, str], GravityProfile] = {
    (Platform.TETRIO, "40l"): GravityProfile(
        g=0.02, lock_delay=30, lock_resets=15, name="TETR.IO 40 LINES",
    ),
    (Platform.TETRIO, "league"): GravityProfile(
        g=0.02, gincrease=0.0035, gmargin=7200,
        lock_delay=30, lock_resets=15, name="TETR.IO Tetra League",
    ),
    (Platform.TETRIO, "zenith"): GravityProfile(
        g=0.02, gincrease=0.0005, gmargin=0,
        lock_delay=30, lock_resets=15, name="TETR.IO Quick Play (no mods)",
    ),
    (Platform.TETRIO, "blitz"): GravityProfile(
        g=_blitz_gravity(1),
        lock_delay=30,
        lock_resets=15,
        ramp=_blitz_gravity,
        level_for_lines=_blitz_level_for_lines,
        name="TETR.IO Blitz",
    ),
    (Platform.JSTRIS, ""): GravityProfile(
        g=0.02, lock_delay=30, lock_resets=15, name="Jstris single-player",
    ),
}

# Fallback when no entry matches: a low constant gravity single-player profile.
_DEFAULT_PROFILE = GravityProfile(g=0.02, name="default (low gravity)")


def gravity_for(meta: ReplayMeta) -> GravityProfile:
    """Resolve a :class:`GravityProfile` for a replay's metadata.

    Looks up ``(platform, gamemode)``; for Jstris (no per-mode gamemode is
    decoded) falls back to the platform's single-player default; otherwise to a
    low-gravity default. The fallback is intentional and documented rather than
    an error so unknown modes still simulate (placements in hard-drop-heavy play
    are largely gravity-insensitive).

    Gravity drivers present in the replay's own options (``g``, ``gincrease``,
    ``gmargin``, ``locktime``, ``lockresets``) override the profile — the same
    precedence the client uses, where a mode is just a set of injected options.
    """
    key = (meta.platform, meta.gamemode or "")
    if key in GRAVITY_PROFILES:
        profile = GRAVITY_PROFILES[key]
    elif (meta.platform, "") in GRAVITY_PROFILES:
        profile = GRAVITY_PROFILES[(meta.platform, "")]
    else:
        profile = _DEFAULT_PROFILE

    opts = meta.raw_options or {}
    overrides = {
        field: opts[opt]
        for opt, field in (
            ("g", "g"), ("gincrease", "gincrease"), ("gmargin", "gmargin"),
            ("locktime", "lock_delay"), ("lockresets", "lock_resets"),
        )
        if isinstance(opts.get(opt), (int, float))
        and not isinstance(opts.get(opt), bool)
    }
    return replace(profile, **overrides) if overrides else profile
