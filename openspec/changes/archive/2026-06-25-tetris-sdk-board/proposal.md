## Why

Building a Tetris SDK in Python requires a solid foundation — the board. Without a well-defined Board class that models the standard modern Tetris grid (40 rows × 10 columns) and supports importing board states from the widely-used fumen format, downstream features like AI training, replay analysis, and tooling have nothing to build on.

## What Changes

- Introduce the **Board** class, representing a modern Tetris board: 40 rows high, 10 columns wide, with support for cell states (empty, filled, solid).
- Implement local **fumen string parsing** — decode fumen v115 format strings to reconstruct board states, enabling tooling and analysis workflows without external services.
- Provide a clean Python package structure (`tetris_sdk/`) with foundational types and constants.

## Capabilities

### New Capabilities
- `board`: A Board class modeling a standard modern Tetris grid (40 rows × 10 cols), with methods to get/set cells, clear lines, and query board state.
- `fumen-parser`: Parse fumen v115 strings locally to produce Board objects. Supports decoding the compressed run-length encoding used by fumen to reconstruct complete board states.

### Modified Capabilities
<!-- None — this is a greenfield addition -->

## Impact

- New package: `tetris_sdk/` with `board.py` and `fumen/parser.py`
- Dependencies: base64/zlib for fumen decoding (stdlib, no third-party packages required)
- No existing code affected — this is a new module in the project
