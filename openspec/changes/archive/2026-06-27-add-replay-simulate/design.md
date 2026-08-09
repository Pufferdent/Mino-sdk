## Context

Reconstructing board states from a decoded `Replay` requires a deterministic, frame-accurate engine that matches the source platform. The pipeline:

```
Replay (decoded)
   │  meta.seed ───────────────► sim-queue (RNG) ──► exact piece sequence + hold
   │  meta.handling ───────────► sim-handling ─────► held keys → discrete motion/frame
   │  meta.gamemode ──[registry]► sim-gravity ─────► gravity / 20G / lock delay
   │  inputs (InputEvent...) ──┐
   ▼                           ▼
  sim-engine (per-frame loop): apply inputs (handling) + gravity + rotate(kicks)
                               + lock(Board) → Event ; advance queue/hold
   │
   ▼
  replay-simulate driver → [placements / board states / events]
   │
   └─ validate against meta.results  (the built-in oracle)
```

The engine reuses what already exists and is verified: `rotate`/kicks, `Board.lock`/`Event`, `classify_spin`. What is genuinely new is everything that turns *time + inputs + seed* into *piece positions*: RNG, handling, gravity, and the frame loop.

## Goals / Non-Goals

**Goals**
- Per-platform seeded RNG reproducing the exact bag order; queue + hold.
- A handling model (DAS/ARR/SDF/DCD) converting input events to motion per frame.
- A per-mode gravity profile registry (gravity, 20G, lock delay, lock resets).
- A frame-stepped engine integrating the above with rotation and locking.
- A `simulate(replay)` driver producing reconstructed states and validating against `meta.results`.

**Non-Goals**
- Multiplayer garbage exchange between two players (single-player reconstruction first).
- Rendering.
- Day-one coverage of every TETR.IO mode — Sprint/40l and Jstris sprint are the first validated profiles; others are additive registry entries.
- Re-deriving spin/clear rules (reuse the engine's).

## Decisions

### Native first, teto fallback, validated by the replay itself

We attempt a native Python reconstruction. We do **not** depend on `@haelp/teto` to *know whether we are correct* — each replay carries its own final statistics (`meta.results`: pieces placed, lines, clears, B2B, T-spins, perfect clears). The driver reconstructs the game and compares aggregates; a match is strong evidence the RNG, handling, and gravity are right, and a mismatch localizes the broken layer. `@haelp/teto` is a documented fallback only for TETR.IO if native fidelity stalls; the engine boundary (`engine="native"|"teto"`) is designed so it can be swapped without touching the driver.

### `sim-queue` — RNG, sequence, hold

```python
class Rng(Protocol): def next_float(self) -> float; ...
class TetrioRng(Rng): ...   # TETR.IO's seeded PRNG
class JstrisRng(Rng): ...   # Jstris's seeded PRNG (distinct)

class Queue:  # 7-bag built from an Rng; preview window; next()/peek()
class Hold:   # single slot, once-per-piece lock
```

RNG is the make-or-break and is validated **in isolation first**: generate the bag order from the seed and confirm the resulting game is collision-free and ends at the right piece count. The two platforms use different PRNGs, so `Rng` is a small pluggable protocol.

### `sim-handling` — inputs to motion

A handling state consumes `InputEvent`s and emits discrete moves per frame using `Handling(das, arr, sdf, dcd, ...)`:
- a tap (press+release within DAS) → one cell;
- a hold past DAS → auto-shift at ARR (ARR 0 = instant to wall);
- `sdf` controls soft-drop speed (sdf large / "infinite" = slam to floor);
- `dcd` (DAS cut delay) affects re-engagement after a rotation/other input.
Handling is frame-stepped: at each frame it reports the net horizontal cells and soft-drop applied.

### `sim-gravity` — the central difficulty (per-mode profiles)

**Gravity is not in the replay.** The TETR.IO fixture is `gamemode: "40l"` with no gravity field; it is implied by the mode. Gravity also *differs by mode and ramps* (Blitz increases gravity with level; Quickplay and Quickplay-with-modifiers differ; Zen differs). So gravity lives in a **registry keyed by `(platform, gamemode[, version])`**:

```python
@dataclass(frozen=True)
class GravityProfile:
    g: float                # cells per frame (or a level→g ramp function)
    lock_delay: int         # frames before a grounded piece locks
    lock_resets: int        # max move/rotate lock-delay resets
    is_20g: bool            # piece snaps to bottom on spawn/movement
    # optional ramp: level -> g, margin time, etc.

GRAVITY_PROFILES: dict[tuple[Platform, str], GravityProfile]
def gravity_for(meta) -> GravityProfile   # falls back to a sane default + warns
```

Initial entries: TETR.IO `40l` (Sprint) and Jstris sprint. Others (Blitz ramp, Quickplay, modifiers) are added as needed, each validated against a replay of that mode. A caller may pass an explicit `gravity=GravityProfile(...)` to override the registry (needed for modifier games whose gravity is non-standard).

Correctness here requires getting **20G, lock delay, and lock-reset** right — these determine the final resting row and whether late rotations/spins are possible, so they directly affect both placement positions and spin classification.

### `sim-engine` — the frame loop

```python
@dataclass
class GameState:
    board: Board; queue: Queue; hold: Hold
    active: Piece; frame: int; ...

def step_frame(state, handling_state, gravity, inputs_this_frame) -> list[Event]:
    # 1. apply queued inputs via handling (moves, rotations via rotate()/kicks,
    #    hold, soft drop)
    # 2. apply gravity (cells down; 20g snaps)
    # 3. lock when grounded past lock_delay (or on hardDrop) via Board.lock(piece, spin)
    #    where spin = classify_spin(...) using whether the last action was a rotation
    # 4. spawn next piece from queue; detect top-out
```

The engine reuses `rotate` (kick-aware), `classify_spin`, and `Board.lock` (which already produces `Event`s with B2B/combo under the configured rule). Spin at lock time is computed from whether the last successful action was a rotation — exactly the engine's existing convention.

### `replay-simulate` — driver + oracle

```python
def simulate(replay, *, gravity=None, engine="native") -> ReplaySim
# ReplaySim: ordered placements, per-lock Events, board snapshots, and a
# validation report comparing reconstructed aggregates to replay.meta.results.
```

The validation report is first-class output: `pieces_placed`, `lines`, `b2b`, `tspins`, `perfect_clears` reconstructed vs. expected. Tests assert these match for both fixtures.

### Module layout

```
mino_sdk/sim/
├── rng.py        # Rng protocol, TetrioRng, JstrisRng
├── queue.py      # Queue, Hold
├── handling.py   # handling state machine
├── gravity.py    # GravityProfile, registry, gravity_for
└── engine.py     # GameState, step_frame, top-out
mino_sdk/replay/
└── simulate.py   # simulate(replay), ReplaySim, validation report
```

## Risks / Trade-offs

- **RNG exactness (make-or-break)** → validate bag order in isolation before building the rest; mismatch makes everything else meaningless.
- **Gravity per-mode and unsourced** → registry keyed by mode/version; start with Sprint/40l + Jstris; explicit override for modifier games; 20G/lock-delay/lock-reset are required for correct lock rows.
- **Handling exactness** → DAS/ARR/SDF determine final columns; validate against reconstructed stats.
- **Native fidelity may stall on TETR.IO** → `engine="teto"` fallback boundary preserved; driver unchanged either way.
- **Version drift** → profiles and RNG keyed by version where behavior differs.
- **Scope is large** → ship per layer (rng → handling → gravity → engine → driver), each validated against the fixtures' own stats before proceeding.

## Open Questions

- Exact TETR.IO and Jstris PRNG algorithms and seed handling (string seed `"4fkj9"` for Jstris vs integer seed for TETR.IO) — pinned during the RNG spike.
- Whether soft-drop in these replays is "sonic"/infinite (`sdf`) or stepped — read from handling and validated.
- How to source gravity for Quickplay-with-modifiers, whose gravity is non-standard and may need to be inferred or supplied explicitly.
- Whether to expose a frame-by-frame generator (streaming states) in addition to the batch reconstruction — likely yes for bot/replay tooling, decide during `sim-engine`.
