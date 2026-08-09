"""Normalized, platform-agnostic replay model.

Replays from TETR.IO and Jstris are raw *input streams*, not board states.
This module defines the single normalized shape every decoder produces: a
:class:`Replay` carrying a :class:`ReplayMeta` and an ordered tuple of
:class:`InputEvent`. The vocabulary (:class:`ReplayInput`) is deliberately the
replay layer's own — not the engine's ``Move`` — so decode never depends on the
engine and can carry ``HOLD``, which the engine defers. The simulator maps
``ReplayInput`` to engine moves later.

Everything here is immutable; ``raw_options``/``results`` preserve the source
container verbatim so the simulator can read anything decode did not model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Platform(Enum):
    """The source platform a replay was decoded from."""

    TETRIO = "TETRIO"
    JSTRIS = "JSTRIS"


class ReplayInput(Enum):
    """A normalized replay action.

    These are player inputs, except :attr:`GRAVITY`, which is a realized engine
    gravity tick (the active piece fell one cell). Jstris records gravity in its
    action stream — it is the exact vertical-position ground truth the simulator
    needs — so it is carried here rather than dropped. TETR.IO never emits it.
    """

    LEFT = "LEFT"
    RIGHT = "RIGHT"
    SOFT_DROP = "SOFT_DROP"
    HARD_DROP = "HARD_DROP"
    CW = "CW"
    CCW = "CCW"
    FLIP = "FLIP"  # 180 rotation
    HOLD = "HOLD"
    GRAVITY = "GRAVITY"  # engine gravity tick (piece fell one cell)


@dataclass(frozen=True)
class InputEvent:
    """A single press or release at a point in the replay timeline."""

    frame: int
    subframe: float  # 0.0 when the platform has no subframe resolution
    input: ReplayInput
    pressed: bool  # True = keydown/press, False = keyup/release
    das: bool = False  # True for a realized DAS auto-shift (Jstris DAS_LEFT/RIGHT)


@dataclass(frozen=True)
class Handling:
    """Player handling settings (DAS/ARR/etc.), with platform extras."""

    das: float
    arr: float
    sdf: float
    dcd: float
    extras: dict = field(default_factory=dict)  # safelock, cancel, may20g, ...


@dataclass(frozen=True)
class ReplayMeta:
    """Everything about a replay except the input stream itself."""

    platform: Platform
    seed: object  # str | int, depending on platform
    gamemode: str  # e.g. "40l"; "" if unknown
    handling: Handling | None
    allow180: bool
    spinbonuses: str  # e.g. "all-mini", "tspins"; "" if unknown
    version: object  # str | int | float
    raw_options: dict  # untouched source options/config for the simulator
    results: dict | None = None  # final stats, when present (the simulate oracle)


@dataclass(frozen=True)
class Replay:
    """A decoded replay: metadata plus an ordered input stream."""

    meta: ReplayMeta
    inputs: tuple[InputEvent, ...]  # ordered by (frame, subframe)
