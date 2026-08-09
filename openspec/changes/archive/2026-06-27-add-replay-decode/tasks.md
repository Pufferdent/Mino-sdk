## 1. Normalized model

- [x] 1.1 Create `tetris_sdk/replay/model.py` with `Platform`, `ReplayInput` enums
- [x] 1.2 Add frozen `InputEvent(frame, subframe, input, pressed)` and `Handling(das, arr, sdf, dcd, extras)`
- [x] 1.3 Add frozen `ReplayMeta(platform, seed, gamemode, handling, allow180, spinbonuses, version, raw_options, results)` and `Replay(meta, inputs)`

## 2. TETR.IO decoder

- [x] 2.1 Create `tetris_sdk/replay/tetrio.py` with the `data.key → ReplayInput` map
- [x] 2.2 Implement `decode_tetrio(obj) -> Replay` — map keydown/keyup events to `InputEvent`s (ordered), drop non-input events
- [x] 2.3 Populate `ReplayMeta` from `replay.options`, top-level `gamemode`, and `replay.results`

## 3. Jstris decoder

- [x] 3.1 Create `tetris_sdk/replay/jstris.py`; LZString-decompress to JSON `{c, d}`; populate `ReplayMeta` from `c`
- [x] 3.2 Reverse-engineer and implement the `d` action-bitstream unpacker → ordered `InputEvent`s
- [x] 3.3 Validate the unpack against the fixture: action counts and timing are monotonic and plausible; document the opcode/timing layout in the module

## 4. Entry points & API

- [x] 4.1 Implement `decode_replay(data)` in `tetris_sdk/replay/__init__.py` with path/str/bytes input and platform auto-detection; raise `ValueError` on unknown
- [x] 4.2 Re-export `decode_tetrio`, `decode_jstris`, and the model types from the package
- [x] 4.3 Export `Replay`, `ReplayMeta`, `InputEvent`, `ReplayInput`, `Platform`, `Handling`, `decode_replay` from `tetris_sdk/__init__.py`
- [x] 4.4 Add `lzstring` to project dependencies

## 5. Tests

- [x] 5.1 `tests/test_replay_decode.py` — TETR.IO: decode `bcf469fc701e.ttr`; assert platform, gamemode `40l`, seed present, handling.das, results non-null, inputs ordered
- [x] 5.2 TETR.IO key mapping: moveLeft/hardDrop/hold → LEFT/HARD_DROP/HOLD with pressed flags; start/end produce no inputs
- [x] 5.3 Jstris: decode `replay_28371693.txt`; assert platform, seed `4fkj9`, das 95, non-empty ordered inputs
- [x] 5.4 `decode_replay` auto-detection for both fixtures; `ValueError` on garbage input
