## Context

Replays are the bridge between real play and the SDK's analysis surfaces, but the two target formats are raw input logs, not board states. This change handles only the first half of the pipeline — turning each platform's container into one normalized input stream — so the simulator (`add-replay-simulate`) has a single, platform-agnostic thing to consume.

Observed from the fixtures in `tests/`:

- **TETR.IO** `bcf469fc701e.ttr` — JSON. `replay.events` (709) are `{frame, type: keydown|keyup, data: {key, subframe}}`; keys are `moveLeft/moveRight/softDrop/hardDrop/rotateCW/rotateCCW/rotate180/hold`. `replay.options` holds `seed`, `handling{arr,das,sdf,dcd,...}`, `allow180`, `spinbonuses`, and top-level `gamemode` (`"40l"`). `replay.results.stats` holds final aggregates (piecesplaced, lines, btb, tspins, …). **Gravity is not present** — it is implied by the mode.
- **Jstris** `replay_28371693.txt` — `LZString.decompressFromEncodedURIComponent` → JSON `{c, d}`. `c` = config (`seed`, `das`, `v`, mode flags `m`, timestamps); `d` = a base64 bitstream of timestamped input actions.

## Goals / Non-Goals

**Goals**
- A normalized, immutable model: `Platform`, `ReplayInput`, `InputEvent`, `Handling`, `ReplayMeta`, `Replay`.
- Decode TETR.IO `.ttr` JSON → `Replay`.
- Decode Jstris LZString blob → `Replay` (including the `d` bitstream).
- `decode_replay(data)` auto-detecting the platform.

**Non-Goals**
- Any simulation: no seed→bag, no handling/gravity, no board reconstruction (that is `add-replay-simulate`).
- Mapping `ReplayInput` to engine `Move` (the simulator does that; decode stays engine-agnostic).
- Re-encoding replays (decode only).

## Decisions

### Normalized model

```python
class Platform(Enum): TETRIO; JSTRIS

class ReplayInput(Enum):
    LEFT; RIGHT; SOFT_DROP; HARD_DROP; CW; CCW; FLIP; HOLD

@dataclass(frozen=True)
class InputEvent:
    frame: int
    subframe: float        # 0.0 when the platform has no subframe resolution
    input: ReplayInput
    pressed: bool          # True = keydown/press, False = keyup/release

@dataclass(frozen=True)
class Handling:
    das: float; arr: float; sdf: float; dcd: float
    extras: dict           # platform-specific flags (safelock, cancel, may20g, ...)

@dataclass(frozen=True)
class ReplayMeta:
    platform: Platform
    seed: str | int
    gamemode: str          # e.g. "40l"; "" if unknown
    handling: Handling | None
    allow180: bool
    spinbonuses: str       # e.g. "all-mini", "tspins" ("" if unknown)
    version: str | int
    raw_options: dict      # untouched source options/config for the simulator
    results: dict | None   # final stats, when present (the simulate oracle)

@dataclass(frozen=True)
class Replay:
    meta: ReplayMeta
    inputs: tuple[InputEvent, ...]   # ordered by (frame, subframe)
```

`ReplayInput` is its own vocabulary (not the engine's `Move`) because (a) decode must not depend on the engine, and (b) it needs `HOLD`, which `Move` defers. The simulator maps `ReplayInput → Move` later. `raw_options` is preserved verbatim so the simulator can read anything decode didn't model (gravity-relevant mode fields, modifiers, etc.).

### TETR.IO decoder (low risk)

`decode_tetrio(obj)`:
- `meta.platform = TETRIO`, `seed = options.seed`, `gamemode = top-level "gamemode"`, `handling` from `options.handling`, `allow180 = options.allow180`, `spinbonuses = options.spinbonuses`, `version = options.version`, `raw_options = options`, `results = replay.results`.
- For each event in `replay.events` where `type in {keydown, keyup}`: map `data.key` via a fixed table to `ReplayInput`, `pressed = (type == "keydown")`, carry `frame` and `data.subframe`. `start`/`end` events are dropped (or used only to bound the stream).

Key map: `moveLeft→LEFT, moveRight→RIGHT, softDrop→SOFT_DROP, hardDrop→HARD_DROP, rotateCW→CW, rotateCCW→CCW, rotate180→FLIP, hold→HOLD`.

### Jstris decoder (the risk)

`decode_jstris(text)`:
1. `lzstring.decompressFromEncodedURIComponent(text)` → JSON `{c, d}`.
2. `c` → `ReplayMeta`: `seed = c.seed`, `handling = Handling(das=c.das, arr=0, sdf=?, dcd=0, extras={"m": c.m, "softDropId": c.softDropId})`, `version = c.v`, `gamemode` derived from mode flags `c.m` if determinable else `""`, `raw_options = c`.
3. `d` → `InputEvent`s: base64-decode to bytes and walk the **action bitstream**, emitting `(frame/time, input, pressed)` per action.

**The `d` bitstream is undocumented.** PCReview did not decode it locally — it POSTed the replay to an external `/jstris` service and consumed the returned fumen. So this decoder requires reverse-engineering the layout (action opcodes + timing deltas). Plan: decode a few hundred bytes, correlate action counts and timing against the known totals (Jstris stores piece/line counts), and lock the format with a round-trip/consistency check. If the layout cannot be pinned, fall back to documenting the gap and supporting TETR.IO first (the decoder interface stays the same).

### Auto-detection

`decode_replay(data)`:
- If `data` parses as JSON with a `replay.events` shape → TETR.IO.
- Else if it is an LZString blob (decompresses to JSON with `c`/`d`) → Jstris.
- Else raise `ValueError`. Accepts a path, `str`, or `bytes`.

### Package layout

```
tetris_sdk/replay/
├── __init__.py   # decode_replay, decode_tetrio, decode_jstris + re-exports
├── model.py      # Platform, ReplayInput, InputEvent, Handling, ReplayMeta, Replay
├── tetrio.py     # decode_tetrio
└── jstris.py     # decode_jstris (+ the d-bitstream unpacker)
```

`replay` imports nothing from `engine`/`board` — it is a pure decode layer. Adds a runtime dependency on `lzstring`.

## Risks / Trade-offs

- **Jstris `d` bitstream undocumented** → the central risk. Mitigated by tackling TETR.IO first behind the same interface, and validating the Jstris unpack against action/timing totals. If unsolved, TETR.IO still ships.
- **`lzstring` dependency** → small, pure-Python; acceptable for a decode-only concern.
- **Format drift** → `version`/`raw_options` are preserved so the simulator and future versions can adapt without re-decoding.
- **Subframe semantics** → kept as a float on every event; Jstris (no subframes) uses `0.0`. The simulator decides how to consume them.

## Open Questions

- Exact Jstris `d` opcode table and timing encoding — to be reverse-engineered during implementation.
- Whether to model `start`/`end`/garbage/seed-reset events as `InputEvent`s or as separate meta — current design drops non-input events but keeps `raw_options`; revisit if the simulator needs them.
- Jstris `gamemode` derivation from the `m` flags bitfield — may stay `""` until the simulator needs it.
