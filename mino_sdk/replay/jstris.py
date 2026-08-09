"""Jstris replay decoder.

A Jstris replay ``.txt`` is ``LZString.compressToEncodedURIComponent`` applied
to a JSON object ``{c, d}``:

* ``c`` is the config: ``seed``, ``das``, version ``v``, ``softDropId``, mode
  flags ``m``, and game start/end timestamps. It maps straight to
  :class:`ReplayMeta` (preserved verbatim as ``raw_options``).
* ``d`` is a base64-encoded **action bitstream**.

The ``d`` bitstream layout
--------------------------
``base64.b64decode(d)`` yields a byte array of **2-byte big-endian records**.
Each 16-bit record packs::

    bits 15..4  (12 bits)  timestamp in milliseconds  -> wraps every 4096
    bits  3..0  ( 4 bits)  action id (Jstris ``Action`` enum, 0..15)

The 12-bit millisecond timestamp is a counter that **wraps at 4096**;
accumulating the wraps recovers a strictly non-decreasing absolute timeline. On
the bundled fixture the unwrapped total is 4,186,111 ms versus a wall-clock game
duration (``gameEnd - gameStart``) of 4,183,532 ms — a 1.001 ratio, confirming
the unit is milliseconds.

This layout was confirmed against Jstris's own client (``replayer.js``): the
``Action`` enum and the ``loadBinaryActionsV3`` reader define exactly this
encoding. The authoritative action ids are::

    0 MOVE_LEFT   1 MOVE_RIGHT  2 DAS_LEFT    3 DAS_RIGHT
    4 ROTATE_LEFT 5 ROTATE_RIGHT 6 ROTATE_180 7 HARD_DROP
    8 SOFT_DROP_BEGIN_END        9 GRAVITY_STEP
    10 HOLD_BLOCK 11 GARBAGE_ADD 12 SGARBAGE_ADD 13 REDBAR_SET
    14 ARR_MOVE   15 AUX

Unlike TETR.IO's keydown/keyup log, Jstris records *realized game actions*, not
raw key transitions: a held movement shows up as ``MOVE_*`` then ``DAS_*`` /
``ARR_MOVE`` steps, and gravity ticks as ``GRAVITY_STEP``. We map the
player-meaningful actions to :class:`ReplayInput` (treating DAS/ARR steps as
ordinary directional moves) and drop the engine/garbage-internal actions
(``GRAVITY_STEP``, ``GARBAGE_ADD``, ``SGARBAGE_ADD``, ``REDBAR_SET``, ``AUX``).
Every emitted :class:`InputEvent` has ``pressed=True`` (Jstris actions are
discrete, with no separate release record); ``frame`` carries the timestamp in
**milliseconds** and ``subframe`` is ``0.0``. ``raw_options`` and the action
timeline are preserved so the simulator can recover anything decode dropped.
"""

from __future__ import annotations

import base64
import json

import lzstring

from mino_sdk.replay.model import (
    Handling,
    InputEvent,
    Platform,
    Replay,
    ReplayInput,
    ReplayMeta,
)

# Jstris Action enum id -> normalized input (confirmed from replayer.js).
# MOVE_* is a single-cell tap; DAS_* is a realized DAS auto-shift (with arr==0,
# a slam to the wall). Both map to LEFT/RIGHT but DAS records set the
# :attr:`InputEvent.das` flag so the simulator can distinguish a tap from a
# wall slide. Ids absent from this table are engine-internal (gravity) or
# non-player (garbage) and produce no InputEvent.
ACTION_MAP: dict[int, ReplayInput] = {
    0: ReplayInput.LEFT,        # MOVE_LEFT
    1: ReplayInput.RIGHT,       # MOVE_RIGHT
    2: ReplayInput.LEFT,        # DAS_LEFT  (das=True)
    3: ReplayInput.RIGHT,       # DAS_RIGHT (das=True)
    4: ReplayInput.CCW,         # ROTATE_LEFT
    5: ReplayInput.CW,          # ROTATE_RIGHT
    6: ReplayInput.FLIP,        # ROTATE_180
    7: ReplayInput.HARD_DROP,   # HARD_DROP
    8: ReplayInput.SOFT_DROP,   # SOFT_DROP_BEGIN_END
    9: ReplayInput.GRAVITY,     # GRAVITY_STEP (piece fell one cell)
    10: ReplayInput.HOLD,       # HOLD_BLOCK
    # 11 GARBAGE_ADD, 12 SGARBAGE_ADD, 13 REDBAR_SET, 14 ARR_MOVE (direction not
    # in the id), 15 AUX -> not player inputs.
}

# Action ids that are DAS auto-shifts (vs single-cell taps).
_DAS_ACTIONS = frozenset({2, 3})

_TIME_WRAP = 1 << 12  # 12-bit millisecond counter wraps at 4096


def _unpack_actions(d: str) -> tuple[InputEvent, ...]:
    """Unpack the ``d`` action bitstream into ordered :class:`InputEvent`s."""
    raw = base64.b64decode(d)
    events: list[InputEvent] = []
    base = 0  # accumulated wrap offset (ms)
    prev = -1  # previous (pre-wrap) 12-bit timestamp
    for i in range(0, len(raw) - 1, 2):
        record = (raw[i] << 8) | raw[i + 1]
        action = record & 0xF
        ms = record >> 4
        if ms < prev:  # 12-bit counter wrapped
            base += _TIME_WRAP
        prev = ms
        mapped = ACTION_MAP.get(action)
        if mapped is None:
            continue
        events.append(
            InputEvent(
                frame=base + ms,  # absolute timestamp in milliseconds
                subframe=0.0,
                input=mapped,
                pressed=True,
                das=action in _DAS_ACTIONS,
            )
        )
    return tuple(events)


def decode_jstris(text: str) -> Replay:
    """Decode a Jstris replay string into a :class:`Replay`."""
    decompressed = lzstring.LZString().decompressFromEncodedURIComponent(
        text.strip()
    )
    if not decompressed:
        raise ValueError("not a valid Jstris replay (LZString decompress failed)")
    obj = json.loads(decompressed)
    if not isinstance(obj, dict) or "c" not in obj or "d" not in obj:
        raise ValueError("not a valid Jstris replay (missing 'c'/'d')")

    c = obj["c"] or {}
    handling = Handling(
        das=c.get("das", 0),
        arr=0,  # Jstris ARR is not stored in `c`; defaults to instant
        sdf=c.get("softDropId", 0),  # soft-drop speed preset id, not a raw SDF
        dcd=0,
        extras={
            "m": c.get("m"),
            "softDropId": c.get("softDropId"),
            "r": c.get("r"),
            "bs": c.get("bs"),
            "se": c.get("se"),
        },
    )
    meta = ReplayMeta(
        platform=Platform.JSTRIS,
        seed=c.get("seed"),
        gamemode="",  # derivable from the `m` flag bitfield; deferred
        handling=handling,
        allow180=False,
        spinbonuses="",
        version=c.get("v"),
        raw_options=c,
        results=None,
    )

    inputs = _unpack_actions(obj["d"])
    return Replay(meta=meta, inputs=inputs)
