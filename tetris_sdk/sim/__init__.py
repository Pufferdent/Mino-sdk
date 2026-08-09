"""Simulation layer: reconstruct gameplay from a decoded replay.

This package turns *time + inputs + seed* into *piece positions*. It is the most
demanding consumer of the SDK, pulling in the live-play stack:

* :mod:`tetris_sdk.sim.rng` — per-platform seeded RNG (``TetrioRng``,
  ``JstrisRng``) reproducing the exact bag order.
* :mod:`tetris_sdk.sim.queue` — 7-bag :class:`Queue` and :class:`Hold`.
* :mod:`tetris_sdk.sim.handling` — DAS/ARR/SDF/DCD input-handling model.
* :mod:`tetris_sdk.sim.gravity` — per-mode gravity profile registry.
* :mod:`tetris_sdk.sim.engine` — the per-frame loop integrating the above with
  rotation and locking (reusing :mod:`tetris_sdk.engine`).

The driver that runs a decoded :class:`~tetris_sdk.replay.model.Replay` through
this stack lives in :mod:`tetris_sdk.replay.simulate`.
"""

from tetris_sdk.sim.rng import Rng, TetrioRng, JstrisRng
from tetris_sdk.sim.queue import Queue, Hold
from tetris_sdk.sim.handling import HandlingState, Motion
from tetris_sdk.sim.gravity import (
    GravityProfile,
    GRAVITY_PROFILES,
    ZENITH_FLOOR_DISTANCE,
    ZENITH_GRAVITY_BUMPS,
    ZENITH_G_LOCK_DELAY,
    ZENITH_GR_LOCK_DELAY,
    gravity_for,
    zenith_floor,
)
from tetris_sdk.sim.engine import GameState, step_frame

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
