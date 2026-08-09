## Why

`add-replay-decode` turns a replay into a normalized input stream, but inputs are not gameplay. To get **board states and piece placements** we must replay those inputs through a faithful, deterministic engine that reproduces the platform's piece sequence (from the seed), input handling (DAS/ARR/SDF/DCD), gravity, and locking — frame by frame. This change builds that simulation layer and the driver that runs a decoded `Replay` through it to reconstruct the game.

This is the most demanding consumer of the SDK: it pulls in the entire live-play stack the analysis layers also need. We attempt a **native Python** reconstruction first (per the project decision), validated against each replay's own final statistics, and keep the `@haelp/teto` engine as a documented fallback for TETR.IO if native fidelity proves insufficient.

## What Changes

- **Seeded piece sequence** (`sim-queue`): per-platform RNG (`TetrioRng`, `JstrisRng`) producing the exact 7-bag order from the replay seed, plus a `Queue` (preview) and `Hold` slot.
- **Handling model** (`sim-handling`): convert held key intervals (`InputEvent` press/release over frames) into discrete horizontal/soft-drop motion using DAS, ARR, SDF, DCD.
- **Gravity** (`sim-gravity`): a **per-mode gravity profile registry** keyed by `(platform, gamemode)` — gravity is *not* in the replay and differs across TETR.IO modes (40l/Sprint, Blitz with level ramp, Quickplay, Quickplay-with-modifiers, Zen, …) and Jstris. Includes cell-gravity, 20G, lock delay, and lock-reset behavior.
- **Frame engine** (`sim-engine`): the per-frame loop that applies handling-driven inputs, gravity, rotation (reusing `rotate`/kicks), and locking (reusing `Board.lock`/`Event`), advancing the active piece and queue/hold.
- **Replay driver** (`replay-simulate`): `simulate(replay, *, gravity=None, engine="native")` that runs a decoded `Replay` through the engine and yields a reconstructed sequence of placements / board states / events, then **validates** the reconstruction against `meta.results` (pieces placed, lines, B2B, T-spins, perfect clears).

## Capabilities

### New Capabilities
- `sim-queue`: per-platform seeded RNG, 7-bag piece sequence, preview queue, and hold.
- `sim-handling`: DAS/ARR/SDF/DCD input-handling model turning input events into motion.
- `sim-gravity`: per-mode gravity profile registry (gravity, 20G, lock delay, lock resets).
- `sim-engine`: the frame-stepped live-play loop integrating queue, handling, gravity, rotation, and locking.
- `replay-simulate`: the driver that reconstructs gameplay from a decoded `Replay` and validates it against the replay's own final stats.

## Impact

- **New modules**: `tetris_sdk/sim/` — `rng.py`, `queue.py`, `handling.py`, `gravity.py`, `engine.py`; and `tetris_sdk/replay/simulate.py` (driver).
- **Reuses (already built)**: `rotate`/kicks, `Board.lock`/`Event`, `classify_spin`, `SpinType`, `reachable` (for placement enumeration / move-path checks).
- **Depends on**: `add-replay-decode` (consumes `Replay`/`InputEvent`/`Handling`/`ReplayMeta`).
- **Public API**: export `simulate`, the gravity profile registry, `TetrioRng`/`JstrisRng`, and the frame engine state type.
- **Tests**: reconstruct both fixtures (`bcf469fc701e.ttr`, `replay_28371693.txt`) and assert final stats match each replay's `results`/config.
- **Non-goals**: live multiplayer/garbage exchange between players, rendering, and exact replication of every TETR.IO mode at first (Sprint/40l and Jstris sprint are the initial validation targets; other gravity profiles are added incrementally).

## Key risks (front-loaded)

1. **RNG exactness** — if the seed→bag order is even slightly wrong, every placement is wrong. Make-or-break; validate the bag sequence first, before the rest of the stack.
2. **Gravity is hard and per-mode** — not stored in the replay, varies by TETR.IO mode and ramps with level (Blitz). The profile registry is the central design risk; getting 20G, lock delay, and lock-reset right is required for correct lock positions.
3. **Handling exactness** — DAS/ARR determine final columns; small errors shift placements.
4. **Version drift** — both platforms change behavior across versions; profiles are keyed by version where needed.
