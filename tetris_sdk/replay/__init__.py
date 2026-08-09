"""Replay decoding: normalized model plus TETR.IO and Jstris decoders.

This is a pure decode layer — it imports nothing from the engine/board. It turns
each platform's container into one normalized :class:`Replay` (metadata plus an
ordered input stream); simulation lives in a separate change.

Use :func:`decode_replay` for auto-detection, or the explicit
:func:`decode_tetrio` / :func:`decode_jstris`.
"""

from __future__ import annotations

import json
import os

from tetris_sdk.replay.model import (
    Handling,
    InputEvent,
    Platform,
    Replay,
    ReplayInput,
    ReplayMeta,
)
from tetris_sdk.replay.tetrio import decode_tetrio
from tetris_sdk.replay.jstris import decode_jstris

__all__ = [
    "Platform",
    "ReplayInput",
    "InputEvent",
    "Handling",
    "ReplayMeta",
    "Replay",
    "decode_tetrio",
    "decode_jstris",
    "decode_replay",
]


def _read_source(data) -> str:
    """Coerce a path, ``str``, or ``bytes`` into replay text."""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    if isinstance(data, str):
        # A filesystem path to an existing replay, or the replay text itself.
        if len(data) < 4096 and os.path.exists(data):
            with open(data, "r", encoding="utf-8") as fh:
                return fh.read()
        return data
    raise ValueError(f"unsupported replay input type: {type(data).__name__}")


def decode_replay(data) -> Replay:
    """Decode a replay, auto-detecting the platform.

    Accepts a filesystem path, a ``str``, or ``bytes``. TETR.IO is recognized as
    JSON with a ``replay.events`` shape; Jstris as an LZString blob that
    decompresses to ``{c, d}``. Anything else raises :class:`ValueError`.
    """
    text = _read_source(data)

    # TETR.IO: plain JSON carrying replay.events.
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict) and isinstance(obj.get("replay"), dict) and (
            "events" in obj["replay"]
        ):
            return decode_tetrio(obj)

    # Jstris: LZString-compressed {c, d}.
    try:
        return decode_jstris(text)
    except Exception:  # noqa: BLE001 - any failure means it is not a Jstris blob
        pass

    raise ValueError("unrecognized replay format (neither TETR.IO nor Jstris)")
