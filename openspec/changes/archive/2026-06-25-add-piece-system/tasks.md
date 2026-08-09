## 1. PieceType enum

- [x] 1.1 Create `mino_sdk/pieces.py` with `PieceType(IntEnum)` — T=1, I=2, L=3, J=4, S=5, Z=6, O=7 — and a `cell` property returning the corresponding `Cell` enum value

## 2. RotationSystem and SRS

- [x] 2.1 Implement `RotationSystem` base class with `name` (str), abstract `rotations(piece_type)` and `kicks(piece_type, from_rot, to_rot)` methods
- [x] 2.2 Implement `SRS(RotationSystem)` — define boolean shape matrices for all 7 piece types, generate 4 rotation states by clockwise rotation, apply SRS origin offset adjustments to produce absolute cell offset tuples
- [x] 2.3 Implement SRS JLSTZ kick table — `kicks()` returns standard 5-test wall kick offsets for all 8 clockwise/counter-clockwise transitions
- [x] 2.4 Implement SRS I-piece kick table — distinct from JLSTZ, same 8 transitions
- [x] 2.5 Implement SRS O-piece kicks — returns empty list for all transitions

## 3. Piece class

- [x] 3.1 Implement `Piece` class with `type: PieceType`, `rotation: int` (0-3), `row: int`, `col: int`, `system: RotationSystem` (default `SRS()`)
- [x] 3.2 Implement `cells` property — computes absolute `(row, col)` positions by adding piece position to system's rotation shape offsets
- [x] 3.3 Implement `copy(**overrides)` method — returns new Piece with optionally overridden attributes, preserving system by default

## 4. Board integration

- [x] 4.1 Add `Board.can_place(piece: Piece) -> bool` — returns True iff all cells in `piece.cells` are in-bounds and EMPTY
- [x] 4.2 Add `Board.place(piece: Piece) -> None` — sets each cell to `piece.type.cell`; raises `ValueError` if placement is invalid

## 5. Public API

- [x] 5.1 Export `PieceType`, `RotationSystem`, `SRS`, `Piece` from `mino_sdk/__init__.py` and add to `__all__`

## 6. Tests

- [x] 6.1 `tests/test_pieces.py` — PieceType values and cell mapping
- [x] 6.2 `tests/test_pieces.py` — SRS rotation shapes: 4 states per type, 4 cells per state, I-piece states all distinct, O-piece states all identical
- [x] 6.3 `tests/test_pieces.py` — SRS kick tables: JLSTZ kicks match expected values, I-piece kicks distinct from JLSTZ, O-piece kicks empty
- [x] 6.4 `tests/test_pieces.py` — Piece construction (defaults and explicit values), `cells` property with known shapes at origin and offset positions, `copy` method
- [x] 6.5 `tests/test_pieces.py` — `Board.can_place`: valid placement, blocked by occupied cell, out-of-bounds left/right/bottom/top
- [x] 6.6 `tests/test_pieces.py` — `Board.place`: locks piece cells for each type, raises ValueError on invalid placement, verifies correct Cell enum value per piece type
