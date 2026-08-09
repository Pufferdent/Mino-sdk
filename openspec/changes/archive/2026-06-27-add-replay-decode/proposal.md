## Why

To use Jstris and TETR.IO replays for research, we first have to read them. Neither format stores board states — both are **raw input streams**: TETR.IO `.ttr` is JSON with a `replay.events` list of `keydown`/`keyup` records; Jstris `.txt` is an LZString-compressed JSON whose `d` field is a custom bitstream of timestamped actions. Reconstructing gameplay from these is a *simulation* problem (separate change). Before that, we need a clean, platform-agnostic **decode** step that unpacks each container into one normalized input stream plus metadata.

Splitting decode from simulate lets us ship something tractable and independently useful now (input timelines, APM, finesse, hold rate, handling/seed inspection) and nail the normalized format the simulator will consume — without taking on the hard per-platform engine work yet.

## What Changes

- Introduce a `replay` package with a normalized data model:
  - `Platform` (TETRIO, JSTRIS), `ReplayInput` (LEFT, RIGHT, SOFT_DROP, HARD_DROP, CW, CCW, FLIP, HOLD), and an immutable `InputEvent(frame, subframe, input, pressed)`.
  - `Handling` (arr, das, dcd, sdf, and flags) and `ReplayMeta` (platform, seed, gamemode, handling, allow180, spinbonuses, version, raw options, optional final `results`).
  - `Replay(meta, inputs)` — the decoded result.
- Introduce **TETR.IO decode**: parse the `.ttr` JSON, map each `replay.events` keydown/keyup to an `InputEvent`, and extract `options`/`results` into `ReplayMeta`.
- Introduce **Jstris decode**: LZString-decompress the blob to JSON, read the `c` config (seed, das, version, mode) into `ReplayMeta`, and unpack the `d` action bitstream into `InputEvent`s.
- Introduce **`decode_replay(data)`** with platform auto-detection, plus explicit `decode_tetrio` / `decode_jstris`.

## Capabilities

### New Capabilities
- `replay-decode`: the normalized replay model (`Platform`, `ReplayInput`, `InputEvent`, `Handling`, `ReplayMeta`, `Replay`) and the TETR.IO and Jstris decoders that produce it, with auto-detection.

## Impact

- **New package**: `mino_sdk/replay/` — `model.py` (data types), `tetrio.py`, `jstris.py`, `__init__.py` (`decode_replay`, `decode_tetrio`, `decode_jstris`).
- **Dependency**: `lz-string` (Python `lzstring`) for Jstris decompression.
- **Public API** (`__init__.py`): export `Replay`, `ReplayMeta`, `InputEvent`, `ReplayInput`, `Platform`, `Handling`, `decode_replay`.
- **Tests**: new `tests/test_replay_decode.py` using the two fixtures already in `tests/` (`bcf469fc701e.ttr`, `replay_28371693.txt`).
- **Non-goals (deferred to `add-replay-simulate`)**: piece-sequence reconstruction (seed→bag), handling/gravity simulation, board-state reconstruction, validation against `results`. Decode produces *inputs + metadata only*; it never simulates.
- **Risk**: the Jstris `d` bitstream layout is undocumented (PCReview offloaded it to an external service rather than decode locally). The TETR.IO path is plain JSON and low-risk; the Jstris bitstream is the one reverse-engineering effort in this change.
