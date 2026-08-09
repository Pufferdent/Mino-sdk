"""Replay driver: reconstruct gameplay from a decoded :class:`Replay`.

:func:`simulate` runs a decoded replay through the :mod:`mino_sdk.sim` stack —
seeded RNG → queue/hold, handling, gravity, frame engine — and returns a
:class:`ReplaySim` with the final board, the per-lock :class:`Event` stream, and
a :class:`ValidationReport` comparing reconstructed aggregates to the replay's
own final statistics (the built-in oracle).

Two platform timelines are handled:

* **TETR.IO** records *raw key transitions* (keydown/keyup) at 60 fps; the
  handling model turns held intervals into DAS/ARR/SDF motion. Its
  ``replay.results.stats`` provides a strong oracle (pieces placed, lines, and
  the clear breakdown) asserted by the tests.
* **Jstris** records *realized discrete actions* in milliseconds: taps, DAS
  auto-shifts (``InputEvent.das``; slam to the wall at ``arr==0``), toggled soft
  drop, gravity ticks (:attr:`ReplayInput.GRAVITY`), rotations, hold, and hard
  drop. The piece sequence comes from Jstris's alea PRNG (verified bit-exact),
  so the simulator drives these directly. Jstris carries no final-stats oracle,
  so its reconstruction is validated for plausibility rather than against stored
  stats.

``engine="teto"`` routes TETR.IO replays to the real ``@haelp/teto`` engine (via
:mod:`mino_sdk.replay.teto`) for an exact, frame-perfect reconstruction — the
documented fallback for the demanding replays where native fidelity stalls.
"""

from __future__ import annotations

from dataclasses import dataclass

from mino_sdk.board import Board
from mino_sdk.engine import Move, SpinType, translate
from mino_sdk.events import B2BRule, Event, classify_lock, is_difficult
from mino_sdk.pieces import SRS, SRSPlus, PieceType, RotationSystem
from mino_sdk.replay.model import Platform, Replay, ReplayInput
from mino_sdk.types import Cell
from mino_sdk.sim.engine import (
    GameState,
    hard_drop,
    hold_piece,
    move,
    rotate_piece,
    soft_drop_to,
    spawn_next,
    step_frame,
)
from mino_sdk.sim.gravity import GravityProfile, gravity_for
from mino_sdk.sim.handling import FLOOR, WALL, HandlingState, Motion
from mino_sdk.sim.queue import Hold, Queue
from mino_sdk.sim.rng import JstrisRng, Rng, TetrioRng

# Frames to keep stepping after the last input so a non-hard-dropped final
# piece can settle and lock under gravity/lock-delay.
_SETTLE_FRAMES = 300

_ROT = {
    ReplayInput.CW: Move.CW,
    ReplayInput.CCW: Move.CCW,
    ReplayInput.FLIP: Move.FLIP,
}


@dataclass(frozen=True)
class ValidationReport:
    """Reconstructed aggregates vs. the replay's own final statistics.

    Each field is ``(reconstructed, expected)``; ``expected`` is ``None`` when
    the platform carries no oracle (Jstris). :attr:`matches` is the overall
    verdict: exact agreement on the available fields for TETR.IO, or a
    plausibility check for Jstris.
    """

    pieces_placed: tuple[int, int | None]
    lines: tuple[int, int | None]
    singles: tuple[int, int | None]
    doubles: tuple[int, int | None]
    triples: tuple[int, int | None]
    quads: tuple[int, int | None]
    perfect_clears: tuple[int, int | None]
    matches: bool


@dataclass
class ReplaySim:
    """The reconstructed result of simulating a replay."""

    replay: Replay
    final_board: Board
    events: tuple[Event, ...]
    pieces_placed: int
    lines_cleared: int
    topped_out: bool
    report: ValidationReport
    engine: str = "native"


def _rng_for(replay: Replay) -> Rng:
    seed = replay.meta.seed
    if replay.meta.platform == Platform.TETRIO:
        return TetrioRng(int(seed))
    # Jstris seeds the alea PRNG with the raw string seed (e.g. "4fkj9").
    return JstrisRng(seed)


def _classify_das(replay: Replay) -> dict[int, bool]:
    """Mark each LEFT/RIGHT press as a DAS hold (held >= das) or a tap.

    Pairs each directional keydown with its matching keyup at subframe
    resolution; a press whose held duration reaches the player's ``das`` is a
    DAS auto-shift, otherwise a one-cell tap. This resolves borderline presses
    exactly, instead of letting integer-frame rounding flip the verdict. Keyed
    by ``id(event)``.
    """
    das = float(replay.meta.handling.das) if replay.meta.handling else 10.0
    verdict: dict[int, bool] = {}
    open_press: dict[ReplayInput, list] = {ReplayInput.LEFT: [], ReplayInput.RIGHT: []}
    for ev in replay.inputs:
        if ev.input not in open_press:
            continue
        t = ev.frame + ev.subframe
        if ev.pressed:
            open_press[ev.input].append((ev, t))
        elif open_press[ev.input]:
            press_ev, pt = open_press[ev.input].pop(0)
            verdict[id(press_ev)] = (t - pt) >= das
    # Presses never released (held to game end) count as DAS holds.
    for pending in open_press.values():
        for press_ev, _ in pending:
            verdict[id(press_ev)] = True
    return verdict


def _system_for(replay: Replay) -> RotationSystem:
    # TETR.IO uses SRS+ (180 kicks); Jstris uses guideline SRS.
    return SRSPlus() if replay.meta.platform == Platform.TETRIO else SRS()


def _to_engine_frame(replay: Replay, raw_frame: int) -> int:
    """Map a replay input's frame to a 60 fps engine frame index."""
    if replay.meta.platform == Platform.JSTRIS:
        return int(raw_frame * 60 // 1000)  # Jstris frames are milliseconds
    return int(raw_frame)


def _apply_tetrio(state: GameState, handling: HandlingState, inp: ReplayInput,
                 pressed: bool, is_das: bool = False) -> None:
    """Apply one TETR.IO key transition (raw keydown/keyup)."""
    if inp == ReplayInput.LEFT:
        if pressed:
            move(state, handling.press_dir(-1, is_das))
        else:
            handling.release_dir(-1)
    elif inp == ReplayInput.RIGHT:
        if pressed:
            move(state, handling.press_dir(1, is_das))
        else:
            handling.release_dir(1)
    elif inp == ReplayInput.SOFT_DROP:
        handling.press_soft() if pressed else handling.release_soft()
    elif not pressed:
        return  # the remaining inputs act only on keydown
    elif inp in _ROT:
        rotate_piece(state, _ROT[inp])
    elif inp == ReplayInput.HOLD:
        hold_piece(state)
    elif inp == ReplayInput.HARD_DROP:
        hard_drop(state)


def _apply_jstris(state: GameState, ev) -> None:
    """Apply one Jstris realized action (discrete, always a keydown).

    Jstris records *realized* actions, so handling is direct:

    * a ``das`` directional event is an auto-shift — with Jstris's typical
      ``arr==0`` it slams to the wall (moves until blocked); a plain move is a
      one-cell tap;
    * ``SOFT_DROP`` is a *toggle* (begin/end), not a one-shot. While soft is
      held, the piece settles to its resting row after the toggle and after each
      subsequent move/rotation (Jstris soft-drop is effectively instant), which
      is what makes soft-drop tucks land correctly.
    """
    inp = ev.input
    soft = getattr(state, "_jstris_soft", False)

    if inp == ReplayInput.GRAVITY:
        if state.active is not None:  # piece fell one cell
            nxt = translate(state.board, state.active, -1, 0)
            if nxt is not None:
                state.active = nxt
        return
    if inp == ReplayInput.LEFT:
        move(state, -WALL if ev.das else -1)
    elif inp == ReplayInput.RIGHT:
        move(state, WALL if ev.das else 1)
    elif inp in _ROT:
        rotate_piece(state, _ROT[inp])
    elif inp == ReplayInput.HOLD:
        hold_piece(state)
        soft = False  # fresh piece; soft re-engages only on the next toggle
    elif inp == ReplayInput.HARD_DROP:
        hard_drop(state)
        state._jstris_soft = False
        return
    elif inp == ReplayInput.SOFT_DROP:
        soft = not soft

    state._jstris_soft = soft
    if soft:
        soft_drop_to(state, FLOOR)  # settle to rest while soft is engaged


def _build_report(replay: Replay, state: GameState) -> ValidationReport:
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    pc = 0
    for ev in state.events:
        if ev.lines in counts:
            counts[ev.lines] += 1
        if ev.perfect_clear:
            pc += 1
    return _report(
        replay, state.pieces_placed, state.lines_cleared_total, counts, pc,
        state.topped_out,
    )


def _report(replay, pieces, lines, counts, pc, topped):
    """Build a :class:`ValidationReport` from reconstructed aggregates.

    Compares against the replay's own ``results.stats`` when present (TETR.IO).
    The per-size clear counts there split spins into their own buckets, so the
    match verdict uses the robust, unambiguous fields — pieces placed, total
    lines, and all-clears. Jstris carries no oracle, so its verdict is a
    plausibility check.
    """
    results = replay.meta.results
    if results and isinstance(results.get("stats"), dict):
        stats = results["stats"]
        clears = stats.get("clears", {}) or {}
        exp_pp = stats.get("piecesplaced")
        exp_lines = stats.get("lines")
        exp_pc = clears.get("allclear")
        exp = {
            1: clears.get("singles"),
            2: clears.get("doubles"),
            3: clears.get("triples"),
            4: clears.get("quads"),
        }
        matches = (
            pieces == exp_pp and lines == exp_lines and pc == exp_pc
        )
    else:
        exp_pp = exp_lines = exp_pc = None
        exp = {1: None, 2: None, 3: None, 4: None}
        matches = pieces > 0 and not topped

    return ValidationReport(
        pieces_placed=(pieces, exp_pp),
        lines=(lines, exp_lines),
        singles=(counts[1], exp[1]),
        doubles=(counts[2], exp[2]),
        triples=(counts[3], exp[3]),
        quads=(counts[4], exp[4]),
        perfect_clears=(pc, exp_pc),
        matches=matches,
    )


_TETO_MINO = {
    "t": Cell.T, "i": Cell.I, "l": Cell.L, "j": Cell.J,
    "s": Cell.S, "z": Cell.Z, "o": Cell.O, "gb": Cell.GARBAGE,
}
_TETO_SPIN = {"mini": SpinType.MINI, "normal": SpinType.FULL, "none": SpinType.NONE}


def _simulate_teto(replay: Replay) -> ReplaySim:
    """Reconstruct a TETR.IO replay with the real engine (exact)."""
    from mino_sdk.replay.teto import run_teto

    result = run_teto(replay)

    board = Board()
    for y, row in enumerate(result["board"]):
        for x, letter in enumerate(row):
            if letter:
                board.set_cell(y, x, _TETO_MINO.get(letter, Cell.GARBAGE))

    events: list[Event] = []
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    pc = 0
    for lock in result["locks"]:
        piece = PieceType[lock["mino"].upper()]
        spin = _TETO_SPIN.get(lock.get("spin") or "none", SpinType.NONE)
        lines = lock["lines"]
        kind, name = classify_lock(piece, spin, lines)
        difficult = is_difficult(piece, spin, lines, board.b2b_rule)
        events.append(Event(
            kind=kind, piece=piece, spin=spin, lines=lines, name=name,
            difficult=difficult, back_to_back=lock["b2b"] > 1,
            b2b=lock["b2b"], combo=lock["combo"], perfect_clear=lock["pc"],
        ))
        if lines in counts:
            counts[lines] += 1
        if lock["pc"]:
            pc += 1

    report = _report(
        replay, result["pieces"], result["lines"], counts, pc,
        result["toppedOut"],
    )
    return ReplaySim(
        replay=replay,
        final_board=board,
        events=tuple(events),
        pieces_placed=result["pieces"],
        lines_cleared=result["lines"],
        topped_out=result["toppedOut"],
        report=report,
        engine="teto",
    )


def simulate(
    replay: Replay,
    *,
    gravity: GravityProfile | None = None,
    engine: str = "native",
) -> ReplaySim:
    """Reconstruct gameplay from a decoded ``replay``.

    ``gravity`` overrides the per-mode profile resolved from the replay's
    metadata (needed for modes whose gravity is non-standard; ``native`` only).
    ``engine`` selects the backend:

    * ``"native"`` (default) — the pure-Python :mod:`mino_sdk.sim` stack;
      frame-accurate for most play.
    * ``"teto"`` — the real ``@haelp/teto`` TETR.IO engine (TETR.IO replays
      only), for an exact frame-perfect reconstruction. Requires Node.js and the
      runner's dependencies (see :mod:`mino_sdk.replay.teto`).
    """
    if engine == "teto":
        return _simulate_teto(replay)
    if engine != "native":
        raise ValueError(f"unknown engine {engine!r}")

    profile = gravity if gravity is not None else gravity_for(replay.meta)
    is_tetrio = replay.meta.platform == Platform.TETRIO
    b2b_rule = B2BRule.S2 if is_tetrio else B2BRule.S1
    system = _system_for(replay)

    das_verdict = _classify_das(replay) if is_tetrio else {}
    no_szo = bool(replay.meta.raw_options.get("no_szo")) if is_tetrio else False
    state = GameState(
        board=Board(b2b_rule=b2b_rule),
        queue=Queue(_rng_for(replay), no_szo=no_szo),
        hold=Hold(),
        system=system,
    )
    spawn_next(state)  # first piece
    handling = HandlingState(replay.meta.handling)

    # Group inputs by engine frame, preserving timeline order within a frame.
    by_frame: dict[int, list] = {}
    last_frame = 0
    for ev in replay.inputs:
        f = _to_engine_frame(replay, ev.frame)
        by_frame.setdefault(f, []).append(ev)
        last_frame = max(last_frame, f)

    frame = 0
    end = last_frame + _SETTLE_FRAMES
    while frame <= end and not state.topped_out:
        for ev in by_frame.get(frame, ()):  # already in timeline order
            if is_tetrio:
                _apply_tetrio(state, handling, ev.input, ev.pressed,
                             das_verdict.get(id(ev), False))
            else:
                _apply_jstris(state, ev)
            if state.topped_out:
                break
        # TETR.IO drives gravity/lock-delay per frame; Jstris is fully
        # event-driven (descent via GRAVITY ticks, locking via HARD_DROP), so a
        # frame-based lock-delay would insert spurious locks during its long
        # between-piece gaps and desync pieces from their inputs.
        if is_tetrio:
            step_frame(state, handling.tick(), profile)
        frame += 1

    return ReplaySim(
        replay=replay,
        final_board=state.board,
        events=tuple(state.events),
        pieces_placed=state.pieces_placed,
        lines_cleared=state.lines_cleared_total,
        topped_out=state.topped_out,
        report=_build_report(replay, state),
    )
