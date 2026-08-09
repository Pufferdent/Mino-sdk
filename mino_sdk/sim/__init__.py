"""Simulation layer: reconstruct gameplay from a decoded replay.

This package turns *time + inputs + seed* into *piece positions*. It is the most
demanding consumer of the SDK, pulling in the live-play stack:

* :mod:`mino_sdk.sim.rng` — per-platform seeded RNG (``TetrioRng``,
  ``JstrisRng``) reproducing the exact bag order.
* :mod:`mino_sdk.sim.queue` — 7-bag :class:`Queue` and :class:`Hold`.
* :mod:`mino_sdk.sim.handling` — DAS/ARR/SDF/DCD input-handling model.
* :mod:`mino_sdk.sim.gravity` — per-mode gravity profile registry.
* :mod:`mino_sdk.sim.engine` — the per-frame loop integrating the above with
  rotation and locking (reusing :mod:`mino_sdk.engine`).

The driver that runs a decoded :class:`~mino_sdk.replay.model.Replay` through
this stack lives in :mod:`mino_sdk.replay.simulate`.
"""

from mino_sdk.sim.rng import Rng, TetrioRng, JstrisRng
from mino_sdk.sim.queue import Queue, Hold
from mino_sdk.sim.handling import HandlingState, Motion
from mino_sdk.sim.gravity import (
    GravityProfile,
    GRAVITY_PROFILES,
    ZENITH_FLOOR_DISTANCE,
    ZENITH_GRAVITY_BUMPS,
    ZENITH_G_LOCK_DELAY,
    ZENITH_GR_LOCK_DELAY,
    gravity_for,
    zenith_floor,
)
from mino_sdk.sim.engine import GameState, step_frame

__all__ = [
    "Rng",
    "TetrioRng",
    "JstrisRng",
    "Queue",
    "Hold",
    "HandlingState",
    "Motion",
    "GravityProfile",
    "GRAVITY_PROFILES",
    "ZENITH_FLOOR_DISTANCE",
    "ZENITH_GRAVITY_BUMPS",
    "ZENITH_G_LOCK_DELAY",
    "ZENITH_GR_LOCK_DELAY",
    "gravity_for",
    "zenith_floor",
    "GameState",
    "step_frame",
]
