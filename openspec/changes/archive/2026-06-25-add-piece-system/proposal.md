## Why

The SDK currently has Board representation and fumen import but no way to express or manipulate tetromino pieces — the fundamental objects of Tetris. Research on placement strategies, AI move evaluation, and game state analysis all require piece types, rotation shapes, wall kick data, and placement operations on a Board.

## What Changes

- Introduce `PieceType` enum: the seven standard tetrominoes (T, I, L, J, S, Z, O) with cell mapping
- Introduce `RotationSystem` abstraction: a pluggable rotation system providing shape data and wall kick tables per piece type. SRS (Super Rotation System) ships as the first implementation, sourced from Techmino's verified data
- Introduce `Piece` class: an active piece positioned on a Board, with type, rotation, position, and a reference to its RotationSystem
- Support piece placement queries: can a piece be placed at a given position/rotation? What cells would it occupy?
- Provide `Board.can_place` and `Board.place` methods

## Capabilities

### New Capabilities
- `piece-system`: Tetromino piece types, pluggable rotation system abstraction, SRS rotation shapes and wall kick tables, and piece placement operations on a Board

### Modified Capabilities
<!-- None - existing Board and fumen-parser specs unchanged -->

## Impact

- **New module**: `tetris_sdk/pieces.py` — PieceType, RotationSystem, SRS class, Piece
- **Modified**: `tetris_sdk/board.py` — `can_place(piece)` and `place(piece)` methods
- **Tests**: New `tests/test_pieces.py`, additional Board tests for placement
- **Public API** (`__init__.py`): Exports PieceType, RotationSystem, SRS, Piece
- **Data source**: SRS shapes and kick tables verified against Techmino's `RSlist.lua` and `gameTables.lua`
