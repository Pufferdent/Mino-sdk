import os

import pytest

from mino_sdk import (
    InputEvent,
    Platform,
    ReplayInput,
    decode_replay,
)
from mino_sdk.replay import decode_jstris, decode_tetrio

import json

FIXTURES = os.path.dirname(__file__)
TTR = os.path.join(FIXTURES, "bcf469fc701e.ttr")
JSTRIS = os.path.join(FIXTURES, "replay_28371693.txt")


def _ordered(inputs):
    keys = [(e.frame, e.subframe) for e in inputs]
    return keys == sorted(keys)


# --- TETR.IO ---------------------------------------------------------------

def test_tetrio_metadata_and_order():
    """5.1: platform, gamemode, seed, handling.das, results, ordered inputs."""
    with open(TTR, encoding="utf-8") as fh:
        obj = json.load(fh)
    replay = decode_tetrio(obj)

    assert replay.meta.platform is Platform.TETRIO
    assert replay.meta.gamemode == "40l"
    assert replay.meta.seed is not None
    assert replay.meta.handling is not None
    assert replay.meta.handling.das  # present and non-zero
    assert replay.meta.results is not None
    assert len(replay.inputs) > 0
    assert all(isinstance(e, InputEvent) for e in replay.inputs)
    assert _ordered(replay.inputs)


def test_tetrio_key_mapping_and_non_inputs():
    """5.2: moveLeft/hardDrop/hold map with pressed; start/end yield nothing."""
    with open(TTR, encoding="utf-8") as fh:
        obj = json.load(fh)
    replay = decode_tetrio(obj)

    by_input = {}
    for e in replay.inputs:
        by_input.setdefault(e.input, []).append(e)

    # The mapped inputs are present.
    assert ReplayInput.LEFT in by_input
    assert ReplayInput.HARD_DROP in by_input
    assert ReplayInput.HOLD in by_input

    # keydown -> pressed True exists for each.
    for inp in (ReplayInput.LEFT, ReplayInput.HARD_DROP, ReplayInput.HOLD):
        assert any(e.pressed for e in by_input[inp])

    # start/end are not inputs: every event maps to a known ReplayInput.
    assert all(isinstance(e.input, ReplayInput) for e in replay.inputs)

    # Specifically: the first event is moveRight keydown at frame 0 (pressed).
    first = replay.inputs[0]
    assert first.input is ReplayInput.RIGHT
    assert first.pressed is True


# --- Jstris ----------------------------------------------------------------

def test_jstris_metadata_and_inputs():
    """5.3: platform, seed 4fkj9, das 95, non-empty ordered inputs."""
    with open(JSTRIS, encoding="utf-8") as fh:
        text = fh.read()
    replay = decode_jstris(text)

    assert replay.meta.platform is Platform.JSTRIS
    assert replay.meta.seed == "4fkj9"
    assert replay.meta.handling is not None
    assert replay.meta.handling.das == 95
    assert len(replay.inputs) > 0
    assert _ordered(replay.inputs)

    # Timestamps are absolute milliseconds: the stream must fit within the
    # game's wall-clock duration (gameEnd - gameStart). This locks the 12-bit
    # ms-with-wrap layout confirmed against the Jstris client.
    duration_ms = replay.meta.raw_options["gameEnd"] - replay.meta.raw_options["gameStart"]
    # Within 1% of wall-clock (gameStart/gameEnd include countdown/offset slack).
    assert duration_ms * 0.5 < replay.inputs[-1].frame <= duration_ms * 1.01
    # Every event maps to a player input (gravity/garbage actions are dropped).
    assert all(isinstance(e.input, ReplayInput) and e.pressed for e in replay.inputs)


# --- Auto-detection --------------------------------------------------------

def test_decode_replay_autodetects_tetrio():
    replay = decode_replay(TTR)
    assert replay.meta.platform is Platform.TETRIO


def test_decode_replay_autodetects_jstris():
    replay = decode_replay(JSTRIS)
    assert replay.meta.platform is Platform.JSTRIS


def test_decode_replay_rejects_garbage():
    with pytest.raises(ValueError):
        decode_replay("this is not a replay at all !!!")
