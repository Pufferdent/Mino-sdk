"""TETR.IO ``.ttr`` decoder.

A ``.ttr`` is plain JSON. ``replay.events`` is a list of frame-stamped records;
each ``keydown``/``keyup`` carries a ``data.key`` naming the action and a
``data.subframe``. We map each key to a :class:`ReplayInput`, drop non-input
events (``start``/``end``/garbage/...), and lift ``replay.options``, the
top-level ``gamemode``, and ``replay.results`` into :class:`ReplayMeta`.

This path is engine-agnostic and low-risk: no simulation, no board state.
"""

from __future__ import annotations

from mino_sdk.replay.model import (
    Handling,
    InputEvent,
    Platform,
    Replay,
    ReplayInput,
    ReplayMeta,
)

# data.key -> normalized input. Keys outside this table are not inputs.
KEY_MAP: dict[str, ReplayInput] = {
    "moveLeft": ReplayInput.LEFT,
    "moveRight": ReplayInput.RIGHT,
    "softDrop": ReplayInput.SOFT_DROP,
    "hardDrop": ReplayInput.HARD_DROP,
    "rotateCW": ReplayInput.CW,
    "rotateCCW": ReplayInput.CCW,
    "rotate180": ReplayInput.FLIP,
    "hold": ReplayInput.HOLD,
}


def _handling(options: dict) -> Handling | None:
    """Build :class:`Handling` from ``options.handling``, if present."""
    h = options.get("handling")
    if not isinstance(h, dict):
        return None
    known = {"arr", "das", "sdf", "dcd"}
    extras = {k: v for k, v in h.items() if k not in known}
    return Handling(
        das=h.get("das", 0),
        arr=h.get("arr", 0),
        sdf=h.get("sdf", 0),
        dcd=h.get("dcd", 0),
        extras=extras,
    )


def decode_tetrio(obj: dict) -> Replay:
    """Decode a parsed TETR.IO ``.ttr`` JSON object into a :class:`Replay`."""
    replay = obj.get("replay", {})
    options = replay.get("options", {}) or {}

    meta = ReplayMeta(
        platform=Platform.TETRIO,
        seed=options.get("seed"),
        gamemode=obj.get("gamemode", "") or "",
        handling=_handling(options),
        allow180=bool(options.get("allow180", False)),
        spinbonuses=options.get("spinbonuses", "") or "",
        version=options.get("version"),
        raw_options=options,
        results=replay.get("results"),
    )

    events: list[InputEvent] = []
    for ev in replay.get("events", []):
        if ev.get("type") not in ("keydown", "keyup"):
            continue
        data = ev.get("data", {}) or {}
        mapped = KEY_MAP.get(data.get("key"))
        if mapped is None:
            continue
        events.append(
            InputEvent(
                frame=ev.get("frame", 0),
                subframe=float(data.get("subframe", 0.0)),
                input=mapped,
                pressed=ev.get("type") == "keydown",
            )
        )

    events.sort(key=lambda e: (e.frame, e.subframe))
    return Replay(meta=meta, inputs=tuple(events))
