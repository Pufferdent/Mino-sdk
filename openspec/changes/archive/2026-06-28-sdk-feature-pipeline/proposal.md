## Why

The Mino SDK is being integrated into a PC-NN machine learning pipeline that relies on external tools (py_fumen_py, sfinder.jar) for fumen parsing, board manipulation, PC solving, and save analysis. These external dependencies add subprocess/JVM overhead, discard structured piece-operation data already parsed by the SDK's decoder, and force consumers to build their own utility layer. Bringing these capabilities into the SDK removes external tool dependencies, unblocks Python-native training pipelines, and gives all consumers a cohesive API.

## What Changes

**Non-solver features (standalone utilities):**
- New `MultiFumenPage` class for multi-page fumen decoding that surfaces `Board` + comment per page
- Board string round-trip: `board_from_string()` / `board_to_string()` for the 40-char PC board format
- Piece shape computation: `get_piece_cells(type, rotation, x, y)` — cells a piece occupies at a given placement
- Fumen encoding: `encode_fumen(pages)` to produce v115 fumen strings from SDK data
- Coordinate system documentation and utilities for conversions between SDK, fumen, and PC board conventions
- Piece type enum alignment: mapping tables between fumen piece indices and SDK `PieceType`/`Cell`
- Color-mode fumen field decoding support

**Solver features (new subsystem):**
- Native Python PC solver with exact draw-order enforcement, hold support, and topological ordering
- Wanted-saves expression language (AND/OR/NOT/avoiders/regex/queues) for save analysis
- Save percentage computation and solve filtering

## Capabilities

### New Capabilities
- `fumen-pipeline`: Multi-page fumen parsing, board string conversion, piece shape computation, fumen encoding, coordinate system utilities, piece type mappings, and color-mode decoding
- `solver-engine`: Native perfect-clear solver, hold-aware queue simulation, wanted-saves expression parser and evaluator, save percentage analysis, and solve filtering

### Modified Capabilities
<!-- None — existing APIs remain unchanged. New functionality is additive. -->

## Impact

- New module: `mino_sdk/fumen/pipeline.py` or similar for MultiFumenPage and encoding
- New module: `mino_sdk/solver/` for solver core, save analysis, and expression parser
- New standalone functions: `get_piece_cells()`, `board_from_string()`, `board_to_string()`
- Dependencies: no new external packages needed (existing `lzstring` may be used for fumen encoding if needed by the algorithm)
- Existing `parse_fumen` and `decode_fumen` APIs are not changed
