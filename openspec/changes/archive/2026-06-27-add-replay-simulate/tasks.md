## 1. RNG & queue (sim-queue) — validate first

- [x] 1.1 Create `mino_sdk/sim/rng.py` with an `Rng` protocol, `TetrioRng`, `JstrisRng` (seeded, deterministic)
- [x] 1.2 **RNG spike**: reproduce each platform's bag order from a fixture seed; confirm determinism and a collision-free, correct-length game before building further (TETR.IO RNG verified bit-exact against the canonical Park-Miller engine)
- [x] 1.3 Create `mino_sdk/sim/queue.py` with `Queue` (7-bag from an `Rng`, preview) and `Hold` (once-per-piece, resets on lock); includes the TETR.IO `no_szo` first-bag rule

## 2. Handling (sim-handling)

- [x] 2.1 Create `mino_sdk/sim/handling.py` — a state machine consuming `InputEvent`s and emitting per-frame horizontal/soft-drop motion from `Handling(das, arr, sdf, dcd)`
- [x] 2.2 Implement tap (1 cell), DAS auto-shift, ARR (incl. arr==0 to wall), SDF soft drop, and DCD re-engagement (DAS verdict resolved at subframe resolution by the driver)

## 3. Gravity (sim-gravity) — the hard part

- [x] 3.1 Create `mino_sdk/sim/gravity.py` with `GravityProfile(g, lock_delay, lock_resets, is_20g[, ramp])`
- [x] 3.2 Implement the `(platform, gamemode)` registry and `gravity_for(meta)` with a documented default + fallback signal
- [x] 3.3 Register initial profiles: TETR.IO `40l` (Sprint), TETR.IO `blitz` (level ramp), and Jstris single-player
- [x] 3.4 Implement gravity application: per-frame descent, 20G snap, lock delay, and lock-reset counting; support an explicit override

## 4. Frame engine (sim-engine)

- [x] 4.1 Create `mino_sdk/sim/engine.py` with `GameState(board, queue, hold, active, frame)` spawning the first piece
- [x] 4.2 Implement `step_frame(state, motion, gravity, ...)`: apply handling motion, rotations via `rotate`, hold, soft drop, gravity, and locking via `Board.lock(piece, classify_spin(...))`
- [x] 4.3 Detect top-out on spawn-blocked; emit `Event`s per lock

## 5. Replay driver (replay-simulate)

- [x] 5.1 Create `mino_sdk/replay/simulate.py` with `simulate(replay, *, gravity=None, engine="native") -> ReplaySim`
- [x] 5.2 Drive the frame loop from `replay.inputs` + seed + handling + gravity; collect placements, events, board snapshots
- [x] 5.3 Implement the validation report comparing reconstructed aggregates to `meta.results` (pieces placed, lines, perfect clears)
- [x] 5.4 Implement the `engine="teto"` path: route TETR.IO replays to the real `@haelp/teto` engine (`mino_sdk/replay/teto/`) for exact frame-perfect reconstruction

## 6. Public API & tests

- [x] 6.1 Export `simulate`, `ReplaySim`, `GravityProfile`, gravity registry/`gravity_for`, `TetrioRng`, `JstrisRng`, `GameState` from `mino_sdk/__init__.py`
- [x] 6.2 `tests/test_sim_queue.py` — RNG determinism; 7-bag permutation; canonical sequence; preview/refill; hold semantics; `no_szo`
- [x] 6.3 `tests/test_sim_handling.py` — tap, DAS, ARR(0), DAS carry, SDF
- [x] 6.4 `tests/test_sim_gravity.py` — registry lookup/fallback/override; blitz level ramp; 20G cap; lock timing
- [x] 6.5 `tests/test_replay_simulate.py` — reconstruct `bcf469fc701e.ttr` (40 LINES) and `cf4f62a670db.ttr` (Blitz) via `engine="teto"` and assert the validation report matches `results` exactly (pieces, lines, perfect clears); native engine and Jstris exercised structurally

## Notes / known limitations

- **Engine rotation fix**: the base `_rotate_cw` in `mino_sdk/pieces.py` rotated counter-clockwise (only the I piece matched, by spawn-row coincidence), mirroring J/L/S/T/Z placements. Fixed to a true clockwise transform with the I piece on the guideline spawn row; the affected `pieces`/`events` tests were updated.
- **`engine="teto"`** requires Node.js on `PATH` and `npm install` in `mino_sdk/replay/teto/`. The native engine is frame-accurate for most play but cannot match TETR.IO's exact sub-frame loop on demanding replays (PC loops, dense soft-drop tucks); `teto` is the documented exact fallback.
- **Jstris reconstructs exactly** (native engine), verified against the bundled PC-Mode fixture: all 2409 pieces placed, no top-out, 242 perfect clears on the required cadence (a PC at least every 10 pieces — the PC-Mode invariant; if reconstruction diverged the PCs would stop). Key pieces, all reversed from the client (`game.js`):
  - RNG: `blockRNG = alea(seed)` (Baagøe alea, string seed) + `Bag.getBlock` draw-without-replacement, `blockIds = {I0,O1,T2,L3,J4,S5,Z6}`. The alea PRNG matches the npm `alea` package and the client byte-for-byte.
  - Decode retains the DAS-vs-tap distinction (`InputEvent.das`, slam to wall at arr 0) and gravity ticks (`ReplayInput.GRAVITY`).
  - Jstris is fully **event-driven**: descent comes from `GRAVITY` ticks and locking from `HARD_DROP`; the frame-based lock-delay is TETR.IO-only (applying it to Jstris's long between-piece gaps inserted spurious locks and desynced pieces from their inputs).
