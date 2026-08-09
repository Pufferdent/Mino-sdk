"""Bridge to the ``@haelp/teto`` engine for exact TETR.IO reconstruction.

The native Python simulator (:mod:`tetris_sdk.sim`) is frame-accurate for most
play, but cannot match TETR.IO's exact sub-frame engine loop on the most
demanding replays (perfect-clear loops, dense soft-drop tucks). ``@haelp/teto``
*is* the TETR.IO engine, so it reproduces a replay's final statistics exactly.

This module shells out to a small Node runner (:file:`runner.mjs`) that drives
teto frame-by-frame from a decoded :class:`~tetris_sdk.replay.model.Replay` and
returns the reconstructed stats, final board, and per-lock events as JSON. It is
the ``engine="teto"`` path of :func:`tetris_sdk.replay.simulate.simulate`.

Requirements: Node.js on ``PATH`` and the runner's dependencies installed
(``npm install`` in this directory). :func:`teto_available` reports both.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from tetris_sdk.replay.model import Platform, Replay, ReplayInput

_RUNNER = Path(__file__).with_name("runner.mjs")
_NODE_MODULES = Path(__file__).with_name("node_modules")

# ReplayInput -> the TETR.IO key name the engine expects.
_KEY = {
    ReplayInput.LEFT: "moveLeft",
    ReplayInput.RIGHT: "moveRight",
    ReplayInput.SOFT_DROP: "softDrop",
    ReplayInput.HARD_DROP: "hardDrop",
    ReplayInput.CW: "rotateCW",
    ReplayInput.CCW: "rotateCCW",
    ReplayInput.FLIP: "rotate180",
    ReplayInput.HOLD: "hold",
}


class TetoUnavailableError(RuntimeError):
    """Raised when the teto engine cannot be run (no Node or deps missing)."""


def teto_available() -> bool:
    """True iff Node.js and the runner's dependencies are both present."""
    return (
        shutil.which("node") is not None
        and _RUNNER.is_file()
        and (_NODE_MODULES / "@haelp" / "teto").is_dir()
    )


def _build_job(replay: Replay) -> dict:
    events = [
        {
            "frame": int(ev.frame),
            "type": "keydown" if ev.pressed else "keyup",
            "data": {"key": _KEY[ev.input], "subframe": ev.subframe},
        }
        for ev in replay.inputs
        if ev.input in _KEY
    ]
    return {
        "gamemode": replay.meta.gamemode or "",
        "options": replay.meta.raw_options or {},
        "events": events,
    }


def run_teto(replay: Replay) -> dict:
    """Reconstruct ``replay`` with the teto engine; return the parsed result.

    The result dict has ``pieces``, ``lines``, ``clears`` (by line count),
    ``spins``, ``perfectClears``, ``toppedOut``, ``board`` (bottom-row-first
    mino-letter grid), and ``locks`` (per-piece outcomes). Raises
    :class:`TetoUnavailableError` if Node/teto is missing, or ``RuntimeError`` if
    the runner fails.
    """
    if replay.meta.platform != Platform.TETRIO:
        raise ValueError("the teto engine only reconstructs TETR.IO replays")
    if shutil.which("node") is None:
        raise TetoUnavailableError("Node.js not found on PATH")
    if not (_NODE_MODULES / "@haelp" / "teto").is_dir():
        raise TetoUnavailableError(
            f"@haelp/teto not installed; run `npm install` in {_RUNNER.parent}"
        )

    proc = subprocess.run(
        ["node", str(_RUNNER)],
        input=json.dumps(_build_job(replay)),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"teto runner failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)
